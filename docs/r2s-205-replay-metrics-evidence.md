# R2S-205 Replay Fidelity Metrics Evidence

`compute_replay_metrics()` compares a recorded and replayed trajectory in SI
units. The alignment policy is named
`recorded_timestamps_linear_interpolation_within_overlap`: each recorded
timestamp within the replay interval receives a linearly interpolated replay
state. Position RMSE and final displacement are metres; heading MAE is radians
with angle wrapping; speed MAE is metres per second.

Each `ReplayMetrics` result includes its alignment method and sample count.
Empty inputs, non-monotonic input timestamps, or trajectories with no overlapping
timestamp raise a clear `ValueError`; missing actors are rejected by
`ReplayTrace.states_for()`.

`tests/test_metrics.py` covers a hand-calculated alignment example, heading wrap
at the `-pi`/`pi` boundary, empty/mismatched error paths, and metrics for every
actor in a scenario replay trace.
