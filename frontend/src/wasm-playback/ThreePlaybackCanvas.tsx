import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { WasmFrame, WasmGround, WasmLidarCloud, WasmRecordedPath, WasmRoadGeometry, WasmOrbitState } from "./types";
import type { RecordedAnnotationTrack } from "../api";
import { actorKindOf, renderVehicleYaw } from "./types";
import { OrbitRuntime } from "./orbit-runtime";

type Props = {
  road: WasmRoadGeometry;
  frame: WasmFrame;
  ground: WasmGround | null;
  showCuboids: boolean;
  paths: WasmRecordedPath[] | null;
  lidar: WasmLidarCloud | null;
  recordedTracks?: RecordedAnnotationTrack[];
  orbit?: WasmOrbitState;
  onOrbitChange?: (orbit: WasmOrbitState) => void;
  showResetView?: boolean;
  focusActorId?: string | null;
  vehicleTint?: number;
  vehicleTints?: Record<string, number>;
  /** Reports the actor picked on the canvas so the workspace can select it. */
  onActorPick?: (actorId: string | null) => void;
};

const GROUND_STYLE: Record<string, { color: number; lift: number }> = {
  drivable_area: { color: 0x232d36, lift: 0.01 },
  walkway: { color: 0x3d4854, lift: 0.012 },
  ped_crossing: { color: 0x8a94a0, lift: 0.014 },
  carpark_area: { color: 0x2f3330, lift: 0.011 },
};
type FocusAnimation = { position: THREE.Vector3; target: THREE.Vector3; progress: number; fromPosition: THREE.Vector3; fromTarget: THREE.Vector3 };

/** Render lift of the drawn asphalt above the recorded surface (z-fighting
 *  guard vs grid/ground). Actor feet rest on this drawn surface, not at the
 *  raw engine z — otherwise the ground fills slice through the cuboids. */
const ROAD_LIFT = 0.02;

const DEFAULT_POSITION = new THREE.Vector3(20, 22, 26);
const DEFAULT_TARGET = new THREE.Vector3(0, 0, 0);

function pointVector(point: { x: number; y: number; z: number }): THREE.Vector3 {
  return new THREE.Vector3(point.x, point.z, -point.y);
}

function roadCenter(road: WasmRoadGeometry): THREE.Vector3 {
  const surfaces = arrayItems<{ left_boundary: Array<{ x: number; y: number; z: number }>; right_boundary: Array<{ x: number; y: number; z: number }> }>(road.lane_surfaces);
  const points = surfaces.flatMap((surface) => [...Array.from(surface.left_boundary), ...Array.from(surface.right_boundary)]);
  if (!points.length) return DEFAULT_TARGET.clone();
  const center = points.reduce<THREE.Vector3>((result, point) => result.add(pointVector(point)), new THREE.Vector3());
  return center.multiplyScalar(1 / points.length);
}

function arrayItems<T>(value: unknown): T[] {
  if (Array.isArray(value)) return value as T[];
  if (value && typeof value === "object" && "size" in value && "get" in value && typeof value.size === "function" && typeof value.get === "function") {
    const vector = value as { size(): number; get(index: number): T };
    return Array.from({ length: vector.size() }, (_, index) => vector.get(index));
  }
  return [];
}

const ACTOR_COLORS = {
  vehicle: 0xe6b85c,
  pedestrian: 0x6fbf8f,
  misc: 0xb39ddb,
  unknown: 0x9fb4c7,
  selected: 0x7dd3fc,
} as const;

const DARK_PART_COLOR = 0x1c2126;

/** Display color for a RECORDED actor_type label (data, not invented
 *  taxonomy — mirrors the engine-kind palette so the two agree). */
function recordedPathColor(actorType: string): number {
  const label = actorType.toLowerCase();
  if (label.includes("ego")) return ACTOR_COLORS.vehicle;
  if (label.includes("pedestrian") || label.includes("human")) return ACTOR_COLORS.pedestrian;
  if (label.includes("cone") || label.includes("barrier") || label.includes("misc")) return ACTOR_COLORS.misc;
  if (label.includes("vehicle") || label.includes("car") || label.includes("truck") || label.includes("moto") || label.includes("bike") || label.includes("bus")) return ACTOR_COLORS.vehicle;
  return ACTOR_COLORS.unknown;
}

