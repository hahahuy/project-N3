"""Top-down review of canonical source trajectories."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .models import Actor, Scenario, State
from .serialization import artifact_from_json


def save_top_down_plot(scenario: Scenario, output_path: str | Path, *, time_s: float | None = None) -> None:
    """Save a top-down trajectory plot at a requested scenario time."""
    viewer = TopDownViewer(scenario, interactive=False)
    viewer.set_time(scenario.duration_s if time_s is None else time_s)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    viewer.figure.savefig(output, bbox_inches="tight", dpi=150)
    viewer.close()


class TopDownViewer:
    """Interactive Matplotlib review surface with a time scrubber and playback."""

    def __init__(self, scenario: Scenario, *, interactive: bool = True) -> None:
        pyplot, animation_class, button_class, slider_class = _load_matplotlib()
        self._pyplot = pyplot
        self._animation = animation_class
        self._scenario = scenario
        self._playing = False
        self.figure, self.axes = pyplot.subplots(figsize=(10, 8))
        self.figure.subplots_adjust(bottom=0.2)
        self._markers: dict[str, object] = {}
        self._draw_trajectories()

        self.slider = None
        self.button = None
        self._animation_handle = None
        if interactive:
            slider_axes = self.figure.add_axes((0.15, 0.08, 0.62, 0.03))
            self.slider = slider_class(
                slider_axes,
                "Time (s)",
                0.0,
                scenario.duration_s,
                valinit=0.0,
                valstep=None,
            )
            self.slider.on_changed(self.set_time)
            button_axes = self.figure.add_axes((0.8, 0.065, 0.12, 0.06))
            self.button = button_class(button_axes, "Play")
            self.button.on_clicked(self._toggle_playback)
            self._animation_handle = animation_class(
                self.figure, self._advance, interval=100, cache_frame_data=False
            )
            self._animation_handle.event_source.stop()
        self.set_time(0.0)

    def set_time(self, time_s: float) -> None:
        """Move actor markers to states available at or before ``time_s``."""
        clamped_time_s = min(max(float(time_s), 0.0), self._scenario.duration_s)
        for actor in self._scenario.actors:
            state = _state_at_or_before(actor, clamped_time_s)
            marker = self._markers[actor.actor_id]
            if state is None:
                marker.set_data([], [])
            else:
                marker.set_data([state.x_m], [state.y_m])
        self.axes.set_title(
            f"{self._scenario.scenario_id} | {self._scenario.coordinate_frame} | "
            f"t={clamped_time_s:.2f}s"
        )
        self.figure.canvas.draw_idle()

    def show(self) -> None:
        """Open the interactive viewer."""
        self._pyplot.show()

    def close(self) -> None:
        """Close the viewer's Matplotlib figure."""
        self._pyplot.close(self.figure)

    def _draw_trajectories(self) -> None:
        all_x: list[float] = []
        all_y: list[float] = []
        for index, actor in enumerate(self._scenario.actors):
            color = "#d42b2b" if actor.actor_id == self._scenario.ego_actor_id else _ACTOR_COLORS[
                index % len(_ACTOR_COLORS)
            ]
            x_values = [state.x_m for state in actor.trajectory]
            y_values = [state.y_m for state in actor.trajectory]
            label = "ego" if actor.actor_id == self._scenario.ego_actor_id else actor.actor_id
            self.axes.plot(x_values, y_values, color=color, linewidth=2.5, label=label)
            (marker,) = self.axes.plot(
                [], [], marker="o", color=color, markersize=8, linestyle="None"
            )
            self._markers[actor.actor_id] = marker
            all_x.extend(x_values)
            all_y.extend(y_values)

        padding_m = max(5.0, max(max(all_x) - min(all_x), max(all_y) - min(all_y)) * 0.1)
        self.axes.set_xlim(min(all_x) - padding_m, max(all_x) + padding_m)
        self.axes.set_ylim(min(all_y) - padding_m, max(all_y) + padding_m)
        self.axes.set_aspect("equal", adjustable="box")
        self.axes.set_xlabel("x (m)")
        self.axes.set_ylabel("y (m)")
        self.axes.grid(True, alpha=0.3)
        self.axes.legend(loc="best")

    def _toggle_playback(self, _event: object) -> None:
        self._playing = not self._playing
        assert self.button is not None
        assert self._animation_handle is not None
        self.button.label.set_text("Pause" if self._playing else "Play")
        if self._playing:
            self._animation_handle.event_source.start()
        else:
            self._animation_handle.event_source.stop()

    def _advance(self, _frame: object) -> None:
        if not self._playing:
            return
        assert self.slider is not None
        next_time_s = self.slider.val + self._scenario.duration_s / 100.0
        self.slider.set_val(0.0 if next_time_s > self._scenario.duration_s else next_time_s)


def _state_at_or_before(actor: Actor, time_s: float) -> State | None:
    state: State | None = None
    for candidate in actor.trajectory:
        if candidate.time_s > time_s:
            break
        state = candidate
    return state


def _load_matplotlib():
    try:
        from matplotlib import pyplot
        from matplotlib.animation import FuncAnimation
        from matplotlib.widgets import Button, Slider
    except ImportError as error:
        raise RuntimeError(
            "Matplotlib is not installed. Install the project with the 'devkit' extra: "
            "pip install -e '.[dev,devkit]'."
        ) from error
    return pyplot, FuncAnimation, Button, Slider


def main(argv: Sequence[str] | None = None) -> int:
    """Render or display a canonical scenario artifact."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path, help="Baseline or variant JSON artifact.")
    parser.add_argument("--output", type=Path, help="Optional PNG output path.")
    parser.add_argument("--time-s", type=float, help="Time to render; defaults to scenario end.")
    parser.add_argument("--show", action="store_true", help="Open the interactive scrub/play viewer.")
    args = parser.parse_args(argv)
    if args.output is None and not args.show:
        parser.error("Provide --output, --show, or both.")
    try:
        scenario, _, _ = artifact_from_json(args.artifact.read_text(encoding="utf-8"))
        if args.output is not None:
            save_top_down_plot(scenario, args.output, time_s=args.time_s)
            print(f"Wrote top-down plot to {args.output}")
        if args.show:
            viewer = TopDownViewer(scenario)
            viewer.set_time(0.0 if args.time_s is None else args.time_s)
            viewer.show()
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))
    return 0


_ACTOR_COLORS = ("#1677b8", "#d17b0f", "#6d9c40", "#7e57c2", "#b74779")


if __name__ == "__main__":
    sys.exit(main())
