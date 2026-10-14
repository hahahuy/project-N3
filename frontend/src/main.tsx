if (import.meta.env.DEV) {
  // Optional local inspection helper; production builds do not load it.
  // @ts-expect-error react-grab is a dev-only optional dependency.
  import("react-grab");
}

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
