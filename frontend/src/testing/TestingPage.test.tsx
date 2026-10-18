// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import TestingPage from "./TestingPage";

vi.mock("../wasm-playback/WasmPlaybackView", () => ({
  default: () => <div data-testid="wasm-playback-view" />,
}));

describe("TestingPage", () => {
  afterEach(() => cleanup());
  it("renders the diagnostic edit-object probe and metrics", () => {
    render(<TestingPage />);
    expect(screen.getByRole("heading", { name: "Edit-object path lab" })).toBeTruthy();
    expect(screen.getByText("Internal physics ADE")).toBeTruthy();
    expect(screen.getByRole("img", { name: /editable two dimensional motion path/i })).toBeTruthy();
  });

  it("releases a dragged keyframe on pointer up", () => {
    render(<TestingPage />);
    const svg = screen.getByRole("img", { name: /editable two dimensional motion path/i });
    Object.defineProperty(svg, "getBoundingClientRect", { value: () => ({ left: 0, top: 0, width: 100, height: 100 }) });
    const handles = svg.querySelectorAll("circle.testing-keyframe");
    const before = handles[1].getAttribute("cx");
    fireEvent.pointerDown(handles[1], { pointerId: 7, clientX: 100, clientY: 100 });
    fireEvent.pointerMove(svg, { pointerId: 7, clientX: 180, clientY: 120 });
    fireEvent.pointerUp(svg, { pointerId: 7, clientX: 180, clientY: 120 });
    const afterDrop = svg.querySelectorAll("circle.testing-keyframe")[1].getAttribute("cx");
    fireEvent.pointerMove(svg, { pointerId: 7, clientX: 280, clientY: 150 });
    expect(afterDrop).not.toBe(before);
    expect(svg.querySelectorAll("circle.testing-keyframe")[1].getAttribute("cx")).toBe(afterDrop);
  });

  it("renders a locked origin keyframe and CAD motion guardrails", () => {
    render(<TestingPage />);
    expect(screen.getByText(/Origin is immutable/)).toBeTruthy();
    expect(screen.getByText(/CAD motion guardrails/)).toBeTruthy();
    expect(screen.getByText(/velocity ≤ 20.0 m\/s/)).toBeTruthy();
    expect(screen.getAllByText(/locked origin/i).length).toBeGreaterThan(0);
  });
});
