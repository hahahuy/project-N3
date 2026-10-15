# R2S-204 esmini Runner and Trace Evidence

`run_esmini()` accepts an explicit `EsminiConfig.executable` or the external
`ESMINI_BIN` environment variable. It invokes the configured binary with
`--osc`, `--headless`, and `--record`; no executable or local simulator path is
committed to the codebase. esmini records a binary DAT file, so the caller also
configures its `dat2csv` companion via `EsminiConfig.trace_converter` or
`ESMINI_DAT2CSV` to create the normalized CSV trace.

The runner defaults to a deterministic `0.05 s` fixed timestep and requests 12
decimal places from `dat2csv`, avoiding duplicate timestamps caused by rounding
sub-millisecond real-time simulator steps to the converter's default precision.

Every `ReplayReport` records the exact command, completion status, timeout flag,
exit code, stdout, stderr, tool version when available, requested trace path,
and parsed trace when successful. Failure reports preserve the diagnostic output
instead of raising away simulator evidence.

The `dat2csv` input header is:

```text
time,id,name,x,y,z,h,p,r,speed,wheel_angle,wheel_rot
```

The parser normalizes `time`, `name`, `x`, `y`, `h`, and `speed` into the
project contract: time in seconds, positions in metres, heading in radians, and
speed in metres per second. Timestamps must strictly increase per actor.

`save_replay_overlay()` produces the review PNG required by the M2 checkpoint:
solid lines are explicitly labeled `recorded` and dashed lines `replayed`.
The initial tests cover failure diagnostics and parser error paths. A local
esmini installation is still required for the M2 integration replay evidence.
