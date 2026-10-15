"""Recipe documents, rollback markers and non-destructive undo/redo.

A Workspace scenario is a parametric document: its construction is an ordered
recipe of constrained maneuver steps.  This module owns that document so the
browser never has to invent step order, step status, rollback markers or undo
history.

Rules this module enforces:

* Steps are ordered.  Order is explicit state, not an artifact of insertion
  time, and can be changed without re-writing any step.
* Step parameters are constrained maneuver parameters.  Free displacement and
  per-axis velocity are rejected, exactly as the preview endpoint rejects them.
* Step status is ``valid`` when the parameters sit inside the Tier 1 kinematic
  limit profile, ``invalid`` when they exceed a limit (with the violation and
  the limit named), and ``error`` when the API rejected the step.
* Undo and redo move between whole document snapshots.  They are non
  destructive: the canonical scenario and every artifact under the artifact root
  are never written, and the parent document stays immutable.
* Rollback markers name a step count.  Restoring one truncates the recipe to
  that count and marks later steps inactive instead of deleting evidence.

The document lives in process.  Nothing is persisted to disk, so the contract
carries an explicit persistence availability block instead of implying that a
recipe survives a restart.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from math import isfinite
from typing import Mapping, Sequence

from real2scenario.kinematic import KINEMATIC_VERSION, KinematicLimits
from real2scenario.models import Scenario

from .adapter import ArtifactRecord
from .schemas import (
    ActorMotionEditRequest,
    RecipeStepRequest,
    RecipeStepStateRequest,
    RollbackMarkerRequest,
    StepMoveRequest,
)

RECIPE_VERSION = "workspace-recipe-v1"
STEP_STATUS_VALID = "valid"
STEP_STATUS_INVALID = "invalid"
STEP_STATUS_ERROR = "error"
STEP_STATUSES = (STEP_STATUS_VALID, STEP_STATUS_INVALID, STEP_STATUS_ERROR)

MOVE_DIRECTIONS = ("up", "down")
INACTIVE_AFTER_MARKER = "after_active_rollback_marker"
INACTIVE_STEP = "operator_deactivated_this_step"

REASON_RECORD_NOT_PERSISTED = "recipe_document_is_held_in_process_and_is_not_persisted_to_disk"
REASON_NO_UNDO_HISTORY = "no_undo_history_for_this_document"
REASON_NO_REDO_HISTORY = "no_redo_history_for_this_document"
REASON_UNKNOWN_ACTOR = "actor_is_not_present_in_this_scenario"
REASON_INVALID_TIME_RANGE = "end_time_s_must_not_precede_start_time_s"
REASON_NON_FINITE_PARAMETER = "maneuver_parameter_must_be_finite"

RECIPE_MUTATION = "workspace-recipe-store"
PARENT_IMMUTABLE = True


@dataclass(frozen=True, slots=True)
class RecipeStep:
    """One ordered constrained maneuver step."""

    step_id: str
    name: str
    kind: str
    parameters: ActorMotionEditRequest
    status: str
    active: bool
    inactive_reason: str | None
    violations: tuple[Mapping[str, object], ...]
    error: str | None
    artifact: Mapping[str, object] | None
    artifact_unavailable_reason: str | None

    def to_dict(self, index: int) -> dict[str, object]:
        return {
            "index": index,
            "step_id": self.step_id,
            "name": self.name,
            "kind": self.kind,
            "status": self.status,
            "active": self.active,
            "inactive_reason": self.inactive_reason,
            "parameters": self.parameters.model_dump(),
            "violations": [dict(violation) for violation in self.violations],
            "error": self.error,
            "artifact": None if self.artifact is None else dict(self.artifact),
            "artifact_unavailable_reason": self.artifact_unavailable_reason,
        }


@dataclass(frozen=True, slots=True)
class RollbackMarker:
    """A named point in the ordered recipe that a document can roll back to."""

    marker_id: str
    name: str
    step_count: int
    revision: int

    def to_dict(self) -> dict[str, object]:
        return {
            "marker_id": self.marker_id,
            "name": self.name,
            "step_count": self.step_count,
            "revision": self.revision,
        }


@dataclass(frozen=True, slots=True)
class RecipeSnapshot:
    """The complete, restorable state of one recipe document."""

    steps: tuple[RecipeStep, ...] = ()
    markers: tuple[RollbackMarker, ...] = ()
    active_marker_id: str | None = None
    revision: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "steps": [step.to_dict(index) for index, step in enumerate(self.steps)],
            "markers": [marker.to_dict() for marker in self.markers],
            "active_marker_id": self.active_marker_id,
            "revision": self.revision,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "RecipeSnapshot":
        from .schemas import ActorMotionEditRequest as _Edit

        return cls(
            steps=tuple(
                RecipeStep(
                    step_id=str(step["step_id"]),
                    name=str(step["name"]),
                    kind=str(step["kind"]),
                    parameters=_Edit(**step["parameters"]),  # type: ignore[arg-type]
                    status=str(step["status"]),
                    active=bool(step["active"]),
                    inactive_reason=step["inactive_reason"],  # type: ignore[arg-type]
                    violations=tuple(step["violations"]),  # type: ignore[arg-type]
                    error=step["error"],  # type: ignore[arg-type]
                    artifact=step["artifact"],  # type: ignore[arg-type]
                    artifact_unavailable_reason=step["artifact_unavailable_reason"],  # type: ignore[arg-type]
                )
                for step in payload["steps"]  # type: ignore[union-attr]
            ),
            markers=tuple(
                RollbackMarker(
                    marker_id=str(marker["marker_id"]),
                    name=str(marker["name"]),
                    step_count=int(marker["step_count"]),  # type: ignore[arg-type]
                    revision=int(marker["revision"]),  # type: ignore[arg-type]
                )
                for marker in payload["markers"]  # type: ignore[union-attr]
            ),
            active_marker_id=payload["active_marker_id"],  # type: ignore[arg-type]
            revision=int(payload["revision"]),  # type: ignore[arg-type]
        )


@dataclass(slots=True)
class RecipeDocument:
    """One scenario's recipe document plus its undo and redo stacks."""

    record: ArtifactRecord
    current: RecipeSnapshot = field(default_factory=RecipeSnapshot)
    undo_stack: list[RecipeSnapshot] = field(default_factory=list)
    redo_stack: list[RecipeSnapshot] = field(default_factory=list)
    marker_sequence: int = 0

    def apply(self, snapshot: RecipeSnapshot) -> None:
        """Move to a new document state, keeping the previous one for undo."""
        self.undo_stack.append(self.current)
        self.current = snapshot
        self.redo_stack.clear()


