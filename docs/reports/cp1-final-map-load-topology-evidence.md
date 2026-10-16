> Historical pre-repair report. Superseded by `cp1-topology-repair-evidence.md`
> and the scene-local corridor evidence. Retained for audit history.

# CP1 Final Map-Load and Topology Evidence

## Scope

The current One-North builder was checked with XML parsing, the project subset
validator, an independent semantic audit, and a local esmini runtime probe.
Generated XODR, XOSC, recording and logs remain private under
`$LOCAL_EVIDENCE_ROOT_FINAL`.

## Results

- Map: `singapore-onenorth`, resolution `5.0 m`.
- Roads: `2,002`; geometry records: `12,061`.
- Unsupported geometry paths: `0`.
- Polygon width sources: `2,002`; junction groups: `1,065`.
- `xmllint --noout`: pass.
- Python XML parse and project subset validator: pass.
- Road-length/geometry consistency errors: `0`.
- Invalid lane widths: `0`.
- Dangling junction references: `936`.
- Dangling road links: `15`.
- esmini `v3.9.0`, build `6434`, loaded the generated XODR and exited `0`.
- esmini unresolved-junction warnings: `936`.

The runtime pass means esmini accepted and executed the probe. It does not mean
the map is semantically topology-correct. The warning count agrees with the
independent audit and blocks CP1 acceptance.

## Private Evidence

```text
$LOCAL_EVIDENCE_ROOT_FINAL/cp1-generated-xodr-semantic-audit.json
$LOCAL_EVIDENCE_ROOT_FINAL/esmini-probe/stdout.txt
$LOCAL_EVIDENCE_ROOT_FINAL/esmini-probe/stderr.txt
$LOCAL_EVIDENCE_ROOT_FINAL/esmini-probe/probe.dat
```

## Decision

Repair junction/reference/link semantics, then rerun the same audit and esmini
probe. The lightweight project subset validator must not be described as XSD
validation. No CP1 acceptance, CARLA, CP2 or same-XOSC claim is made.
