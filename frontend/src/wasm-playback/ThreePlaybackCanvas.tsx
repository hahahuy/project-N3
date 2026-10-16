import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { WasmFrame, WasmRoadGeometry } from "./types";

type Props = { road: WasmRoadGeometry; frame: WasmFrame };
type FocusAnimation = { position: THREE.Vector3; target: THREE.Vector3; progress: number; fromPosition: THREE.Vector3; fromTarget: THREE.Vector3 };

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

export default function ThreePlaybackCanvas({ road, frame }: Props) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const actorsRef = useRef<Map<number, THREE.Mesh>>(new Map());
  const animationRef = useRef<FocusAnimation | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#101821");
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 5000);
    camera.position.copy(DEFAULT_POSITION);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    host.appendChild(renderer.domElement);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.copy(DEFAULT_TARGET);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    scene.add(new THREE.HemisphereLight(0xddeeff, 0x18242b, 2));
    scene.add(new THREE.GridHelper(200, 40, 0x48606d, 0x263842));
    sceneRef.current = scene;
    cameraRef.current = camera;
    controlsRef.current = controls;
    rendererRef.current = renderer;

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const onPointerDown = (event: PointerEvent) => {
      const bounds = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1;
      pointer.y = -((event.clientY - bounds.top) / bounds.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects(Array.from(actorsRef.current.values()), false)[0];
      if (!hit) { setSelectedId(null); return; }
      const id = Number(hit.object.userData.objectId);
      const actor = hit.object as THREE.Mesh;
      const target = actor.position.clone();
      const offset = new THREE.Vector3(8, 6, 10);
      animationRef.current = { position: target.clone().add(offset), target, progress: 0, fromPosition: camera.position.clone(), fromTarget: controls.target.clone() };
      setSelectedId(id);
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
    let animationFrame = 0;
    const render = () => {
      const focus = animationRef.current;
      if (focus) {
        focus.progress = Math.min(1, focus.progress + 0.08);
        const eased = 1 - Math.pow(1 - focus.progress, 3);
        camera.position.lerpVectors(focus.fromPosition, focus.position, eased);
        controls.target.lerpVectors(focus.fromTarget, focus.target, eased);
        if (focus.progress >= 1) animationRef.current = null;
      }
      controls.update();
      renderer.render(scene, camera);
      animationFrame = requestAnimationFrame(render);
    };
    render();

    return () => {
      cancelAnimationFrame(animationFrame);
      observer.disconnect();
      renderer.domElement.removeEventListener("pointerdown", onPointerDown);
      controls.dispose();
      renderer.dispose();
      host.removeChild(renderer.domElement);
      sceneRef.current = null;
      cameraRef.current = null;
      controlsRef.current = null;
      rendererRef.current = null;
    };
  }, []);

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;
    scene.children.filter((child) => child.userData.wasmRoad).forEach((child) => scene.remove(child));
    for (const surface of road.lane_surfaces) {
      for (const boundary of [surface.left_boundary, surface.right_boundary]) {
        const geometry = new THREE.BufferGeometry().setFromPoints(boundary.map(pointVector));
        const line = new THREE.Line(geometry, new THREE.LineBasicMaterial({ color: 0x7999a7 }));
        line.userData.wasmRoad = true;
        scene.add(line);
      }
    }
  }, [road]);

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;
    const liveIds = new Set(frame.object_states.map((object) => object.id));
    for (const [id, mesh] of actorsRef.current) {
      if (!liveIds.has(id)) { scene.remove(mesh); mesh.geometry.dispose(); (mesh.material as THREE.Material).dispose(); actorsRef.current.delete(id); }
    }
    for (const object of frame.object_states) {
      let mesh = actorsRef.current.get(object.id);
      if (!mesh) {
        mesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshStandardMaterial({ color: 0xe6b85c }));
        mesh.userData.objectId = object.id;
        actorsRef.current.set(object.id, mesh);
        scene.add(mesh);
      }
      mesh.position.copy(pointVector(object));
      mesh.scale.set(Math.max(object.width, 1), Math.max(object.height, 1), Math.max(object.length, 2));
      mesh.rotation.y = -object.h;
      (mesh.material as THREE.MeshStandardMaterial).color.set(object.id === selectedId ? 0x7dd3fc : 0xe6b85c);
    }
  }, [frame, selectedId]);

  const resetView = () => {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!camera || !controls) return;
    animationRef.current = { position: DEFAULT_POSITION.clone(), target: roadCenter(road), progress: 0, fromPosition: camera.position.clone(), fromTarget: controls.target.clone() };
    setSelectedId(null);
  };

  return <div className="three-playback-shell">
    <div ref={hostRef} className="three-playback-canvas" role="img" aria-label={`3D WASM playback at ${frame.simulation_time.toFixed(2)} seconds`} />
    <div className="three-playback-overlay"><button type="button" onClick={resetView}>Reset View</button><span>{selectedId === null ? "Click a vehicle to focus" : `Selected vehicle ${selectedId}`}</span><span>Orbit / zoom enabled</span></div>
  </div>;
}
