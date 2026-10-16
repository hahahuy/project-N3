# Public Demo Hardening Backlog

Status: `OPEN — PAGINATION AND BATCH LIMITS REMAIN`
Scope: the three items that must be completed before the web application is
reachable by anyone outside the local network.

Agents must not treat the remaining pagination or batch-limit items as complete.
The reverse-proxy item is built and locally verified, while S-1/S-2 path
confinement is implemented and covered by API tests. The numbers below were
measured on `hhf-server` against a `v1.0-trainval` release and are recorded as
evidence, not as a claim of `DONE`.

Related: `docs/current/active-work.md`, `docs/current/artifact-policy.md`,
`docs/guides/security-deployment.md`, `docs/guides/datastreaming.md`,
`docs/current/project-status.md`.

---

## 1. Why this file exists

The repository currently documents a hardening plan in `docs/guides/` but does
not track it in `docs/current/`. An agent reading the standard onboarding order
would not learn that the public deployment is blocked on three specific items.

This file closes that gap. It is the authoritative status record for these three
items. The guides describe the design; this file describes the state.

---

## 2. D-3 / S-5 — Paginate scene discovery

Status: `OPEN`
Priority: **highest remaining value**

### Problem

`GET /api/source-scenes` returns every scene unpaginated. The implementation is
at `src/r2s_web/app.py` (`list_source_scenes`), which calls
`SourceSceneAdapter.discover()` (`src/r2s_web/source_scenes.py:63-67`). That
iterates all scenes and, per scene, calls `index.sample_tokens()` and
`index.instance_tokens()`.

`fetchSourceScenes` (`frontend/src/api.ts`) consumes the unpaginated list and
renders it without paging.

### Measured cost

Against the mounted `v1.0-trainval` release (850 scenes):

| Call | Time |
|---|---:|
| First call in a process (index already cached) | 56.30 s |
| Second call, same process | 4.19 s |
| First call after container restart | 4.38 s |

The 4.19 s is paid on **every** request. The 56.30 s figure is the first call in
a cold process and is currently invisible to the caller; see D-2 below.

### Required work

1. Add `?limit=&offset=&q=` to the endpoint. Return a total count so the UI can
   show `n/total`.
2. Bound `discover()` so it does not call `sample_tokens()` per scene for a
   page of results.
3. Page the catalog UI.

### Constraints

`active-work.md` records the metadata index invariant: *"discovery and import
output unchanged"*. Pagination must not change which scenes, actors, timestamps
or conventions are selected. A page is a view over the same ordered result, not
a different selection.

### Acceptance criteria

- `GET /api/source-scenes?limit=20` returns 20 records and a correct total.
- `?q=` filters on scene name and returns consistent totals.
- `offset` paging returns every scene exactly once across pages, in the same
  order as the unpaginated response.
- Discovery and import output is byte-identical to the current behaviour for
  every scene, verified against a full unpaginated read.
- Frontend tests and `npm run build` pass.

---

## 3. S-6 — Cap concurrent batch jobs

Status: `OPEN`
Priority: **launch blocker for public exposure**

### Problem

`POST /api/batches` runs generation synchronously inside the request handler.
`BatchService.create` calls `self._run(...)` directly at
`src/r2s_web/jobs.py:86-95`. There is no thread pool, no queue and no cap on
concurrent jobs.

Two consequences:

1. Request handlers block for the full generation duration, so the worker pool
   saturates under load.
2. The endpoint returns HTTP `202 Accepted`, which is incorrect for a
   synchronous handler.

### What already has a cap

`src/r2s_web/live_session.py` correctly caps concurrent live esmini sessions:

- `MAX_SESSIONS = 4` (`src/r2s_web/live_session.py:21`)
- raises `live_session_limit_reached` at line 308-309 when exceeded

The live-session path already applies the discipline this item requires. The
batch path does not.

### Why this matters more now

The live runtime and sensor-evidence work added further callable surfaces:

