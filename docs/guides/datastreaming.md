# Data Streaming and Database Optimization Guide

Status: `PROPOSED — NOT IMPLEMENTED`
Scope: metadata access, scene discovery, artifact catalog and Docker wiring.
Authority: this document proposes changes. It does not alter current Plan A
scope, canonical schemas, scientific contracts or the metadata-index design.

Related: `docs/guides/security-deployment.md`, `docs/current/technical-contracts.md`,
`docs/current/ui-mvp-flow-spec.md`.

---

## 1. Summary

The metadata architecture is already correct and should not be replaced.
`MetadataIndex` streams the nuScenes JSON tables once into a SQLite projection
and answers scene-scoped queries from it. `tables_for_scenes()` already narrows
extraction to a single scene. This is the right design for a single-user local
tool.

The observed slowness is **not** caused by the design. It is caused by four
specific, independently fixable defects:

1. the metadata index is rebuilt from 2.5 GB of JSON on every container
   recreation, because its cache directory is not persisted;
2. the index is built lazily inside the first API request, so the first request
   hangs for minutes with no progress reported;
3. `/api/source-scenes` enumerates all 850 scenes unbounded and unpaginated;
4. `ArtifactAdapter.discover()` re-parses every artifact JSON on every call.

SQLite remains the correct store. A different database would add operational
cost without addressing any of the above.

---

## 2. Current Docker topology

```text
compose.dev.yml
  api      python:3.11-slim-bookworm   Dockerfile.dev
           - .:/app                          bind mount (source + HMR)
           - project-n3-prod-reports:/app/reports        named volume
           - /mnt/backup/nuscenes:/...:ro     read-only bind mount
           - ~/esmini:/opt/esmini:ro          read-only bind mount
           CMD uvicorn --host 0.0.0.0 --port 8000 --reload

  frontend node:22-bookworm-slim       frontend/Dockerfile.dev
           - ./frontend:/app/frontend          bind mount (HMR)
           - frontend-node-modules:/...         named volume
           CMD npm run dev -- --host 0.0.0.0
```

Two facts follow from this and drive most of the recommendations below.

**F-A — The API container runs as root and has no cache volume.**
`Dockerfile.dev` declares no `USER`. `MetadataIndex.default_cache_dir()`
(`src/real2scenario/metadata_index.py:53-55`) resolves to
`Path.home() / ".cache" / "real2scenario" / "metadata-index"`, which is therefore
`/root/.cache/...` inside the container. `compose.dev.yml` mounts no volume
there, and `R2S_METADATA_CACHE` is set in no compose file, Dockerfile or doc.
The cache therefore lives in the container writable layer and is destroyed on
every `docker compose down`, rebuild or image recreate.

The production `Dockerfile` is correct by contrast: it creates `appuser`
(uid 10001) and switches to it.

**F-B — The frontend proxies `/api` to the backend by service name.**
`frontend/vite.config.ts` reads `VITE_API_PROXY` (default `http://127.0.0.1:8000`);
`compose.dev.yml` sets it to `http://api:8000`. The browser only ever talks to
the Vite dev server on `:5173`. This means **every API call is proxied through
Node**, adding a hop, and all backend load is serialized behind the single
frontend container.

---

## 3. Root cause: the index rebuild

`v1.0-trainval` metadata as mounted:

| File | Size |
|---|---|
| `sample_data.json` | 1.35 GB |
| `ego_pose.json` | 646 MB |
| `sample_annotation.json` | 583 MB |
| `instance.json` | 16 MB |
| `sample.json` | 7.4 MB |
| **Total** | **~2.6 GB** |

On the host, a valid index already exists:
`~/.cache/real2scenario/metadata-index/v1.0-trainval-nuscenes-metadata-index-v1.sqlite3`
(787 MB). The container cannot see it (F-A), so it re-streams all 2.6 GB through
Python on every recreation. This is the observed "reads the whole dataset at
once" behaviour.

Rebuild cost is amortized within a container lifetime: `_source_signature`
(`src/real2scenario/metadata_index.py:585-594`) stat()s nine tables and
`_cache_matches` (`:597-615`) only rebuilds when size or mtime changes. The
problem is purely **cross-restart cache loss**.

---