export default function ThreePlaybackCanvas({ road, frame, ground, showCuboids, paths, lidar, recordedTracks = [], orbit, onOrbitChange, showResetView = false, focusActorId = null, vehicleTint, vehicleTints, onActorPick }: Props) {
  const orbitRuntimeRef = useRef<OrbitRuntime | null>(null);
  if (!orbitRuntimeRef.current) orbitRuntimeRef.current = new OrbitRuntime(orbit ?? { position: [20, 22, 26], target: [0, 0, 0] });
  const hostRef = useRef<HTMLDivElement | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const actorsRef = useRef<Map<number, THREE.Group>>(new Map());
  const cuboidsRef = useRef<Map<number, THREE.LineSegments>>(new Map());
  const cuboidEdgesRef = useRef<THREE.EdgesGeometry | null>(null);
  const followRef = useRef<THREE.Vector3 | null>(null);
  const animationRef = useRef<FocusAnimation | null>(null);
  const interactionOrbitRef = useRef<WasmOrbitState | null>(null);
  const visibleRef = useRef(true);
  const renderRef = useRef<(() => void) | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const recordedMeshRef = useRef<THREE.InstancedMesh | null>(null);

function actorColor(object: { object_type: number; name: string }, selected: boolean, tint?: number, tints?: Record<string, number>): number {
  if (selected) return ACTOR_COLORS.selected;
  if (tints?.[object.name] !== undefined && actorKindOf(object) === "vehicle") return tints[object.name];
  if (actorKindOf(object) === "misc") return 0xff5c7a;
  if (tint !== undefined && actorKindOf(object) === "vehicle") return tint;
  return ACTOR_COLORS[actorKindOf(object)];
}

/** Procedural schematic skins in unit space ([-0.5, 0.5]^3, y up, z forward).
 *  The caller scales the group to the exact recorded cuboid, so silhouettes
 *  stay proportional while footprints never lie. Shapes are illustrative, not
 *  measured: a box that looks like a car is still only a cuboid underneath. */
function makeActorGroup(object: { object_type: number }, selected: boolean): THREE.Group {
  const kind = actorKindOf(object);
  const color = selected ? ACTOR_COLORS.selected : ACTOR_COLORS[kind];
  const group = new THREE.Group();
  const paint = (geometry: THREE.BufferGeometry, tint: number = color): THREE.Mesh => {
    const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({ color: tint }));
    group.add(mesh);
    return mesh;
  };
  if (kind === "vehicle") {
    const body = paint(new THREE.BoxGeometry(0.9, 0.45, 1.0));
    body.position.y = -0.275;
    const cabin = paint(new THREE.BoxGeometry(0.7, 0.35, 0.55));
    cabin.position.set(0, 0.125, -0.05);
    const wheelGeometry = new THREE.CylinderGeometry(0.16, 0.16, 0.12, 12);
    for (const [x, z] of [[-0.42, -0.32], [0.42, -0.32], [-0.42, 0.32], [0.42, 0.32]] as const) {
      const wheel = new THREE.Mesh(wheelGeometry, new THREE.MeshStandardMaterial({ color: DARK_PART_COLOR }));
      wheel.rotation.z = Math.PI / 2;
      wheel.position.set(x, -0.34, z);
      group.add(wheel);
    }
  } else if (kind === "pedestrian") {
    const torso = paint(new THREE.CylinderGeometry(0.22, 0.26, 0.62, 10));
    torso.position.y = -0.19;
    const head = paint(new THREE.SphereGeometry(0.16, 12, 10));
    head.position.y = 0.34;
  } else if (kind === "misc") {
    const cone = paint(new THREE.ConeGeometry(0.35, 0.9, 12));
    cone.position.y = -0.05;
    const foot = paint(new THREE.BoxGeometry(0.7, 0.1, 0.7));
    foot.position.y = -0.45;
  } else {
    paint(new THREE.BoxGeometry(1, 1, 1));
  }
  return group;
}