class RecipeStore:
    """In-process, non-destructive recipe documents keyed by scenario id."""

    def __init__(self) -> None:
        self._documents: dict[str, RecipeDocument] = {}

    def document(self, record: ArtifactRecord) -> RecipeDocument:
        document = self._documents.get(record.scenario.scenario_id)
        if document is None:
            document = RecipeDocument(record=record)
            self._documents[record.scenario.scenario_id] = document
        return document

    def view(self, record: ArtifactRecord) -> dict[str, object]:
        document = self.document(record)
        snapshot = document.current
        return {
            "contract_version": RECIPE_VERSION,
            "scenario_id": record.scenario.scenario_id,
            "coordinate_frame": record.scenario.coordinate_frame,
            "parent_scenario_id": record.parent_scenario_id,
            "parent_immutable": PARENT_IMMUTABLE,
            "mutation": RECIPE_MUTATION,
            "persistence": {
                "available": False,
                "unavailable_reason": REASON_RECORD_NOT_PERSISTED,
            },
            "limits": _limits(),
            "steps": [step.to_dict(index) for index, step in enumerate(snapshot.steps)],
            "step_count": len(snapshot.steps),
            "active_step_count": sum(step.active for step in snapshot.steps),
            "rollback_markers": [marker.to_dict() for marker in snapshot.markers],
            "active_marker_id": snapshot.active_marker_id,
            "history": {
                "revision": snapshot.revision,
                "undo_depth": len(document.undo_stack),
                "redo_depth": len(document.redo_stack),
                "non_destructive": True,
                "undo_unavailable_reason": None if document.undo_stack else REASON_NO_UNDO_HISTORY,
                "redo_unavailable_reason": None if document.redo_stack else REASON_NO_REDO_HISTORY,
                "undoable": bool(document.undo_stack),
                "redoable": bool(document.redo_stack),
            },
            "artifact_visibility": "local_private",
        }

    # -- mutations -------------------------------------------------------
    def add_step(self, record: ArtifactRecord, request: RecipeStepRequest) -> dict[str, object]:
        """Append one validated step; a rejected step is stored with its error."""
        document = self.document(record)
        step = build_step(record.scenario, request, index=len(document.current.steps))
        candidate = replace(document.current, steps=document.current.steps + (step,))
        document.apply(_bump(_apply_marker(candidate)))
        return self.view(record)

    def set_step_active(
        self, record: ArtifactRecord, step_id: str, request: RecipeStepStateRequest
    ) -> dict[str, object]:
        """Activate or deactivate one step without removing its evidence."""
        document = self.document(record)
        step = _step_by_id(document.current, step_id)
        if request.active and step.inactive_reason == INACTIVE_AFTER_MARKER:
            raise ValueError(
                f"step {step_id!r} is after the active rollback marker and cannot be activated."
            )
        updated = replace(
            step,
            active=request.active,
            inactive_reason=None if request.active else (step.inactive_reason or INACTIVE_STEP),
        )
        document.apply(
            _bump(replace(document.current, steps=_replace_step(document.current.steps, updated)))
        )
        return self.view(record)

    def remove_step(self, record: ArtifactRecord, step_id: str) -> dict[str, object]:
        """Remove one step; undo restores it with its parameters and status."""
        document = self.document(record)
        _step_by_id(document.current, step_id)
        remaining = tuple(step for step in document.current.steps if step.step_id != step_id)
        document.apply(
            _bump(
                replace(
                    document.current,
                    steps=remaining,
                    markers=tuple(
                        marker for marker in document.current.markers
                        if marker.step_count <= len(remaining)
                    ),
                )
            )
        )
        return self.view(record)

    def move_step(
        self, record: ArtifactRecord, request: StepMoveRequest
    ) -> dict[str, object]:
        """Move one step by exactly one position, preserving every parameter."""
        document = self.document(record)
        steps = list(document.current.steps)
        index = _step_index(document.current, request.step_id)
        target = index - 1 if request.direction == "up" else index + 1
        if target < 0 or target >= len(steps):
            raise ValueError(
                f"step {request.step_id!r} cannot move {request.direction} at the recipe edge."
            )
        steps[index], steps[target] = steps[target], steps[index]
        document.apply(_bump(replace(document.current, steps=tuple(steps))))
        return self.view(record)

    def add_marker(self, record: ArtifactRecord, request: RollbackMarkerRequest) -> dict[str, object]:
        """Mark the current step count as a rollback point."""
        document = self.document(record)
        document.marker_sequence += 1
        marker = RollbackMarker(
            marker_id=f"marker-{document.marker_sequence}",
            name=request.name.strip(),
            step_count=len(document.current.steps),
            revision=document.current.revision + 1,
        )
        snapshot = replace(
            document.current,
            markers=document.current.markers + (marker,),
            active_marker_id=marker.marker_id,
        )
        document.apply(_bump(snapshot))
        return self.view(record)

    def restore_marker(self, record: ArtifactRecord, marker_id: str) -> dict[str, object]:
        """Roll back to a marker: truncate steps, keep later steps as inactive."""
        document = self.document(record)
        marker = next(
            (item for item in document.current.markers if item.marker_id == marker_id), None
        )
        if marker is None:
            raise KeyError(f"Rollback marker {marker_id!r} was not found.")
        kept = document.current.steps[: marker.step_count]
        trailing = tuple(
            replace(step, active=False, inactive_reason=INACTIVE_AFTER_MARKER)
            for step in document.current.steps[marker.step_count:]
        )
        document.apply(
            _bump(
                replace(
                    document.current,
                    steps=kept + trailing,
                    active_marker_id=marker.marker_id,
                    markers=tuple(
                        item for item in document.current.markers
                        if item.step_count <= marker.step_count
                    ),
                )
            )
        )
        return self.view(record)

    def undo(self, record: ArtifactRecord) -> dict[str, object]:
        """Step one state back.  Never touches a canonical artifact."""
        document = self.document(record)
        if not document.undo_stack:
            raise ValueError(REASON_NO_UNDO_HISTORY)
        previous = document.undo_stack.pop()
        document.redo_stack.append(document.current)
        document.current = previous
        return self.view(record)

    def redo(self, record: ArtifactRecord) -> dict[str, object]:
        """Step one state forward over an undone change."""
        document = self.document(record)
        if not document.redo_stack:
            raise ValueError(REASON_NO_REDO_HISTORY)
        following = document.redo_stack.pop()
        document.undo_stack.append(document.current)
        document.current = following
        return self.view(record)

    def applied_edits(self, record: ArtifactRecord) -> list[ActorMotionEditRequest]:
        """Active steps in order, for the Tier 1 preview request."""
        return [step.parameters for step in self.document(record).current.steps if step.active]