## 4. Recommended changes

Ordered by value. D-1 and D-3 are the highest return.

### D-1 — Persist the metadata index cache (critical)

Add a named volume at the cache path.

```yaml
  api:
    volumes:
      - .:/app
      - project-n3-prod-reports:/app/reports
      - project-n3-metadata-cache:/root/.cache/real2scenario   # add
      - /mnt/backup/nuscenes:/mnt/backup/nuscenes:ro
      - ${HOME}/esmini:/opt/esmini:ro

volumes:
  frontend-node-modules:
  project-n3-prod-reports:
  project-n3-metadata-cache:                                     # add
```

More portable than hardcoding `/root`, and independent of D-4:

```yaml
    environment:
      R2S_METADATA_CACHE: /var/cache/real2scenario        # add
    volumes:
      - project-n3-metadata-cache:/var/cache/real2scenario       # add
```

This key is already honoured at `src/real2scenario/metadata_index.py:30-33`.
Pre-seed the volume from the existing host index to make the first boot free:

```bash
docker compose -f compose.dev.yml up -d
docker compose -f compose.dev.yml exec -T api \
  sh -c 'mkdir -p /var/cache/real2scenario/metadata-index'
docker cp ~/.cache/real2scenario/metadata-index/v1.0-trainval-nuscenes-metadata-index-v1.sqlite3 \
  "$(docker compose -f compose.dev.yml ps -q api)":/var/cache/real2scenario/metadata-index/
```

The `_source_signature` guard means the seeded file is adopted if size and mtime
still match the mounted source.

### D-2 — Build the index at startup, not inside the first request

`/api/health` → `_settings_view()` → `SourceSceneAdapter.discover()` →
`shared_metadata_index()` (`src/PROJECT_N3_WEB/source_scenes.py:36-52`) constructs the
index synchronously. The first caller absorbs the entire build cost.

Move construction into the FastAPI lifespan/startup hook, so that:

- `/api/health` answers immediately;
- the response reports readiness honestly (e.g. `index_ready`, `index_state`,
  `scene_count`);
- the UI can show a real progress state instead of a hung request.

This directly satisfies `docs/current/ui-mvp-flow-spec.md:31-32`: availability
must never degrade silently.

### D-3 — Paginate scene discovery

`GET /api/source-scenes` (`src/PROJECT_N3_WEB/app.py:234-239`) returns all scenes and is
consumed by `fetchSourceScenarios` (`frontend/src/api.ts:110`) with no paging.

Add `?limit=&offset=&q=` server-side, returning a total count for the UI. Pair
with the catalog work described in `docs/current/ui-mvp-flow-spec.md` so the
scene list becomes the intended entry surface rather than a hidden endpoint.

Query cost today is ~1,700 SQL statements per uncached first call
(`sample_tokens()` plus `instance_tokens()` per scene).

### D-4 — Add a non-root user to the dev image

Match `Dockerfile`. This makes the cache path explicit and independent of the
`HOME` assumption, and removes F-5 from `docs/guides/security-deployment.md`.

Requires care: the bind-mounted project tree must stay writable, and the named
cache volume must be chowned to the new uid.

### D-5 — Mount only what the viewer reads

The current mount exposes all of nuScenes, including `samples/` and `sweeps/`
(camera and LiDAR blobs), which the metadata path never reads.

```yaml
    volumes:
      - /mnt/backup/nuscenes/v1.0-trainval:/data/nuscenes/v1.0-trainval:ro
      - /mnt/backup/nuscenes/maps:/data/nuscenes/maps:ro
    environment:
      NUSCENES_ROOT: /data/nuscenes
```

Smaller blast radius, faster cold starts. Note `WebSettings.__post_init__`
(`src/PROJECT_N3_WEB/config.py:22-27`) already falls back from `v1.0-trainval` to
`v1.0-mini` when the former is absent, so this layout stays compatible.

---

## 5. Database recommendations

**Keep SQLite. Do not migrate to a server database.** Rationale: single-user
local deployment, no shared storage, no queue (`README.md:169-171`), and the
canonical scenario schema is file-based by design. Postgres would add a service,
a schema migration and an operational burden while leaving every finding in this
document untouched.

Four concrete improvements to the current SQLite usage:

