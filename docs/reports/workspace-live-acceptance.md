# Workspace Live Acceptance Evidence

Status: `RUNTIME-VERIFIED / LOCAL-PRIVATE / PROVISIONAL`

Environment: local `/mnt/backup/nuscenes` `v1.0-trainval` release with
`nuscenes-devkit==1.2.0`, local FastAPI and Vite development servers.

- Real `scene-0001` imported through the source-scene API.
- Workspace returned three real actors, time-indexed states and nine native map
  layer collections for the imported scenario.
- Native map capability and patch queries returned real devkit data with
  `source=nuscenes-devkit` and `artifact_visibility=local_private`.
- A real `LIDAR_TOP` keyframe returned an `application/octet-stream` payload
  with timestamp, calibration token, frame, decimation, counts and private
  visibility metadata.
- Browser smoke flow loaded the Workspace, selected the real scenario, rendered
  Top-down actor state data, opened constrained editing, added a third-person
  view and displayed its explicit simulator-unavailable reason. The no-dataset
  acceptance runtime also exercised Recipe, rollback/undo/redo, constrained
  Tier 1 fields, Compare, timeline/gate text equivalents, keyboard shortcuts
  and narrow-layout behavior through the frontend test suite.
- The incomplete-metadata environment is now fail-closed: `/api/settings`
  returns zero source scenes rather than a 500 when the configured release
  directory lacks `scene.json`. The real dataset runtime was kept separate from
  the no-dataset acceptance runtime.

This is private provisional runtime evidence, not CP1 acceptance evidence.
The live-session contract is also present in the local API, but this environment
has no configured compatible `esminiLib`; capability is therefore explicitly
`unavailable`. The browser's live renderer path is state-based and separate from
the internal transform preview and image artifacts, so no native live execution
claim is made here.
 Internal simulator frames now return timestamped third-person and ego-mounted
 in-car transform frames through `simulator-frame-v1`, and the browser binds
 those frames to the Workspace playhead. This is transform-backed rendering,
 not a static placeholder image. The LiDAR pane now fetches the private binary
 `LIDAR_TOP` payload, applies the API calibration and ego-pose transforms in its
 canvas projection, and exposes decimation, timestamp, frame, transform version
 and returned/total point counts. Decimated results are labelled partial where
 appropriate. No post-edit sensor frame is generated or claimed; variant views
 remain explicitly unavailable until the backend provides parent-sweep fallback
  status or real regenerated frames. esmini image-frame rendering is implemented
  behind a real private capture manifest and remains unavailable in this headless
  environment. CP1
 `20/143 = 13.99%`, metric roles, private artifact policy and CARLA same-XOSC
 boundaries are unchanged.
