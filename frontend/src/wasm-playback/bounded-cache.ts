/** Small, deterministic cache primitives for playback-side decoded payloads. */

export type DisposeCallback<K, V> = (value: V, key: K) => void;
export type ByteBoundedLruOptions<K, V> = { maxBytes: number; byteSize: (value: V, key: K) => number; onDispose?: DisposeCallback<K, V> };
type Entry<K, V> = { key: K; value: V; bytes: number };

/** An insertion-ordered LRU with a hard byte budget. */
export class ByteBoundedLru<K, V> {
  private readonly entries = new Map<K, Entry<K, V>>();
  private readonly dispose?: DisposeCallback<K, V>;
  private totalBytes = 0;
  readonly maxBytes: number;
  readonly byteSize: (value: V, key: K) => number;

  constructor(options: ByteBoundedLruOptions<K, V>) {
    if (!Number.isFinite(options.maxBytes) || options.maxBytes < 0) throw new RangeError("maxBytes must be a finite non-negative number");
    this.maxBytes = options.maxBytes;
    this.byteSize = options.byteSize;
    this.dispose = options.onDispose;
  }
  get size(): number { return this.entries.size; }
  get bytes(): number { return this.totalBytes; }
  has(key: K): boolean { return this.entries.has(key); }
  touch(key: K): boolean { return this.get(key) !== undefined; }
  /** Read without changing eviction order; safe for render-time inspection. */
  peek(key: K): V | undefined { return this.entries.get(key)?.value; }
  get(key: K): V | undefined {
    const entry = this.entries.get(key);
    if (!entry) return undefined;
    this.entries.delete(key); this.entries.set(key, entry);
    return entry.value;
  }
  set(key: K, value: V): this {
    const bytes = this.byteSize(value, key);
    if (!Number.isFinite(bytes) || bytes < 0) throw new RangeError("byteSize must be finite and non-negative");
    const previous = this.entries.get(key);
    if (previous) { this.entries.delete(key); this.totalBytes -= previous.bytes; this.disposeEntry(previous); }
    if (bytes > this.maxBytes) { this.dispose?.(value, key); return this; }
    while (this.totalBytes + bytes > this.maxBytes) {
      const oldest = this.entries.entries().next().value as [K, Entry<K, V>] | undefined;
      if (!oldest) break;
      this.entries.delete(oldest[0]); this.totalBytes -= oldest[1].bytes; this.disposeEntry(oldest[1]);
    }
    this.entries.set(key, { key, value, bytes }); this.totalBytes += bytes;
    return this;
  }
  delete(key: K): boolean {
    const entry = this.entries.get(key); if (!entry) return false;
    this.entries.delete(key); this.totalBytes -= entry.bytes; this.disposeEntry(entry); return true;
  }
  clear(): void { for (const entry of this.entries.values()) this.disposeEntry(entry); this.entries.clear(); this.totalBytes = 0; }
  keys(): K[] { return [...this.entries.keys()]; }
  private disposeEntry(entry: Entry<K, V>): void { this.dispose?.(entry.value, entry.key); }
}

export const byteLengthOfFloat32Array = (value: Float32Array): number => value.byteLength;
export type TimedSweep = { time_s: number };

/** Select a centered, bounded window around the latest sweep at/before playhead. */
export const selectSweepWindow = <T extends TimedSweep>(sweeps: readonly T[], playheadS: number, maxSweeps: number): T[] => {
  if (!Number.isInteger(maxSweeps) || maxSweeps < 0) throw new RangeError("maxSweeps must be a non-negative integer");
  if (maxSweeps === 0 || sweeps.length === 0) return [];
  if (sweeps.length <= maxSweeps) return [...sweeps];
  if (maxSweeps === 1) {
    let active = 0;
    for (let index = 1; index < sweeps.length && sweeps[index].time_s <= playheadS; index++) active = index;
    return [sweeps[active]];
  }
  let active = 0;
  for (let index = 1; index < sweeps.length && sweeps[index].time_s <= playheadS; index++) active = index;
  const before = Math.floor((maxSweeps - 1) / 2);
  const start = Math.max(0, Math.min(active - before, sweeps.length - maxSweeps));
  return sweeps.slice(start, start + maxSweeps);
};
