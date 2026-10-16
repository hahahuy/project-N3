# Development and Product Environments

Status: `CURRENT`
Audience: anyone maintaining `project-N3`, especially readers new to running
separate environments.

Related: `docs/current/demo-hardening-backlog.md`,
`docs/guides/security-deployment.md`, `README.md`.

---

## 1. What the two environments are

Both run **the same application code**. Only the configuration differs.

| | **Development** | **Product** |
|---|---|---|
| Audience | you | judges / contest |
| URL | `http://100.114.248.93:5173` | `https://project-n3.hahuy.cloud` |
| Compose file | `compose.dev.yml` | `compose.demo.yml` |
| Docker project | `project-n3` | `project-n3-prod` |
| Frontend | Vite dev server, hot reload | built bundle from `frontend/dist` |
| Source on disk | bind-mounted, edits are live | built assets only |
| Access control | none | nginx shared key + TLS |
| Reachable from | LAN / Tailscale only | public internet |
| Restarts freely | yes | deliberately, rarely |

The API runs as the configured host UID/GID in both Compose environments. A
short-lived root-only `api-permissions` service initializes the reports volume
before the API starts, so replay, preview and WASM-pair artifacts remain
writable without running the API as root.

### Why they must differ

A development server is built for someone who already has the code open. It
recompiles on save, serves your TypeScript source directly, and exposes hot
module replacement. None of that helps a judge, and all of it leaks information.

Serving the development server to the public internet is therefore the mistake
this separation exists to prevent. Section 3 shows what that mistake looks like
when it happens.

## 2. How the product environment is wired

```text
judge browser
    │  https, shared key
    ▼
Cloudflare edge  ──►  project-n3.hahuy.cloud
    │  encrypted tunnel, no public origin port
    ▼
project-n3-prod-cloudflared      (tunnel connector)
    ▼
project-n3-prod-gateway          (nginx: TLS, Basic auth, :8443 → :443)
    ▼
project-n3-prod-api              (FastAPI :8000)
    ├── /api/*        scenario, workspace, batch endpoints
    └── everything else  static SPA from frontend/dist
```

FastAPI serves the built bundle itself, mounted below the `/api` namespace
(`src/r2s_web/app.py:889-893`). There is deliberately **no frontend container in
the product stack** and **no Vite dev server on the public path**.

Only `gateway` publishes a host port. `api` and `cloudflared` publish none, so
the shared key cannot be bypassed by reaching the backend directly.

## 3. What changed, and why

### The product stack stopped running a dev server

Previously the product stack proxied to `frontend:5173` — the Vite development
server. Verified consequences over the public route:

| Path | Before | After |
|---|---|---|
| `/src/api.ts` | `200`, real TypeScript source | `404` |
| `/@vite/client` | `200`, HMR client | `404` |
| `/vite.config.ts` | `200` | `404` |
| `/package.json` | `200` | `404` |

The gateway now proxies to `api:8000`, which serves `frontend/dist`. This also
removed a 651 MB container.

### The metadata index is shared

The nuScenes metadata tables total ~2.6 GB. Building the index takes roughly
56 seconds and produces a 787 MB SQLite file.

Each stack previously had its own volume, so both paid that cost. They now
reference one explicitly named volume:

```yaml
volumes:
  project-n3-metadata-cache:
    name: project-n3-metadata-cache   # same volume for both compose projects
```

Measured effect on the product route: the first `/api/source-scenes` after a
fresh volume went from **55.8 s** to **4.2 s**.

The index is validated against source table size and mtime
(`src/real2scenario/metadata_index.py:585-594`), so a dataset change rebuilds
it automatically.

### Product artifacts are isolated

`artifact_root` is `/app/scenarios` in both environments, but each now resolves
to a different storage location:

- development → the repository working tree (gitignored `scenarios/`)
- product → a dedicated named volume

So a judge importing scenes cannot clutter your development catalog, and your
experiments do not appear in the demo. The product volume is seeded from
`scenarios/nuscenes/` so judges still start with curated content.

### Resource limits

The product services are capped, so a runaway batch cannot starve the other
containers on this host. `hhf-server` also runs `banking-agent`, `kavita`,
`searxng`, two sites and a `carla` container on 12 cores.

| Service | CPU | Memory |
|---|---|---|
| `api` | 2.0 | 4G |
| `gateway` | 0.5 | 256M |
| `cloudflared` | 0.25 | 128M |

## 4. Commands

```
make dev          start development        -> http://100.114.248.93:5173
make prod         build bundle, start prod -> https://project-n3.hahuy.cloud
make status       what is running in both
make stop         stop everything
make test         python + frontend suites
make key          rotate the shared key / certificate
make prod-logs    tail product logs
make dev-down     stop development
```

Run these from the repository root. `make prod` rebuilds the frontend bundle
every time, so the public site never serves stale code.

## 5. Before a contest or demo

**Stop the development stack.** `compose.dev.yml` binds `0.0.0.0:8001` and
`0.0.0.0:5173` and serves the same application with no authentication. While it
runs, anyone on the LAN or Tailscale can reach the app and bypass the shared key
entirely. Verified at runtime:

```
http://127.0.0.1:8001/api/health  -> 200   with no credential
```

```bash
make dev-down
```

The shared key protects the **public route only**.

## 6. Day-to-day workflow

```bash
make dev                 # work on code, view at 100.114.248.93:5173
# ... edit files; the browser hot-reloads ...
make test                # before showing anyone
make prod                # publish what you just built
# verify: https://project-n3.hahuy.cloud  ->  401 without the key, 200 with
make dev-down            # close the LAN exposure
```

If the public site still shows your previous change, run `make prod-rebuild`
rather than `make prod`.

## 7. Verification performed

| Check | Result |
|---|---|
| Public route without credential | `401` with `www-authenticate: Basic realm="Real2Scenario Contest Demo"` |
| Public route with credential | `200`, built bundle served |
| `/api/health` through the gateway | `200` |
| `/api/scenarios` through the gateway | 7 scenarios |
| Dev-server paths over the public route | all `404` |
| Product `/api/source-scenes` | 4.2 s (was 55.8 s cold) |
| Product published ports | gateway only |
| Product container memory | 83 MB api, 10 MB gateway, 16 MB cloudflared |
| Development stack | unaffected, still serving on `8001`/`5173` |
| Python suite | 322 passed |

## 8. Unverified

- The 4.2 s source-scene time is a single observation with warm page cache, not
  a benchmark. Under load it will be slower.
- Resource limits are set but not tested under deliberate load.
- Product artifact isolation is verified for the seeded catalog only. A judge
  importing new scenes has not been exercised.
- `make` targets were smoke-tested individually, not as a full daily cycle.
- S-6, the batch concurrency cap, is still unimplemented. See
  `docs/current/demo-hardening-backlog.md` section 3.