def build_step(
    scenario: Scenario, request: RecipeStepRequest, *, index: int
) -> RecipeStep:
    """Validate one step against the scenario and the Tier 1 limit profile."""
    try:
        violations = _validate(scenario, request.actor_edit)
    except ValueError as error:
        return RecipeStep(
            step_id=request.step_id,
            name=request.name,
            kind=request.kind,
            parameters=request.actor_edit,
            status=STEP_STATUS_ERROR,
            active=False,
            inactive_reason=None,
            violations=(),
            error=str(error),
            artifact=None,
            artifact_unavailable_reason="recipe_step_preview_artifact_not_created",
        )
    return RecipeStep(
        step_id=request.step_id,
        name=request.name,
        kind=request.kind,
        parameters=request.actor_edit,
        status=STEP_STATUS_INVALID if violations else STEP_STATUS_VALID,
        active=request.active and not violations,
        inactive_reason=None
        if request.active and not violations
        else ("parameter_limit_exceeded" if violations else None),
        violations=violations,
        error=None,
        artifact=None,
        artifact_unavailable_reason="recipe_step_preview_artifact_not_created",
    )


def _validate(scenario: Scenario, edit: ActorMotionEditRequest) -> tuple[Mapping[str, object], ...]:
    """Reject free edits and name every exceeded Tier 1 limit."""
    if edit.actor_id not in {actor.actor_id for actor in scenario.actors}:
        raise ValueError(f"{REASON_UNKNOWN_ACTOR}:{edit.actor_id}")
    if edit.end_time_s is not None and edit.end_time_s < edit.start_time_s:
        raise ValueError(REASON_INVALID_TIME_RANGE)
    for value in (
        edit.speed_multiplier,
        edit.heading_offset_rad,
        edit.timing_offset_s,
        edit.initial_gap_delta_m,
        edit.steering_angle_rad,
        edit.acceleration_mps2,
        edit.braking_mps2,
        edit.target_speed_mps,
    ):
        if value is not None and not isfinite(float(value)):
            raise ValueError(f"{REASON_NON_FINITE_PARAMETER}:{edit.actor_id}")
    limits = KinematicLimits()
    violations: list[Mapping[str, object]] = []
    if edit.acceleration_mps2 is not None and edit.acceleration_mps2 > limits.max_acceleration_mps2:
        violations.append(
            _violation("acceleration_exceeded", edit, edit.acceleration_mps2, limits.max_acceleration_mps2)
        )
    if edit.braking_mps2 is not None and edit.braking_mps2 > limits.max_deceleration_mps2:
        violations.append(
            _violation("deceleration_exceeded", edit, edit.braking_mps2, limits.max_deceleration_mps2)
        )
    if abs(edit.steering_angle_rad) > limits.max_yaw_rate_radps:
        violations.append(
            _violation("yaw_rate_exceeded", edit, abs(edit.steering_angle_rad), limits.max_yaw_rate_radps)
        )
    return tuple(violations)


