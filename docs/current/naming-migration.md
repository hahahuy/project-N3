# Naming Migration — `r2s` to `project-N3`

Status: `COMPLETE / PARTIAL BY DESIGN`
Date: 2026-10-15

The repository is named `project-N3`. Its deployment identifiers previously used
an `r2s` prefix inherited from the working title "Real2Scenario". This note
records what was renamed, what was deliberately **not** renamed, and why.

Related: `docs/current/environment-environments.md`,
`docs/guides/datastreaming.md`, `docs/guides/security-deployment.md`.

---

## 1. What was renamed

### Environment variables

The `R2S_` prefix became `PROJECT_N3_`. These are read by application code, so
code and infrastructure were changed together.

| Old | New |
|---|---|
| `R2S_PROJECT_ROOT` | `PROJECT_N3_ROOT` |
| `R2S_ARTIFACT_ROOT` | `PROJECT_N3_ARTIFACT_ROOT` |
| `R2S_OUTPUT_ROOT` | `PROJECT_N3_OUTPUT_ROOT` |
| `R2S_METADATA_CACHE` | `PROJECT_N3_METADATA_CACHE` |
| `R2S_EXTRA_DATA_ROOTS` | `PROJECT_N3_EXTRA_DATA_ROOTS` |
| `R2S_WEB_API_PORT` | `PROJECT_N3_WEB_API_PORT` |
| `R2S_WEB_FRONTEND_PORT` | `PROJECT_N3_WEB_FRONTEND_PORT` |
| `R2S_UID` / `R2S_GID` | `PROJECT_N3_UID` / `PROJECT_N3_GID` |
| `R2S_DEMO_HOSTNAME` | `PROJECT_N3_DEMO_HOSTNAME` |
| `R2S_DEMO_HTTPS_PORT` | `PROJECT_N3_DEMO_HTTPS_PORT` |

Files touched: `src/r2s_web/config.py`, `src/r2s_web/source_scenes.py`,
`compose.dev.yml`, `compose.demo.yml`, `Dockerfile`, `Dockerfile.dev`,
`tests/test_web_api.py`, `Makefile`, `ops/`, and the guides under `docs/`.

### Docker identifiers

| Old | New |
|---|---|
| compose project `r2s-demo` | `project-n3-prod` |
| `r2s-metadata-cache` | `project-n3-metadata-cache` (shared) |
| `r2s-prod-scenarios` | `project-n3-prod-scenarios` |
| `r2s-reports` (product) | `project-n3-prod-reports` |
| `r2s-reports` (development) | `project-n3-dev-reports` |
| `demo-logs` | `project-n3-prod-logs` |
| `frontend-node-modules` (product) | `project-n3-prod-node-modules` |
| `frontend-node-modules` (development) | `project-n3-dev-node-modules` |

Volume contents were migrated rather than rebuilt: the 787 MB metadata index and
the 7 seeded product scenarios were copied into the renamed volumes.

## 2. What was deliberately NOT renamed

Three categories of `r2s` identifiers remain. They are **not** project naming.
Changing them would break contracts or history.

### 2.1 Artifact format versions — must not change

```python
OPENDRIVE_SUBSET_VERSION = "r2s-odr-subset-v1"   # src/real2scenario/mapbuilder/__init__.py:15
XOSC_SUBSET_VERSION     = "r2s-xosc-subset-v1"   # src/real2scenario/xosc_subset.py:11
```

These are **format identifiers**, not project names. They are written into every
generated artifact (`mapbuilder/__init__.py:85`, `:320`) and validated by
`gates.py:220`. Renaming them would silently change the identity of all existing
artifacts and recorded evidence, which is a contract change, not a cosmetic one.
It requires a version bump and owner approval, not a find-and-replace.

Related format identifiers that follow the same pattern and must also stay:
`r2s-xosc-interpreter-v1`, `r2s-lidar-metadata`, `r2s-clean-checkout-*`.