- `POST /api/esmini/live/sessions`
- `POST /api/esmini/live/scenario-pairs`
- `POST /api/esmini/live/sessions/{session_id}/commands`
- `GET /api/workspace/lidar/{sample_data_token}`
- `GET /api/workspace/scenarios/{scenario_id}/sensor-evidence`

Each additional compute or bulk-data surface widens the exposure while
`jobs.py` remains unbounded.

### Host contention

`hhf-server` is shared. `project-N3` does not run alone; the host also runs
`banking-agent` on port 8000, `normalhahuysite` on 8081, `kavita` on 5000,
`searxng` on 8888, `stratum-site`, and a `carla` container. A batch-generation
flood starves those services, not just this project.

### Required work

1. Add a bounded semaphore or queue to `BatchService` with a configurable limit.
2. Reject excess work with an explicit, documented reason rather than queueing
   unboundedly.
3. Decide whether to run generation off the request thread so the `202`
   semantics are truthful.
4. Bound `count`, grid dimensions and other per-request variant limits.
5. Bound disk growth on `reports/` and `scenarios/`.

### Constraints

`ui-mvp-flow-spec.md` requires that failures are stated plainly and that
unavailability carries an explicit reason. A rejection must name the limit that
was hit, in the same vocabulary as existing availability blocks.

### Acceptance criteria

- A test proves N concurrent batch requests never exceed the configured cap.
- Excess requests return a documented status with a verbatim reason.
- Disk growth is bounded; a documented quota or rotation exists for
  `reports/` and `scenarios/`.
- Full test suite passes.

---

## 4. Reverse proxy shared key — deployment

Status: `BUILT / VERIFIED LOCALLY / NOT PUBLICLY EXPOSED`

The committee accepted a shared access key. The design is in
`docs/guides/security-deployment.md` Section 5.1. The stack is built and running
on the local host. It is **not** reachable from the public internet.

### Target hostname

The intended public route is **`project-n3.hahuy.cloud`** in zone `hahuy.cloud`.

`hahuy.site` is dead — it resolves to parking nameservers
(`ns1/ns2.lander.d.parity.domains`). Certificates and host configuration must use
`hahuy.cloud`. An earlier build generated a certificate for
`project-n3-prod.hahuy.site`; it was reissued on 2026-10-15 and the stale value was
removed from `compose.demo.yml` and `ops/scripts/`.

Do not copy the stale `*.hahuy.site` ingress entries that the four existing
tunnels carry. They are unreachable leftovers.

### What was built

| Path | Purpose |
|---|---|
| `compose.demo.yml` | Demo stack, project name `project-n3-prod`, gateway is the only published service |
| `ops/nginx/demo.conf` | TLS terminator, HTTP→HTTPS redirect, Basic auth, upstream proxy |
| `ops/scripts/generate-demo-credentials.sh` | Generates the shared key and a TLS certificate |
| `ops/demo/secrets/`, `ops/demo/certs/` | Generated material, gitignored |

`frontend/vite.config.ts` gained an opt-in `VITE_ALLOWED_HOSTS` setting so the
dev server accepts the Host header forwarded by the gateway. Vite's DNS
rebinding protection is not disabled; the host is allowlisted explicitly, and
`compose.dev.yml` is unchanged.

### Verified at runtime

| Check | Result |
|---|---|
| No credential | `401` |
| Wrong credential | `401` |
| Correct credential | `200`, app HTML served |
| API through gateway | `/api/health` returns JSON |
| Forwarded `Host: project-n3.hahuy.cloud` | `200` |
| Forwarded `Host: evil.example.com` | `403` (Vite allowlist rejects it) |
| **Bypass: demo-stack `api`/`frontend`** | **no host port published** |
| Published ports (demo stack) | only `0.0.0.0:8443→443` |
| S-1/S-2 under the gateway | `400 artifact_root must stay inside an allowed root` |
| TLS | TLSv1.3, `CN=project-n3.hahuy.cloud`, expires 2026-11-14 |
| Python / frontend suites | 322 passed / 48 passed, build clean |

