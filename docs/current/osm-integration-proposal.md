# OSM Integration Proposal

Status: `PROPOSAL`  
Default pipeline impact: `NONE`  
Canonical map source: nuScenes vector map

## Intended Role

OpenStreetMap would be an auxiliary geographic reference, alignment and
visualization layer. It would not replace the nuScenes vector map for CP1 and
would not automatically become the CARLA map for CP2.

```text
nuScenes vector map -> canonical CP1 OpenDRIVE source
OSM -> optional alignment/reference layer
nuScenes annotations -> dynamic actors
nuScenes sensors -> optional visual QA layer
```

## Proposed Pipeline

```text
nuScenes map frame
  -> identify shared landmarks
  -> project OSM into a local metric CRS
  -> estimate rigid SE(2) transform
  -> calculate residuals
  -> write local/private alignment manifest
  -> render QA overlay
```

The alignment manifest must record source/target frames, CRS, control points,
transform version, residual p50/p95/max, source dates and visibility. Never
guess latitude/longitude from nuScenes x/y without control-point evidence.

## Modes

- `osm_alignment_reference`: QA only; does not replace CP1.
- `osm_visualization_layer`: OSM plus lanes, actors and optional point cloud.
- `osm_carla_feasibility_fixture`: technical CARLA smoke only.
- `nuscenes_opendrive`: canonical Plan A mode.

## Guardrails

- Do not snap trajectories silently to OSM roads.
- Do not use OSM to hide road-match failures.
- Do not call an OSM-derived CARLA world nuScenes map fidelity.
- Review OSM attribution/license separately from nuScenes terms.
- Keep OSM-derived maps and overlays local/private until approved.

## Activation Criteria

OSM work may be activated only after a separate decision records the extract,
CRS, alignment residual tolerance, attribution status and intended mode.
