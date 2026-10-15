import type { ReactElement } from "react";

const icons = {
  undo: <><path d="M3 8h7a3 3 0 1 1 0 6H7" /><path d="M6 5 3 8l3 3" /></>,
  redo: <><path d="M13 8H6a3 3 0 1 0 0 6h3" /><path d="M10 5l3 3-3 3" /></>,
  import: <><path d="M8 10.5V2.5" /><path d="m5 5.5 3-3 3 3" /><path d="M2.5 10.5V13a1 1 0 0 0 1 1h9a1 1 0 0 0 1-1v-2.5" /></>,
  export: <><path d="M8 10.5V2.5" /><path d="m5 5.5 3-3 3 3" /><path d="M2.6 10.5H2.5v2.5a1 1 0 0 0 1 1h9a1 1 0 0 0 1-1v-2.5h-.1" /></>,
  cursor: <><path d="M4 2.2 12.4 8 9 8.9 10.6 12.4 8.9 13.2 7.3 9.7 4 11.6z" /></>,
  edit: <><path d="M11.4 2.4 13.6 4.6 5.6 12.6 2.4 13.6 3.4 10.4z" /><path d="m9.4 4.4 2.2 2.2" /></>,
  behavior: <><circle cx="4" cy="4.5" r="1.6" /><circle cx="4" cy="11.5" r="1.6" /><circle cx="12" cy="4.5" r="1.6" /><path d="M4 6.1v3.8" /><path d="M4 4.5h8" /><path d="M4 11.5h4.5" /></>,
  validate: <><path d="M8 2 13 4v4.4c0 3-2.2 5-5 5.6-2.8-.6-5-2.6-5-5.6V4z" /><path d="m5.8 8.1 1.6 1.6 3.5-4" /></>,
  replay: <><path d="M13 8a5 5 0 1 1-1.9-3.9" /><path d="M13 2.4v3.2H9.8" /></>,
  measure: <><path d="M2.6 9.4 9.4 2.6l4 4-6.8 6.8z" /><path d="m4.8 7.2 1.5 1.5" /><path d="m6.9 5.1 1.5 1.5" /><path d="m9 3 1.5 1.5" /></>,
  compare: <><path d="M2.6 3.5h4.6v9H2.6z" /><path d="M8.8 3.5h4.6v9H8.8z" /></>,
  "add-view": <><path d="M2.6 4.4a1.8 1.8 0 0 1 1.8-1.8h7.2a1.8 1.8 0 0 1 1.8 1.8v7.2a1.8 1.8 0 0 1-1.8 1.8H4.4a1.8 1.8 0 0 1-1.8-1.8z" /><path d="M8 5.6v4.8" /><path d="M5.6 8h4.8" /></>,
  more: <><circle cx="3.4" cy="8" r="1.15" /><circle cx="8" cy="8" r="1.15" /><circle cx="12.6" cy="8" r="1.15" /></>,
  sun: <><circle cx="8" cy="8" r="3.1" /><path d="M8 1.4v1.5" /><path d="M8 13.1v1.5" /><path d="M1.4 8h1.5" /><path d="M13.1 8h1.5" /><path d="m3.3 3.3 1.1 1.1" /><path d="m11.6 11.6 1.1 1.1" /><path d="m12.7 3.3-1.1 1.1" /><path d="m4.4 11.6-1.1 1.1" /></>,
  moon: <><path d="M13.4 9.6A5.8 5.8 0 0 1 6.4 2.6a5.9 5.9 0 1 0 7 7z" /></>,
  recipe: <><path d="M3.6 3.4h8.8v10.2H3.6z" /><path d="M6 2h4v2.4H6z" /><path d="M6 8h4" /><path d="M6 10.6h4" /></>,
  catalog: <><path d="M2.6 2.6h4.8v4.8H2.6z" /><path d="M8.6 2.6h4.8v4.8H8.6z" /><path d="M2.6 8.6h4.8v4.8H2.6z" /><path d="M8.6 8.6h4.8v4.8H8.6z" /></>,
  layers: <><path d="m8 2.4 5.8 2.9L8 8.2 2.2 5.3z" /><path d="m2.2 8.3 5.8 2.9 5.8-2.9" /><path d="m2.2 11.1 5.8 2.9 5.8-2.9" /></>,
  comments: <><path d="M2.6 3.6h10.8v7.3H7.1L3.6 13.3v-2.4h-1z" /></>,
  metrics: <><path d="M2.4 13.4h11.2" /><path d="M4 13.4V8.4" /><path d="M7 13.4V4.4" /><path d="M10 13.4v-3.6" /><path d="M13 13.4V6.6" /></>,
  gates: <><circle cx="8" cy="8" r="5.8" /><path d="m5.3 8.2 1.9 1.9 3.5-3.9" /></>,
  provenance: <><circle cx="4" cy="4.4" r="1.6" /><circle cx="4" cy="11.6" r="1.6" /><circle cx="12" cy="7.9" r="1.6" /><path d="M4 6v3.9" /><path d="M4 4.4h5.6" /><path d="M4 11.6h1" /></>,
  artifacts: <><path d="M8 2.2 13.4 5v6L8 13.8 2.6 11V5z" /><path d="m2.6 5 5.4 2.9L13.4 5" /><path d="M8 7.9v5.9" /></>,
  "top-down": <><path d="m2.6 4 3.4-1.5 4 1.5 3.4-1.5v9L9.6 13 5.6 11.5 2.6 13z" /><path d="M6 2.5v9" /><path d="M10 4v9.5" /></>,
  "third-person": <><circle cx="8" cy="4.6" r="2.3" /><path d="M3.6 13.6a4.4 4.4 0 0 1 8.8 0" /></>,
  "in-car": <><path d="M2.5 10.8h11" /><path d="m4 10.8 1.2-4h5.6l1.2 4" /><circle cx="4.5" cy="12.5" r="1" /><circle cx="11.5" cy="12.5" r="1" /></>,
  lidar: <><circle cx="8" cy="8" r="1.7" /><path d="M4.7 6.3a4.8 4.8 0 0 0 0 3.4" /><path d="M11.3 6.3a4.8 4.8 0 0 1 0 3.4" /><path d="M8 2.4v1.6" /><path d="M8 12v1.6" /><path d="M2.4 8H4" /><path d="M12 8h1.6" /></>,
  "sensor-evidence": <><path d="M2.5 11.5 5.7 8l2.3 2.2 3.5-4.1 2 2" /><path d="M2.5 13.5h11" /><circle cx="5.7" cy="8" r="1" /><circle cx="11.5" cy="6.1" r="1" /></>,
  "chevron-left": <><path d="m9.5 4-4 4 4 4" /></>,
  "chevron-right": <><path d="m6.5 4 4 4-4 4" /></>,
  "chevron-up": <><path d="m4 9.5 4-4 4 4" /></>,
  "chevron-down": <><path d="m4 6.5 4 4 4-4" /></>,
} satisfies Record<string, ReactElement>;

export type IconName = keyof typeof icons;

export function Icon({ name, size = 16 }: { name: IconName; size?: number }) {
  return (
    <svg className="icon" width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.35} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      {icons[name]}
    </svg>
  );
}
