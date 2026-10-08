# R2S-202 OpenDRIVE Template Registry Evidence

The initial registry supports only `straight_road`, represented by the versioned
`straight-two-lane` OpenDRIVE template. It is a local road-aligned replay
approximation, not a conversion of a nuScenes map.

`select_opendrive_template()` requires a `local_road_aligned` scenario and an
explicit topology. It rejects unsupported topology rather than silently
selecting a substitute map. Selection records the template ID, version,
topology, reason, registry version, and `local-template-approximation` mode in
scenario provenance.

`tests/test_templates.py` verifies selection, the installed XML template,
recorded provenance, unsupported-topology rejection, and source-frame rejection.