def _violation(
    code: str, edit: ActorMotionEditRequest, observed: float, limit: float
) -> Mapping[str, object]:
    return {
        "code": code,
        "actor_id": edit.actor_id,
        "observed": observed,
        "limit": limit,
        "provenance": KINEMATIC_VERSION,
    }


def _limits() -> dict[str, object]:
    limits = KinematicLimits()
    return {
        "version": limits.version,
        "simulator": KINEMATIC_VERSION,
        "max_acceleration_mps2": limits.max_acceleration_mps2,
        "max_deceleration_mps2": limits.max_deceleration_mps2,
        "max_yaw_rate_radps": limits.max_yaw_rate_radps,
        "silent_clamps": "forbidden",
    }


def _bump(snapshot: RecipeSnapshot) -> RecipeSnapshot:
    """Advance the document revision; the caller decides the new content."""
    return replace(snapshot, revision=snapshot.revision + 1)


def _apply_marker(snapshot: RecipeSnapshot) -> RecipeSnapshot:
    """Keep steps after the active rollback marker inactive rather than deleted."""
    if snapshot.active_marker_id is None:
        return snapshot
    marker = next(
        (item for item in snapshot.markers if item.marker_id == snapshot.active_marker_id), None
    )
    if marker is None:
        return snapshot
    return replace(
        snapshot,
        steps=tuple(
            replace(step, active=False, inactive_reason=INACTIVE_AFTER_MARKER)
            if index >= marker.step_count and step.active
            else step
            for index, step in enumerate(snapshot.steps)
        ),
    )


def _replace_step(steps: Sequence[RecipeStep], updated: RecipeStep) -> tuple[RecipeStep, ...]:
    return tuple(updated if step.step_id == updated.step_id else step for step in steps)


def _step_by_id(snapshot: RecipeSnapshot, step_id: str) -> RecipeStep:
    for step in snapshot.steps:
        if step.step_id == step_id:
            return step
    raise KeyError(f"Recipe step {step_id!r} was not found.")


def _step_index(snapshot: RecipeSnapshot, step_id: str) -> int:
    for index, step in enumerate(snapshot.steps):
        if step.step_id == step_id:
            return index
    raise KeyError(f"Recipe step {step_id!r} was not found.")
