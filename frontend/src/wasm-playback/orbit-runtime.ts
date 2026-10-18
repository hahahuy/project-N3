import type { WasmOrbitState } from "./types";

export type OrbitCommand =
  | { type: "reset"; orbit: WasmOrbitState }
  | { type: "focus"; actorId: string; orbit: WasmOrbitState }
  | { type: "lock"; actorId: string | null };

export type OrbitListener = (snapshot: WasmOrbitState, revision: number) => void;

const sameVector = (left: readonly number[], right: readonly number[]) => left.every((value, index) => value === right[index]);
const sameOrbit = (left: WasmOrbitState, right: WasmOrbitState) => sameVector(left.position, right.position) && sameVector(left.target, right.target);

export class OrbitRuntime {
  private snapshot: WasmOrbitState;
  private revision = 0;
  private listeners = new Set<OrbitListener>();
  private commands: OrbitCommand[] = [];

  constructor(initial: WasmOrbitState) {
    this.snapshot = initial;
  }

  getSnapshot(): WasmOrbitState { return { position: [...this.snapshot.position] as WasmOrbitState["position"], target: [...this.snapshot.target] as WasmOrbitState["target"] }; }
  getRevision(): number { return this.revision; }

  subscribe(listener: OrbitListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  update(next: WasmOrbitState): boolean {
    if (sameOrbit(this.snapshot, next)) return false;
    this.snapshot = { position: [...next.position] as WasmOrbitState["position"], target: [...next.target] as WasmOrbitState["target"] };
    this.revision += 1;
    for (const listener of this.listeners) listener(this.snapshot, this.revision);
    return true;
  }

  enqueue(command: OrbitCommand): void { this.commands.push(command); }
  consumeCommands(): OrbitCommand[] {
    const commands = this.commands;
    this.commands = [];
    return commands;
  }
}
