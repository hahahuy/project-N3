# M5A Development Readiness

## Remote Development Entry Point

The development stack is `compose.dev.yml`. It runs a reloadable FastAPI
backend and a Vite frontend with HMR. The repository is mounted into both
containers, while `node_modules` and generated reports use named volumes.

Use:

```bash
docker compose -f compose.dev.yml up -d --build
```

Review the UI at `http://<tailscale-host>:5173`. Vite proxies `/api` to the
backend container. The API is available on the configured host port, defaulting
to `8001` to avoid collisions with existing services.

## M5A Implementation Checklist

- [x] Add esmini capability discovery: configuration, executable, `dat2csv`, version, and diagnostic.
- [x] Extract replay orchestration from `BatchService` into a focused local backend.
- [x] Preserve export, esmini execution, trace normalization, and replay metrics sequence.
- [x] Run replay as a separate non-blocking local job.
- [x] Expose status, version, logs, artifacts, metrics, and structured failures in the API/UI.
- [x] Persist job-specific `.xosc`, `.xodr`, trace, stdout/stderr, and overlay PNG.
- [x] Add fake executable coverage for success, missing configuration, non-zero exit, timeout, and malformed trace.
- [ ] Add a dedicated backend integration test for missing template setup.
- [ ] Add an optional real esmini browser smoke test when tool paths are configured.

The mounted esmini smoke run completed successfully with v3.9.0/build 6434 and
produced metrics plus replay artifacts. The Docker development environment is
ready for the remaining failure-mode tests and browser evidence.
