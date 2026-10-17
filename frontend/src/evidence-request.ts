export type PlayheadFetcher<TArgs, TResult> = (args: TArgs, signal: AbortSignal) => Promise<TResult>;

export function createPlayheadRequest<TArgs, TResult>(fetcher: PlayheadFetcher<TArgs, TResult>, debounceMs = 125) {
  if (!Number.isFinite(debounceMs) || debounceMs < 100 || debounceMs > 150) throw new RangeError("debounceMs must be between 100 and 150 milliseconds");
  let timer: ReturnType<typeof setTimeout> | undefined;
  let controller: AbortController | undefined;
  let rejectPending: ((reason?: unknown) => void) | undefined;
  let disposed = false;
  const abortError = () => new DOMException("Playhead request was superseded", "AbortError");
  const cancel = () => {
    if (timer !== undefined) clearTimeout(timer);
    timer = undefined;
    controller?.abort();
    controller = undefined;
    rejectPending?.(abortError());
    rejectPending = undefined;
  };
  return {
    request(args: TArgs): Promise<TResult> {
      if (disposed) return Promise.reject(new Error("Playhead request handle is disposed"));
      cancel();
      const next = new AbortController();
      controller = next;
      return new Promise<TResult>((resolve, reject) => {
        rejectPending = reject;
        timer = setTimeout(() => {
          timer = undefined;
          if (next.signal.aborted || controller !== next) return;
          void fetcher(args, next.signal).then((value) => {
            if (controller !== next || next.signal.aborted) return;
            controller = undefined; rejectPending = undefined; resolve(value);
          }, (error) => {
            if (controller !== next || next.signal.aborted) return;
            controller = undefined; rejectPending = undefined; reject(error);
          });
        }, debounceMs);
      });
    },
    cancel,
    dispose() { if (!disposed) { cancel(); disposed = true; } },
  };
}
