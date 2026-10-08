# R2S-203 OpenSCENARIO Baseline Export Evidence

`build_openscenario_xml()` exports a selected `local_road_aligned` scenario to
deterministic OpenSCENARIO 1.1 XML. It supports an ego vehicle plus one to three
non-ego actors. Each entity has a stable canonical actor ID, explicit initial
state, and a relative-time polyline trajectory in SI units. The trajectory is
started by the replay event, so its vertex timing is relative to event start.

The XML references the selected package-relative OpenDRIVE template path, so it
does not contain machine-specific paths. `write_openscenario()` is the explicit
filesystem boundary for writing the `.xosc` artifact.

`tests/test_exporter.py` parses the XML, checks deterministic output, entity and
trajectory timing, package-relative map reference, file writing, and actor-count
rejection.