function tintGroup(group: THREE.Group, color: number): void {
  group.traverse((node) => {
    const mesh = node as THREE.Mesh;
    if (!mesh.isMesh) return;
    (mesh.material as THREE.MeshStandardMaterial).color.set(color);
  });
}

function disposeObject(root: THREE.Object3D): void {
  root.traverse((node) => {
    const mesh = node as THREE.Mesh;
    if (mesh.geometry) mesh.geometry.dispose();
    const material = mesh.material as THREE.Material | THREE.Material[] | undefined;
    if (Array.isArray(material)) material.forEach((item) => item.dispose());
    else if (material) material.dispose();
  });
}

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#101821");
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 5000);
    camera.position.fromArray(orbit?.position ?? (DEFAULT_POSITION.toArray() as [number, number, number]));
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    host.appendChild(renderer.domElement);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.fromArray(orbit?.target ?? (DEFAULT_TARGET.toArray() as [number, number, number]));
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    scene.add(new THREE.HemisphereLight(0xddeeff, 0x18242b, 2));
    scene.add(new THREE.GridHelper(200, 40, 0x48606d, 0x263842));
    sceneRef.current = scene;
    cameraRef.current = camera;
    controlsRef.current = controls;
    rendererRef.current = renderer;
    const captureOrbit = () => {
      const next = { position: camera.position.toArray() as [number, number, number], target: controls.target.toArray() as [number, number, number] };
      interactionOrbitRef.current = next;
      orbitRuntimeRef.current?.update(next);
    };
    const persistOrbit = () => {
      const next = interactionOrbitRef.current;
      if (next && orbitRuntimeRef.current?.getRevision() !== undefined) onOrbitChange?.(next);
      interactionOrbitRef.current = null;
    };
    controls.addEventListener("change", captureOrbit);
    controls.addEventListener("end", persistOrbit);

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const onPointerDown = (event: PointerEvent) => {
      const bounds = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1;
      pointer.y = -((event.clientY - bounds.top) / bounds.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects([...Array.from(actorsRef.current.values()), ...Array.from(cuboidsRef.current.values())], true)[0];
      let node: THREE.Object3D | null = hit?.object ?? null;
      while (node && node.userData.objectId === undefined) node = node.parent;
      if (!node) { setSelectedId(null); onActorPick?.(null); return; }
      const id = Number((node as THREE.Group).userData.objectId);
      const target = (node as THREE.Group).position.clone();
      const offset = new THREE.Vector3(8, 6, 10);
      animationRef.current = { position: target.clone().add(offset), target, progress: 0, fromPosition: camera.position.clone(), fromTarget: controls.target.clone() };
      setSelectedId(id);
      onActorPick?.(String(node.userData.actorName ?? ""));
    };
    renderer.domElement.addEventListener("pointerdown", onPointerDown);

    const resize = () => {
      const width = host.clientWidth;
      const height = Math.max(host.clientHeight, 280);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(host);
    const visibilityObserver = new IntersectionObserver(([entry]) => {
      visibleRef.current = entry.isIntersecting;
      if (visibleRef.current) renderRef.current?.();
    }, { threshold: 0.01 });
    visibilityObserver.observe(host);
    let animationFrame = 0;
    const render = () => {
      if (!visibleRef.current) { animationFrame = 0; return; }
      const focus = animationRef.current;
      if (focus) {
        focus.progress = Math.min(1, focus.progress + 0.08);
        const eased = 1 - Math.pow(1 - focus.progress, 3);
        camera.position.lerpVectors(focus.fromPosition, focus.position, eased);
        controls.target.lerpVectors(focus.fromTarget, focus.target, eased);
        if (focus.progress >= 1) {
          animationRef.current = null;
           const next = { position: camera.position.toArray() as [number, number, number], target: controls.target.toArray() as [number, number, number] };
           orbitRuntimeRef.current?.update(next);
           onOrbitChange?.(next);
        }
      }
      controls.update();
      renderer.render(scene, camera);
      animationFrame = requestAnimationFrame(render);
    };
    renderRef.current = render;
    render();

    return () => {
      persistOrbit();
      cancelAnimationFrame(animationFrame);
      controls.removeEventListener("change", captureOrbit);
      controls.removeEventListener("end", persistOrbit);
      observer.disconnect();
      visibilityObserver.disconnect();
      renderer.domElement.removeEventListener("pointerdown", onPointerDown);
      controls.dispose();
      renderer.dispose();
      if (recordedMeshRef.current) {
        recordedMeshRef.current.geometry.dispose();
        (recordedMeshRef.current.material as THREE.Material).dispose();
      }
      host.removeChild(renderer.domElement);
      sceneRef.current = null;
      cameraRef.current = null;
      controlsRef.current = null;
      rendererRef.current = null;
      renderRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!orbit || animationRef.current || !cameraRef.current || !controlsRef.current) return;
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    const samePosition = camera.position.toArray().every((value, index) => Math.abs(value - orbit.position[index]) < 1e-4);
    const sameTarget = controls.target.toArray().every((value, index) => Math.abs(value - orbit.target[index]) < 1e-4);
    if (samePosition && sameTarget) return;
    camera.position.fromArray(orbit.position);
    controls.target.fromArray(orbit.target);
    controls.update();
  }, [orbit]);

  useEffect(() => {
    if (!focusActorId) return;
    const actor = [...actorsRef.current.values()].find((item) => String(item.userData.actorName).toLowerCase() === focusActorId.toLowerCase());
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!actor || !camera || !controls) return;
    const target = actor.position.clone();
    animationRef.current = { position: target.clone().add(new THREE.Vector3(8, 6, 10)), target, progress: 0, fromPosition: camera.position.clone(), fromTarget: controls.target.clone() };
    setSelectedId(Number(actor.userData.objectId));
    followRef.current = target.clone();
  }, [focusActorId]);

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;
    scene.children
      .filter((child) => child.userData.wasmRoad)
      .forEach((child) => {
        scene.remove(child);
        disposeObject(child);
      });
    // Asphalt ribbons: one merged mesh for all recorded lane surfaces.
    // Only recorded boundaries are drawn — no invented markings or shoulders.
    const positions: number[] = [];
    const indices: number[] = [];
    let base = 0;
    for (const surface of road.lane_surfaces) {
      const left = surface.left_boundary.map(pointVector);
      const right = surface.right_boundary.map(pointVector);
      const count = Math.min(left.length, right.length);
      for (let index = 0; index < count; index++) {
        positions.push(left[index].x, left[index].y, left[index].z, right[index].x, right[index].y, right[index].z);
      }
      for (let index = 0; index < count - 1; index++) {
        const anchor = base + index * 2;
        indices.push(anchor, anchor + 1, anchor + 2, anchor + 1, anchor + 3, anchor + 2);
      }
      base += count * 2;
    }
    if (positions.length > 0) {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
      geometry.setIndex(indices);
      geometry.computeVertexNormals();
      const asphalt = new THREE.Mesh(
        geometry,
        new THREE.MeshStandardMaterial({ color: 0x2a3540, roughness: 1, metalness: 0, side: THREE.DoubleSide }),
      );
      asphalt.position.y = ROAD_LIFT;
      asphalt.userData.wasmRoad = true;
      scene.add(asphalt);
    }
    // Recorded lane edges + road marks as merged line segments (previously
    // fetched but never drawn). Marks exist only where the source provides
    // them — builder maps legitimately show unmarked asphalt.
    const edgePairs: THREE.Vector3[] = [];
    const pushStrip = (points: THREE.Vector3[], lift: number) => {
      for (let index = 0; index + 1 < points.length; index++) {
        edgePairs.push(
          new THREE.Vector3(points[index].x, points[index].y + lift, points[index].z),
          new THREE.Vector3(points[index + 1].x, points[index + 1].y + lift, points[index + 1].z),
        );
      }
    };
    for (const surface of road.lane_surfaces) {
      pushStrip(surface.left_boundary.map(pointVector), 0.03);
      pushStrip(surface.right_boundary.map(pointVector), 0.03);
    }
    const markPairs: THREE.Vector3[] = [];
    for (const mark of road.road_marks) {
      const points = mark.points.map(pointVector);
      for (let index = 0; index + 1 < points.length; index++) {
        markPairs.push(
          new THREE.Vector3(points[index].x, points[index].y + 0.05, points[index].z),
          new THREE.Vector3(points[index + 1].x, points[index + 1].y + 0.05, points[index + 1].z),
        );
      }
    }
    const addSegments = (pairs: THREE.Vector3[], color: number) => {
      if (pairs.length === 0) return;
      const geometry = new THREE.BufferGeometry().setFromPoints(pairs);
      const lines = new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color }));
      lines.userData.wasmRoad = true;
      scene.add(lines);
    };
    addSegments(edgePairs, 0x7999a7);
    addSegments(markPairs, 0xd8d3c3);
    // Survey ground context under the lane ribbons. Polygons arrive in the
    // scenario local frame; ShapeGeometry triangulates them (holes included)
    // and one rotation lays them flat matching pointVector. A bad polygon is
    // skipped loudly (console) rather than killing the whole scene.
    for (const layer of ground?.layers ?? []) {
      const style = GROUND_STYLE[layer.name] ?? { color: 0x2a3540, lift: 0.011 };
      for (const polygon of layer.polygons) {
        try {
          if (polygon.exterior.length < 3) continue;
          const shape = new THREE.Shape(polygon.exterior.map(([x, y]) => new THREE.Vector2(x, y)));
          for (const ring of polygon.holes) {
            if (ring.length < 3) continue;
            shape.holes.push(new THREE.Path(ring.map(([x, y]) => new THREE.Vector2(x, y))));
          }
          const mesh = new THREE.Mesh(
            new THREE.ShapeGeometry(shape),
            new THREE.MeshStandardMaterial({ color: style.color, roughness: 1, metalness: 0, side: THREE.DoubleSide }),
          );
          mesh.rotation.x = -Math.PI / 2;
          mesh.position.y = style.lift;
          mesh.userData.wasmRoad = true;
          scene.add(mesh);
        } catch (error) {
          console.warn("Skipping invalid ground polygon", layer.name, error);
        }
      }
    }
  }, [road, ground]);

  // Recorded overlays (travel paths + heading glyphs + lidar sweep). The
  // parent passes null unless the checkbox is on, so this stays dumb:
  // render what arrives, all in the scenario local frame.
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;
    const old = scene.getObjectByName("wasm-overlay");
    if (old) {
      scene.remove(old);
      old.traverse((node) => {
        const mesh = node as THREE.Mesh | THREE.Points | THREE.Line;
        if (mesh.geometry) mesh.geometry.dispose();
        const material = mesh.material as THREE.Material | undefined;
        if (material) material.dispose();
      });
    }
    if ((!paths || paths.length === 0) && !lidar) return;
    const overlay = new THREE.Group();
    overlay.name = "wasm-overlay";
    const PATH_LIFT = ROAD_LIFT + 0.04;
    if (paths) {
      const up = new THREE.Vector3(0, 1, 0);
      const coneGeometry = new THREE.ConeGeometry(0.35, 1.0, 8);
      for (const path of paths) {
        if (path.points.length < 2) continue;
        const color = path.role === "origin" ? 0x8395a1 : recordedPathColor(path.actor_type);
        const material = path.role === "origin"
          ? new THREE.LineDashedMaterial({ color, dashSize: 0.6, gapSize: 0.35, transparent: true, opacity: 0.75 })
          : new THREE.LineBasicMaterial({ color });
        const line = new THREE.Line(
          new THREE.BufferGeometry().setFromPoints(path.points.map((point) => new THREE.Vector3(point.x_m, PATH_LIFT, -point.y_m))),
          material,
        );
        if (path.role === "origin") line.computeLineDistances();
        overlay.add(line);
        const stride = Math.max(1, Math.floor((path.points.length - 1) / 8));
        for (let index = 0; index + 1 < path.points.length; index += stride) {
          const a = path.points[index];
          const b = path.points[index + 1];
          const dir = new THREE.Vector3(b.x_m - a.x_m, 0, -(b.y_m - a.y_m));
          if (dir.lengthSq() < 1e-9) continue;
          const cone = new THREE.Mesh(coneGeometry, new THREE.MeshBasicMaterial({ color }));
          cone.quaternion.setFromUnitVectors(up, dir.normalize());
          cone.position.set(a.x_m, PATH_LIFT + 0.2, -a.y_m);
          overlay.add(cone);
        }
      }
    }
    if (lidar && lidar.point_count > 0) {
      // Buffer is pre-mapped to the render frame (x, z, -y) at decode time.
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(lidar.xyz, 3));
      overlay.add(new THREE.Points(
        geometry,
        new THREE.PointsMaterial({ color: 0x8fd3ff, size: 0.18, sizeAttenuation: true, transparent: true, opacity: 0.9 }),
      ));
    }
    scene.add(overlay);
  }, [paths, lidar]);

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;
    if (!recordedMeshRef.current || recordedTracks.length > recordedMeshRef.current.count) {
      const previous = recordedMeshRef.current;
      const capacity = Math.max(512, Math.pow(2, Math.ceil(Math.log2(Math.max(1, recordedTracks.length)))));
      const mesh = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshBasicMaterial({ color: 0xd9a441, transparent: true, opacity: 0.35, wireframe: true }), capacity);
      mesh.userData.recordedAnnotationLayer = true;
      if (previous) { scene.remove(previous); previous.geometry.dispose(); (previous.material as THREE.Material).dispose(); }
      recordedMeshRef.current = mesh;
      scene.add(mesh);
    }
    const mesh = recordedMeshRef.current;
    const matrix = new THREE.Matrix4();
    const quaternion = new THREE.Quaternion();
    const scale = new THREE.Vector3();
    let active = 0;
    for (const track of recordedTracks) {
      const eligible = track.states.filter((item) => item.time_s <= frame.simulation_time);
      const state = eligible[eligible.length - 1];
      if (!state || frame.simulation_time > track.states[track.states.length - 1].time_s || active >= mesh.count || !state.center_local || !state.yaw_local_rad) continue;
      const [x, y] = state.center_local;
      const [width, length, height] = state.size_m;
      quaternion.setFromAxisAngle(new THREE.Vector3(0, 1, 0), renderVehicleYaw(state.yaw_local_rad));
      scale.set(width, height, length);
      matrix.compose(new THREE.Vector3(x, height / 2 + ROAD_LIFT, -y), quaternion, scale);
      mesh.setMatrixAt(active, matrix);
      active += 1;
    }
    for (let index = active; index < mesh.count; index += 1) {
      matrix.makeScale(0, 0, 0);
      mesh.setMatrixAt(index, matrix);
    }
    mesh.instanceMatrix.needsUpdate = true;
  }, [recordedTracks, frame.simulation_time]);

  // A new selection anchors the follow lock without a camera jump; the
  // click animation still plays once, then per-frame deltas take over.
  useEffect(() => {
    followRef.current = null;
  }, [selectedId]);

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;
    if (!cuboidEdgesRef.current) cuboidEdgesRef.current = new THREE.EdgesGeometry(new THREE.BoxGeometry(1, 1, 1));
    const liveIds = new Set(frame.object_states.map((object) => object.id));
    for (const [id, group] of actorsRef.current) {
      if (!liveIds.has(id)) { scene.remove(group); disposeObject(group); actorsRef.current.delete(id); }
    }
    for (const [id, cuboid] of cuboidsRef.current) {
      if (!liveIds.has(id)) {
        scene.remove(cuboid);
        (cuboid.material as THREE.Material).dispose();
        cuboidsRef.current.delete(id);
      }
    }
    for (const object of frame.object_states) {
      let group = actorsRef.current.get(object.id);
      if (!group) {
        group = makeActorGroup(object, object.id === selectedId);
        group.userData.objectId = object.id;
        group.userData.actorName = object.name;
        actorsRef.current.set(object.id, group);
        scene.add(group);
      }
      group.position.copy(pointVector(object));
      // Feet on the drawn road: skins span unit y [-0.5, 0.5] and the group
      // scales by the exact recorded height, so the origin sits half a cuboid
      // under the contact patch. The engine reports surface z; without this
      // lift actors render centered at h=0 with wheels sunk under the fills.
      const halfHeight = Number.isFinite(object.height) && object.height > 0 ? object.height / 2 : 0;
      group.position.y += halfHeight + ROAD_LIFT;
      // Exact recorded cuboid: the engine reports the XOSC BoundingBox dims,
      // which the exporter fills with recorded annotation sizes (or documented
      // fallbacks), so the unit-space skin scales through unclamped. Owner
      // order 2026-10-16: what you see must be what the data says.
      group.scale.set(object.width, object.height, object.length);
       group.rotation.y = renderVehicleYaw(object.h);
      group.visible = !showCuboids;
      tintGroup(group, actorColor(object, object.id === selectedId, vehicleTint, vehicleTints));
      // Exact-cuboid overlay: unit wireframe scaled to the recorded dims,
      // centered on the data cuboid (group origin minus the asphalt lift).
      const dimsFinite = [object.width, object.height, object.length].every((dim) => Number.isFinite(dim) && (dim as number) > 0);
      let cuboid = cuboidsRef.current.get(object.id);
      if (dimsFinite && !cuboid) {
        cuboid = new THREE.LineSegments(cuboidEdgesRef.current, new THREE.LineBasicMaterial({ color: actorColor(object, object.id === selectedId, vehicleTint, vehicleTints) }));
        cuboid.userData.objectId = object.id;
        cuboidsRef.current.set(object.id, cuboid);
        scene.add(cuboid);
      }
      if (cuboid) {
        cuboid.position.set(group.position.x, group.position.y - ROAD_LIFT, group.position.z);
         cuboid.rotation.y = group.rotation.y;
        cuboid.scale.set(object.width, object.height, object.length);
        (cuboid.material as THREE.LineBasicMaterial).color.set(actorColor(object, object.id === selectedId, vehicleTint, vehicleTints));
        cuboid.visible = showCuboids && dimsFinite;
      }
    }
    // Selection lock: the orbit follows the actor through time. The camera
    // keeps its user-controlled offset; only the delta is applied, so orbiting
    // or zooming while locked keeps working and deselect stops the follow.
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (camera && controls && selectedId !== null) {
      const followed = actorsRef.current.get(selectedId);
      if (followed) {
        if (!followRef.current) {
          followRef.current = followed.position.clone();
        } else {
          const delta = followed.position.clone().sub(followRef.current);
          if (delta.lengthSq() > 0) {
            camera.position.add(delta);
            controls.target.add(delta);
            followRef.current.copy(followed.position);
          }
        }
      }
    }
  }, [frame, selectedId, showCuboids]);

  const resetView = () => {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!camera || !controls) return;
    const ego = [...actorsRef.current.values()].find((actor) => String(actor.userData.actorName ?? "").toLowerCase() === "ego");
    const target = ego?.position.clone() ?? roadCenter(road);
    animationRef.current = { position: target.clone().add(new THREE.Vector3(8, 6, 10)), target, progress: 0, fromPosition: camera.position.clone(), fromTarget: controls.target.clone() };
    setSelectedId(ego?.userData.objectId === undefined ? null : Number(ego.userData.objectId));
    followRef.current = target.clone();
  };

  return <div className="three-playback-shell">
    <div ref={hostRef} className="three-playback-canvas" role="img" aria-label={`3D WASM playback at ${frame.simulation_time.toFixed(2)} seconds`} />
    <div className="three-playback-overlay">{showResetView && <button type="button" onClick={resetView}>Reset View</button>}<span>{selectedId === null ? "Click an actor to focus" : `Following actor ${selectedId} · click empty space to release`}</span><span>Orbit / zoom enabled</span></div>
  </div>;
}
