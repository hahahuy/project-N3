if (import.meta.env.DEV) {
  import("react-grab");
}

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import WasmSmokePage from "./wasm-smoke/WasmSmokePage";
import TestingPage from "./testing/TestingPage";
import CppWasmPage from "./cpp-wasm/CppWasmPage";
import "./styles.css";

const Root = window.location.pathname === "/wasm-smoke"
  ? WasmSmokePage
  : window.location.pathname === "/testing"
    ? TestingPage
    : window.location.pathname === "/cpp-wasm"
      ? CppWasmPage
      : App;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);