### Live risk: a memory limit silently took the whole route down

Observed 2026-10-15. Recorded because the failure looks healthy from outside.

The product `api` container was capped at **4 GB**. A judge loaded the app and
worked normally, then opened the recorded-LiDAR surfaces. Those endpoints decode
point-cloud sweeps and pushed the container past its limit, so Docker killed the
worker:

```
OOMKilled=true
```

The failure was silent because `Dockerfile.dev` runs
`uvicorn --reload`, and **the `--reload` supervisor does not respawn a
killed worker**. Result:

- container status stayed `Up`
- the health check reported `unhealthy` only after its own retries
- nothing was listening on 8000
- every public request returned `502` or timed out
- `docker stats` showed ~3 MB RSS, which reads as "idle", not "dead"

**Fix history — three states, only the last is current.** This section previously
read "the memory limit was removed"; that statement is **stale**.

1. The 4 GB cap was removed, and the owner accepted host-memory risk in
   preference to the silent-failure mode. CPU stayed bounded at 4.0.
2. Unbounded memory was then tried. On 2026-10-15 a worker grew to ~25 GB
   anon-rss and the kernel performed four GLOBAL OOM kills, which took down
   **unrelated containers on the host**. The `--reload` supervisor still did not
   respawn the killed worker, so the container stayed `Up` while nothing listened
   on 8000 and the whole product route returned 502 behind a healthy-looking
   container.
3. **Current, in the uncommitted working tree of `compose.demo.yml`:** memory is
   capped at **12G** by owner request (2026-10-15). This bounds the blast radius
   to this container while leaving headroom above the observed LiDAR-path peak.

| Service | CPU | Memory | State |
|---|---|---|---|
| `api` | 4.0 | 12G | current (uncommitted) |
| `gateway` | 0.5 | 256M | current |
| `cloudflared` | 0.25 | 128M | current |

Observed peak for the product `api` on the LiDAR path: **~7.7 GB** (4 GB era) and
**~25 GB** (unbounded era, 2026-10-15). The 12G cap sits between the two; it is
an owner decision recorded in the compose comment, not a measured optimum.

**The underlying hazard is not solved by any of the three states:** `uvicorn
--reload` in `Dockerfile.dev` does not respawn a killed worker, so any memory
limit or any kernel OOM kill presents as a healthy container serving 502s. The
durable fixes are removing `--reload` from a long-running environment and adding
a restart policy, neither of which is implemented. Until then, treat the demo
route as capable of silent total failure and monitor with an actual request, not
container status.

Two lessons:

1. Do not add a memory limit to a service that decodes point clouds without
   measuring that path first.
2. `--reload` in a long-running environment is the real hazard: it hides a
   crashed worker behind an apparently healthy container. The production
   `Dockerfile` does not use `--reload`; `Dockerfile.dev` does.

### Live risk: the dev stack bypasses the key

`compose.dev.yml` binds `0.0.0.0:8001` and `0.0.0.0:5173` and serves the **same
application** with no authentication. This was confirmed at runtime: with the
dev stack running, `curl http://127.0.0.1:8001/api/health` returns `200` with no
credential.

The shared key therefore protects the **public route only**. Anyone on the LAN or
Tailscale can reach the app and bypass it entirely via the dev stack.

**Before the contest, stop the dev stack** or bind it to loopback:

```bash
docker compose -f compose.dev.yml stop
```

This was observed directly: the earlier bypass test passed only because the dev
stack happened to be stopped at that moment.

Two defects were found and fixed during this build, both recorded here because
they are the kind that silently return:

1. **`compose.demo.yml` and `compose.dev.yml` shared a project name**, so the
   demo stack silently clobbered the running dev containers. Fixed with
   `name: project-n3-prod`. Both stacks now run simultaneously.
2. **nginx resolves literal upstream names at configuration load** and exits if
   they do not resolve, so the gateway crash-looped when it started before Vite
   was listening. Fixed with a runtime `resolver 127.0.0.11` plus a variable in
   `proxy_pass`, which also survives a frontend recreation without a reload.

