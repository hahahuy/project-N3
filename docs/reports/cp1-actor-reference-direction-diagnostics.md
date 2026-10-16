# CP1 Actor Reference and Direction Diagnostics

## Status

`IMPLEMENTED`, `TESTED`, `DIAGNOSTIC`, `PROVISIONAL`, `OWNER-REVIEW-REQUIRED`

This report records the next additive CP1 semantic-alignment slice. It does not
replace the immutable `20/143 = 13.99%` selected-corridor baseline, change actor
selection, reverse production lane direction, or claim CP1 acceptance.

## Scope

The diagnostic compares the same scenario against explicitly named lane graphs
and evaluates only globally declared actor-reference hypotheses:

- `annotation_center`;
- `rear_axle`;
- `front_axle`;
- `fixed_heading_offset`.

Axle hypotheses require actor length. Missing dimensions remain unsupported and
are not guessed. The fixed heading offset is a declared counterfactual only; it
does not alter the canonical scenario or ingestion convention.

The direction diagnostic retains, per state:

- annotation yaw;
- motion heading from adjacent trajectory positions;
- selected reference lane heading;
- annotation and motion heading errors;
- a diagnostic classification.

No lane graph is reversed or mutated. Direction results remain counterfactual and
must be interpreted with native, canonical and generated-reference provenance.

## Backend Contracts

Implemented in `src/real2scenario/road_match.py`:

- `analyze_actor_reference_sensitivity()`;
- `classify_direction_counterfactuals()`;
- `actor-reference-sensitivity-v1`;
- `direction-counterfactual-v1`.

The existing `compare_lane_references()` contract now also preserves lane and
motion headings on matched state diagnostics. All reports remain explicitly
`diagnostic` and `PROVISIONAL`.

## Verification

```text
focused road-match tests: 22 passed
related model/mapbuilder tests: 43 passed
full suite before this slice: 201 passed, 1 warning
docs consistency before this slice: PASS
```

The attempted compileall check was blocked by pre-existing unwritable
`__pycache__` files. It was not used as acceptance evidence.

## Scene-0061 Private Run

The runner `scripts/run_cp1_reference_diagnostics.py` was executed against the
existing private corridor bundle and local `v1.0-trainval` dataset:

```text
command:
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_cp1_reference_diagnostics.py \
  --evidence-root "$CP1_EVIDENCE_ROOT" \
  --dataset-root "$NUSCENES_ROOT"

private output: `$CP1_EVIDENCE_ROOT/semantic-follow-up/`
git revision: 4137164936c6535147491fb0f065bed8d4f8f729
scene: scene-0061
states: 143
selected lanes: 82
generated XODR lanes: 82
XODR SHA-256: 79461c44d6b158b6b1abb63d2f11f984d33bee626fc5ce5f4c229b3b67cb75e5
```

Native direction classifications were `47 aligned`, `53 annotation_only`,
`16 source_annotation_yaw_error`, `3 true_reverse_motion` and `24 uncertain`.
Generated XODR classifications were `47 aligned`, `53 annotation_only`, `8
source_annotation_yaw_error` and `35 uncertain`. The native `true_reverse_motion`
states are confined to the `instance-fdd...` actor and remain counterfactual;
the generated XODR parser cannot establish the same direction classification for
that actor because its lightweight lane association is unresolved.

The native annotation-center lateral means were:

| Actor | Mean lateral | P95 lateral | Interpretation |
|---|---:|---:|---|
| ego | 0.535 m | 1.424 m | native reference is close; ego occupancy still unsupported |
| `instance-e91...` | 3.167 m | 3.364 m | lateral association/reference unresolved |
| `instance-e3c...` | 5.031 m | 5.031 m | direction/reference semantics unresolved |
| `instance-fdd...` | 7.317 m | 7.403 m | lateral association/reference unresolved |

The globally declared axle and fixed-offset hypotheses did not produce a
cross-actor resolution. Native means for `instance-e91...` ranged from 3.093 m
to 3.256 m across rear/front axle hypotheses; `instance-fdd...` ranged from
6.750 m to 7.570 m. The ego axle hypotheses were unsupported because ego
dimensions are absent. No hypothesis is promoted to production behavior.

The private run card and raw outputs remain outside the repository at
`$CP1_EVIDENCE_ROOT/semantic-follow-up/`. No raw nuScenes or
trajectory-derived private artifact was added to the repository.

## Decisions and Boundaries

- The native/canonical/XODR comparison remains the source of reference-model
  results; this slice adds sensitivity and heading evidence only.
- No actor-specific offset is introduced.
- No tolerance, HMM weight, actor-selection or ground-truth policy changes.
- Ego dimensions remain unsupported when absent.
- CP1 remains `PARTIAL/PROVISIONAL`.

## Next Action

Run the new contracts against the private scene-0061 evidence bundle and record
the per-reference rows in the owner-review report. Then decide whether the
remaining lateral and direction findings stay unresolved; do not promote a
counterfactual hypothesis into production without owner approval and repeated
cross-scene evidence.
