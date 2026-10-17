import type { IconName } from "./icons";

export type ViewRenderer = "top-down" | "sensor-evidence" | "lidar" | "pov" | "real-camera";

export type ViewDescriptor = {
  type: string;
  label: string;
  icon: IconName;
  renderer: ViewRenderer;
  menuDescription: string;
  supportsNativeSession: boolean;
  replayOnly?: boolean;
};

export const VIEW_REGISTRY = {
  mainView: "third-person",
  maxViews: 3,
  descriptors: [
    { type: "top-down", label: "Top-down", icon: "top-down", renderer: "top-down", menuDescription: "nuScenes devkit map and point cloud", supportsNativeSession: false },
    { type: "sensor-evidence", label: "Sensor Evidence", icon: "sensor-evidence", renderer: "sensor-evidence", menuDescription: "nuScenes LIDAR_TOP recorded sweeps", supportsNativeSession: false, replayOnly: true },
    { type: "third-person", label: "3rd-person POV", icon: "third-person", renderer: "pov", menuDescription: "internal transform POV with optional esmini state/image", supportsNativeSession: true },
    { type: "in-car", label: "In-car POV", icon: "in-car", renderer: "pov", menuDescription: "ego-mounted internal transform POV with optional esmini state/image", supportsNativeSession: true },
    { type: "lidar", label: "LiDAR 3D", icon: "lidar", renderer: "lidar", menuDescription: "recorded LIDAR_TOP point cloud", supportsNativeSession: false },
    { type: "real-camera", label: "Real Camera", icon: "third-person", renderer: "real-camera", menuDescription: "recorded camera channel view", supportsNativeSession: false },
  ] satisfies readonly ViewDescriptor[],
} as const;

export type ViewType = (typeof VIEW_REGISTRY.descriptors)[number]["type"];
export const MAIN_VIEW: ViewType = VIEW_REGISTRY.mainView;
export const MAX_VIEWS = VIEW_REGISTRY.maxViews;

export function getViewDescriptor(type: ViewType): ViewDescriptor {
  const descriptor = VIEW_REGISTRY.descriptors.find((item) => item.type === type);
  if (!descriptor) throw new Error(`unknown_view_type:${type}`);
  return descriptor;
}