### 2.2 Evidence record identifiers

`r2s-100` through `r2s-505` are identifiers for recorded evidence documents under
`docs/evidence/`. They are referenced from reports, the evidence index and
handoff notes. Renaming them would invalidate the claim-to-report mapping in
`docs/current/evidence-index.md`.

The distribution name in `pyproject.toml` is `real2scenario`, and the product
name used throughout documentation is "Real2Scenario". The evidence prefix is
historical and harmless.

### 2.3 The Python package `r2s_web`

`src/r2s_web/` is the FastAPI application package, referenced ~100 times.

Renaming it is mechanically possible but was judged not worth the risk:

- it requires renaming the directory, all imports, the Dockerfile entrypoint
  (`r2s_web.app:app`) and a full image rebuild;
- it touches the code path that serves the live contest route;
- the distribution is already named `real2scenario`, so `r2s` is an internal
  abbreviation rather than the project's public name.

If a rename is wanted later, it should be its own change with the full test suite
run against a rebuilt image, not folded into infrastructure work.

## 3. The volume-name defect discovered during migration

Renaming the compose project revealed a latent defect worth recording, because
it silently produces the wrong storage.

**Symptom.** `compose.demo.yml` declared:

```yaml
volumes:
  project-n3-prod-scenarios:
```

Docker Compose prefixes undeclared volume names with the project name, so the
actual volume became:

```
project-n3-prod_project-n3-prod-scenarios
```

Data was written to a volume named `project-n3-prod-scenarios` (created manually
by the agent), which nothing mounted. The result was a container with an **empty**
`/app/scenarios` and `/api/scenarios` returning `0`, while `docker volume ls`
showed a correctly-named volume that nobody used.

**Why it matters.** The failure is silent. The stack starts healthy, the health
check passes, and only the data is missing. It was caught only because the
scenario count was verified against a known value rather than trusting a `200`.

**Fix applied.** Every volume now declares an explicit `name:`, so the project
prefix is never applied:

```yaml
volumes:
  project-n3-prod-scenarios:
    name: project-n3-prod-scenarios
```

**Related risks in this repository.** The same class of bug — a name that looks
right and silently resolves elsewhere — has three siblings worth checking when
changing deployment:

| Risk | Where | Why |
|---|---|---|
| Container name collisions | `docker ps` | Both compose files originally derived the project name from the directory, so `compose.demo.yml` silently replaced the running development containers |
| Environment variable mismatch | `PROJECT_N3_*` vs image | Renaming an env var without rebuilding the image leaves the container setting the old name. Observed: `Permission denied: '/.cache'` because the image still exported `R2S_METADATA_CACHE` while the code read `PROJECT_N3_METADATA_CACHE` |
| Port already allocated | `docker ps` | A stale container from a previous project name holds the published port and blocks startup |

**Habit this argues for.** After any deployment change, verify *content*, not
just status: check that a known scenario is present and a known endpoint returns
the expected count. `make prod` prints a URL but does not assert data.

## 4. Verification

| Check | Result |
|---|---|
| Public route without credential | `401` |
| Public route with credential | `200` |
| `/api/scenarios` through the gateway | 7 scenarios |
| `/api/source-scenes` through the gateway | 850 scenes |
| Development route `100.114.248.93:5173` | `200` |
| Development API `100.114.248.93:8001/api/health` | `200` |
| Container names | `project-n3-prod-*`, `project-n3-*` |
| Volume names | `project-n3-*`, no project prefix duplication |
| Python suite | 322 passed |
| Documentation consistency | PASS |

## 5. Unverified

- The rename was not exercised under concurrent load.
- Docker networks keep their original names (`project-n3_default`,
  `project-n3-prod_demo`). Networks are recreated per stack and were left alone
  deliberately; renaming them has no functional benefit.
- No environment outside this host consumes the `PROJECT_N3_*` variables. If
  another host or CI job sets `R2S_*`, it must be updated; no such consumer was
  found in this repository.
