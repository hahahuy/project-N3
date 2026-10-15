# R2S-104: Top-down source visualizer evidence

## Contract

`real2scenario-visualize` consumes a validated baseline or variant JSON artifact,
not raw nuScenes files. It renders canonical trajectories in their declared
coordinate frame with SI-meter axes:

- ego path and marker: red;
- each non-ego actor: a separate stable color;
- title: scenario ID, coordinate frame, and current time.

The interactive `--show` view has a time slider plus Play/Pause control. Actors
that appear later than the selected time remain hidden until their first state.
The headless `--output` path creates a PNG for review evidence without opening a
window.

## Commands

```bash
source .venv/bin/activate
real2scenario-visualize /tmp/scenario.json --output /tmp/source-top-down.png
real2scenario-visualize /tmp/scenario.json --show
```

The artifact must first be produced with the canonical serialization contract.
For M1 review, use a source window between 8 and 20 seconds after R2S-103 has
written its selected actor provenance.

## Automated evidence

`tests/test_visualization.py` verifies late-appearing actor state lookup and a
non-empty headless PNG generated from a synthetic canonical scenario. A CLI
smoke run also wrote `/tmp/visualization-fixture.png` from a validated synthetic
baseline artifact. No licensed data or derived trajectory is committed.

## Real-data M1 evidence

A local-only artifact and plot were generated from `scene-0061` with the full
licensed mini dataset:

- Scene token: `cc8c0bf57f984915a77078b10eb33198`.
- Window: first through thirty-ninth keyframe, 19.149566 s.
- Candidate instance tokens:
  `6dd2cbf4c24b4caeb625035869bca7b5`,
  `48d58b69b40149aeb2e64aa4b1a9192f`, and
  `bd26c2cdb22d4bb1834e808c89128898`.
- Selection config: `max_distance_m=50.0`, `max_ttc_s=5.0`, `max_actors=3`.
- All three candidates qualified by distance; their decision metrics are stored
  in the local artifact provenance.
- Local-only outputs: `/tmp/m1-source-scenario.json` and
  `/tmp/m1-source-top-down.png` (81,394 bytes).

The artifact and PNG are derived from licensed nuScenes data and intentionally
remain outside the repository.