### D-6 — Replace the global query lock with per-thread connections

`_query` (`src/real2scenario/metadata_index.py:475-479`) holds a single
`threading.RLock` around one shared connection created with
`check_same_thread=False` (`:622-626`). Under FastAPI's thread pool, **every**
metadata query serializes across all requests.

Switch to WAL mode and a `threading.local()` connection per worker. WAL permits
concurrent readers with a single writer, which is exactly this access pattern.

### D-7 — Tune read pragmas

The build uses `journal_mode=OFF` and `synchronous=OFF`
(`src/real2scenario/metadata_index.py:280-281`), which is correct for bulk load.
For the read path, set on the persistent cache connection:

```sql
PRAGMA journal_mode = WAL;
PRAGMA mmap_size = 268435456;   -- 256 MB
PRAGMA cache_size = -64000;     -- 64 MB
PRAGMA temp_store = MEMORY;
```

`mmap_size` avoids copying pages through the SQLite heap, which matters for a
787 MB file under concurrent reads.

### D-8 — Make `scene()` a dict lookup

`scene()` (`:120-124`) performs a linear scan over all scene records — 850
iterations — and is called from `import_scene` and from `tables_for_scenes()`,
which itself calls `self.scene(token)` per token (`:181-182`).

`_small_table` already memoizes, so build a `token -> record` dict alongside it.
O(n) to O(1), no schema change.

### D-9 — Cache the artifact catalog

`ArtifactAdapter.discover()` (`src/PROJECT_N3_WEB/adapter.py:51-73`) performs
`artifact_root.rglob("*.json")` and fully parses **every** artifact on **every**
call. It is reached by `GET /api/scenarios` (`src/PROJECT_N3_WEB/app.py:260-262`) and
by `/api/health` (`:77`).

Currently 6 artifacts / 180 KB, so negligible. It becomes the dominant cost as
variants accumulate — and a 20-variant batch adds 20 files, all re-parsed on
each subsequent list call. Cache keyed on `(artifact_root, count, max_mtime)`.

Do not add a database table for this. The files are the source of truth and the
invalidation is trivial.

---

## 6. Frontend/backend observations

Per F-B, every API call is proxied through the Vite dev server. For the demo
tier this disappears entirely, because a static bundle talks to a static host —
which is a further argument for the split proposed in
`docs/guides/security-deployment.md`.

The current frontend has no router and no route-level code splitting
(`frontend/package.json` has no `react-router`; `frontend/src/App.tsx` is a
single 101-line component). Adding an intro surface and a paginated catalog
means introducing routing and splitting the component. Worth doing deliberately
rather than by accretion, since the workspace shell is already dense.

---

## 7. Verification

Per `docs/README.md`, runtime claims require command, version, logs and
cleanup evidence.

| ID | Evidence required |
|---|---|
| D-1 | Cold start timing before/after; confirm `cache_built_now` is false on second boot |
| D-2 | `/api/health` responds sub-second while index is building; readiness state visible |
| D-3 | Timing for `limit=20` vs unpaginated 850; total count correct |
| D-4 | Container `id -u` is non-zero; project tree still writable |
| D-5 | `/api/source-scenes` returns 850; import still succeeds |
| D-6 | Concurrent query benchmark before/after |
| D-7 | `PRAGMA journal_mode` reports `wal` |
| D-8 | Correctness parity test: all 850 tokens resolve identically |
| D-9 | Listing N artifacts is not slower after warm-up |

## 8. Unverified

- No measurements have been taken yet. The 2.6 GB table sizes and the 787 MB
  cache file are observed facts; the resulting build duration is not measured.
- The container has not been started with these changes, so cache-volume
  permissions under a non-root user (D-4) are untested.
- Concurrent-read improvement from WAL (D-6) is expected but unbenchmarked.

## 9. Proposed execution order

1. D-1 (cache volume) — largest single win, smallest diff.
2. D-3 (pagination) — server plus catalog UI.
3. D-2 (lifespan) — removes the silent multi-minute hang.
4. D-4 (non-root) — pairs with the security work.
5. D-5 (trim mount).
6. D-9, D-8, D-6, D-7 — query-path tuning.

Awaiting owner approval before execution.