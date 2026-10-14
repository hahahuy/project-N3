# M5B Manual Run Record

Copy to a local ignored location. Do not commit binaries, recordings, credentials, or absolute paths.

- Run ID / UTC:
- Operator / git revision:
- Preflight output:
- CARLA server/client/Python versions:
- Launch method, command, port, host/GPU:
- World ID and reconstruction mode:
- Scenario: scene-0061; duration; source artifact:
- Synchronous mode: yes/no; fixed timestep: 0.05 s

## Actor mapping

| Actor | Role | CARLA blueprint | Spawn transform | Decision |
|---|---|---|---|---|
| ego | vehicle | explicit versioned blueprint: | | supported/blocked |
| target-1 | vehicle | explicit versioned blueprint: | | supported/blocked |

## Evidence checklist

- [ ] versions, launch, world and original settings captured
- [ ] synchronous fixed timestep confirmed
- [ ] direct open-loop transforms applied per tick
- [ ] tick/time/actor/transform/velocity trace saved
- [ ] logs, exit/timeout, completion, normalized trace saved
- [ ] actors destroyed in finally and settings restored
- [ ] cleanup tested after success and forced failure
- [ ] three consecutive runs completed

- Startup/runtime/cleanup:
- Trace samples / actors / final time:
- Visual artifact:
- Limitation:
- Decision: PROCEED / DEFER / REJECT

## Standalone runner

After the preflight passes, run:

```bash
python3 scripts/m5b_carla_spike.py scenarios/nuscenes/scene-0061.json \
  --output reports/m5b-carla-scene-0061
```

The runner requires a CARLA client matching the running server. It loads one
built-in world, enables synchronous `0.05 s` ticks, replays the ego and one
vehicle with direct transforms, writes `trace.jsonl` and `manifest.json`, then
destroys actors and restores world settings.
