# CP1 Topology Repair Evidence

## Scope

Repair dangling OpenDRIVE topology references without changing road IDs,
geometry mode, source map, width behavior or private artifact boundaries.

## Repair

- Ordinary lane roads now retain `junction="-1"`.
- Connector roads own emitted junction IDs.
- Predecessor/successor links are emitted only when their target road was
  actually emitted.
- Existing first-link and conservative connector semantics are unchanged.

## Synthetic Verification

```text
.venv/bin/python -m pytest -q
173 passed, 2 warnings
```

Tests now assert junction references and road links resolve to emitted IDs and
that unresolved map API link targets are omitted.

## Private External Before/After

Input map SHA-256 remained:

```text
17939122b940d7faff50fa7ff623ded7f739549a781c32dff1ecd1ac7bebca02
```

| Audit | Before | After |
|---|---:|---:|
| Roads | 2,002 | 2,002 |
| Geometry records | 12,061 | 12,061 |
| Junction groups | 1,065 | 1,065 |
| Road-length errors | 0 | 0 |
| Dangling junction refs | 936 | 0 |
| Dangling road links | 15 | 0 |
| esmini unresolved-junction warnings | 936 | 0 |
| esmini probe exit | 0 | 0 |

Repaired XODR SHA-256:

```text
091a00a767d2a97d483fde28eb85feade9f831ccabae213e0ac40ae3f5e51ca5
```

The generated XODR, probe XOSC, recording and logs remain under
`$LOCAL_EVIDENCE_ROOT_FINAL/repaired` and are not repository artifacts.

## Remaining Limits

- Junction graph semantics remain conservative; outgoing junction connections
  and lane-level topology are not fully modeled.
- The project validator remains a lightweight subset check, not XSD validation.
- CARLA map loading remains unverified.
- Polygon width remains an effective area/centerline proxy, not cross-section
  boundary reconstruction.
- Road-match and occupancy remain diagnostic/provisional.

No CP1 acceptance, CARLA, CP2 or same-XOSC claim is made.