### Access model

The credential file is mounted directly rather than by directory, and nginx
workers (uid 101) receive read access through an ACL
(`setfacl -m u:101:r--`). It is never world-readable and never enters the
frontend bundle.

### Still required before public exposure

1. **A Cloudflare tunnel and DNS record.** This is the only remaining blocker.
   It cannot be created from this host: the existing `cloudflared` tunnels use
   token-managed ingress (`tunnel run --token ...`), so the tunnel, its ingress
   rules and the proxied CNAME all live in the Cloudflare dashboard/API. An
   owner action is required to create a `project-n3` tunnel pointing at
   `https://gateway:443`, and to add a proxied CNAME
   `project-n3.hahuy.cloud` → `<tunnel-id>.cfargotunnel.com`.
2. **Origin TLS decision.** The current certificate is self-signed and expires
   **2026-11-14**. Cloudflare will not trust a self-signed origin certificate
   even when its hostname matches, so a tunnel route with
   `service: https://gateway:443` requires either `noTLSVerify: true` on that
   ingress, or a Cloudflare Origin CA certificate. Note that `noTLSVerify`
   removes origin authentication: a green test under it does not prove the route
   is correct, because it would also mask a genuinely wrong origin. This is an
   owner decision.
3. **Stop the dev stack** during the contest, or the key is bypassable on the LAN
   (see above).
4. **Per-judge keys.** One shared credential is configured. One key per judge
   would allow individual revocation and auditability.
5. **S-6.** No concurrency cap on batch generation behind a public route.

### Acceptance criteria status

| Criterion | Status |
|---|---|
| Unauthenticated request returns 401, correct credential returns 200 | met |
| API port unreachable from the host | met |
| Origin serves HTTPS | met, self-signed |
| Origin rejects plain HTTP on the TLS port | met, `400` |
| S-1/S-2 confinement tests still pass | met, 6 tests |

### Already complete

S-1 and S-2 are implemented in `src/r2s_web/config.py` and covered by the path-safety tests in
`tests/test_web_api.py`. Untrusted input can no longer select `dataset_root`,
`artifact_root` or `output_root` outside the allowed roots. Do not reintroduce
raw path handling in `WebSettings.with_paths`. Re-confirmed through the demo
gateway at runtime.

---

## 5. Relationship to `docs/current/project-status.md:116`

That line states backend work must not claim *"public nuScenes artifact release"*.

Publishing derived scenario JSON to a contest demo appears to conflict with it.
`docs/guides/security-deployment.md` Section 6 records that the nuScenes licence
permits sharing adapted material for NonCommercial purposes, subject to
attribution and share-alike, so the licence is not the blocker. The blocker is
the project's own stated scope.

This requires an explicit owner decision recorded in `docs/current/decisions.md`.
It is **not** resolved, and no agent should resolve it by publishing.

---

## 6. Suggested execution order

| Order | Item | Rationale |
|---:|---|---|
| 1 | D-3 / S-5 | Cheapest, largest measured win; not a security control |
| 2 | S-6 | Remaining launch blocker for public exposure |
| 3 | Real certificate + Cloudflare hostname | Owner actions; gateway already built |

## 7. Unverified

- No public origin has been tested. All exposure statements describe local state.
- The certificate is self-signed; no real CA-issued certificate has been
  obtained or tested with judges.
- The Cloudflare public hostname has not been created, so no public path to the
  gateway exists and none was tested.
- Only one shared credential was exercised. Per-judge issuance and revocation
  are untested.
- The 4.19 s and 56.30 s timings are single observations on `hhf-server` with
  warm page cache, not a benchmark.
- `hhf-server` was under concurrent load from other containers during
  measurement.
- The concurrency cap value for S-6 is not chosen.
- `vite.config.ts` was modified by this work. `npm test` and `npm run build`
  pass, but the allowlist behaviour has only been exercised through the local
  gateway.
