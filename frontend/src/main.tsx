if (import.meta.env.DEV) {
  import("react-grab");
}

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import WasmSmokePage from "./wasm-smoke/WasmSmokePage";
import TestingPage from "./testing/TestingPage";
import "./styles.css";

const Root = window.location.pathname === "/wasm-smoke" ? WasmSmokePage : window.location.pathname === "/testing" ? TestingPage : App;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);
