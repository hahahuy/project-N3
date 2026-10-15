# Production Push — Command Helper

Status: `CURRENT`
Scope: publishing a working development version to the product environment, and
rolling it back.
Audience: whoever is about to say "it works on dev, ship it".

Everything here is a command you can paste. Nothing here requires Docker or
Compose knowledge.

---

## 1. TL;DR

```bash
make rollback-check     # what is live right now?
make promote            # test, build, publish the frontend bundle
make revert SHA=3d2dfcf # roll back to a known-good commit
make status             # what is running in both environments
```

| Command | What it does |
|---|---|
| `make promote` | Runs the full test suite, builds the frontend bundle, publishes it |
| `make revert SHA=<commit>` | Rolls the **frontend** back to that commit and republishes |
| `make rollback-check` | Shows HEAD, uncommitted files, and the bundle currently live |
| `make status` | Lists containers in both environments |
| `make test` | 322 Python + 48 frontend tests |
| `make prod-rebuild` | Rebuilds **images** too — only for Dockerfile or dependency changes |
| `make key` | Rotates the contest key and certificate |
| `make dev-down` | **Stops the LAN exposure. Do this before a contest.** |

Run everything from the repository root.

---

## 2. Read this before your first push

**There is no promotion boundary for backend code.**

```
project-n3-api-1       - /app  <- repository root, bind mounted
project-n3-prod-api-1  - /app  <- the same source directory
prod CMD: uvicorn r2s_web.app:app ... --reload
```

Both stacks bind-mount the same repository directory at `/app`, and production
runs `--reload`. Therefore:

| Change | Reaches production |
|---|---|
| **Python / backend** — `src/**`, `pyproject.toml` | **Immediately, about 1 second, on save** |
| **Frontend** — `frontend/**` | Not until the bundle is rebuilt |

Both compose files mount the repository root read-write:

```yaml
# compose.dev.yml and compose.demo.yml
- .:/app
```

Consequences you must internalise:

- Editing `src/` in dev **already changed production** the moment you saved.
- `make promote` affects the **frontend only**.
- "I tested it on dev first" is not currently true for backend code. Dev and
  prod run the same bytes at the same instant.
- `make rollback-check` shows uncommitted backend edits that are **live**.

This is acceptable for a contest weekend and for iteration. It is not a safe
long-term arrangement. See Section 8.

---

## 3. Promoting

```bash
make promote
```

Runs, in order:

1. the full Python and frontend test suites — **aborts on failure**, so a broken
   bundle is never published;
2. `npm run build`, producing a frozen bundle in `frontend/dist/`;
3. `docker compose up -d` on the product stack only. Dev is untouched.

Then verify:

```bash
# without the key -> must be 401
curl -s -o /dev/null -w '%{http_code}\n' https://project-n3.hahuy.cloud/

# with the key -> must be 200
curl -s -u "r2s:<KEY>" -o /dev/null -w '%{http_code}\n' https://project-n3.hahuy.cloud/
```

Open `https://project-n3.hahuy.cloud` in a browser and click through one
scenario. A `200` on the root only proves the bundle loaded.

### If you changed a Dockerfile or a dependency

`make promote` does not rebuild images. Use:

```bash
make prod-rebuild
```

That rebuilds the frontend bundle **and** the container images, then recreates
the product stack.

### If you only changed backend code

You do not need to do anything. It is already live. Verify it instead:

```bash
make test
curl -s -u "r2s:<KEY>" https://project-n3.hahuy.cloud/api/health
```

---

## 4. Reverting

```bash
make revert SHA=3d2dfcf
```

This resets `frontend/` to that commit, rebuilds, and republishes. It validates
the commit first, so a typo fails safely:

```
$ make revert
usage: make revert SHA=<commit>

$ make revert SHA=deadbeef
unknown commit: deadbeef
```

### Known-good rollback points

```
3d2dfcf  Approve nuScenes devkit optimization
1134549  Document nuScenes evidence view direction
a789b6a  Verify native esmini runtime path
068100f  Complete sensor evidence and live runtime contracts   <- current HEAD
```

Take a note of the current commit **before** you start work:

```bash
git rev-parse --short HEAD    # this is your "known good"
```

### Reverting backend code

`make revert` does **not** touch `src/`. Uncommitted backend edits were never
committed, so there is nothing to check out. Inspect and discard manually:

```bash
git diff -- src/          # what is live in production right now
git checkout -- src/      # discard, back to the last commit
```

This takes effect immediately, via `--reload`. There is no undo step.

---

## 5. Before you push

```bash
make rollback-check       # confirm you know what you are shipping
make test                 # 322 Python + 48 frontend
make status               # both environments should be Up
```

Checklist:

- [ ] `git status` shows no unintended files
- [ ] `make test` passes
- [ ] `https://project-n3.hahuy.cloud` loads a scenario **with the key**
- [ ] one workflow exercised end to end, not just the landing page

---

## 6. Rolling back an incident

If the public site is broken and judges are watching:

```bash
# 1. find a known-good commit
git log --oneline -8

# 2. roll the frontend back
make revert SHA=<commit>

# 3. confirm recovery
curl -s -u "r2s:<KEY>" -o /dev/null -w '%{http_code}\n' https://project-n3.hahuy.cloud/
make status
```

If the **backend** is broken, `--reload` means you cannot easily un-break it
live. Safer: revert `src/` to the last commit, then

```bash
make prod-rebuild         # rebuild so the image is clean too
```

---

## 7. Environment reference

| | Development | Product |
|---|---|---|
| URL | `http://100.114.248.93:5173` | `https://project-n3.hahuy.cloud` |
| Compose file | `compose.dev.yml` | `compose.demo.yml` |
| Project name | `project-n3` | `project-n3-prod` |
| Frontend served | Vite dev server, live | frozen bundle in `frontend/dist` |
| Credential | none | Basic auth, username `r2s` |
| Container limits | none | api 4.0 CPU / memory unbounded |

| Item | Value |
|---|---|
| Credential file | `ops/demo/secrets/htpasswd` (`0600`, ACL for uid 101, gitignored) |
| Rotate the key | `make key`, then `make prod-rebuild` |
| Certificate | `ops/demo/certs/`, Cloudflare Origin CA, expires 2028-10-14 |
| Published ports | only `0.0.0.0:8443` (gateway). `api` and `frontend` publish none |
| Dev exposure | `0.0.0.0:8001` and `0.0.0.0:5173`, unauthenticated |

> **`make dev-down` before the contest.** While the development stack runs, the
> shared key protects the public route only — anyone on LAN or Tailscale can
> reach the app on `:8001` / `:5173` with no credential at all.

---

## 8. Known hazards

| Hazard | Symptom | Response |
|---|---|---|
| No backend promotion boundary | A dev typo breaks production on save | Revert `src/`, then `make prod-rebuild` |
| `uvicorn --reload` in production | A crashed worker is not respawned; container says `Up` while nothing listens, all requests `502` | `make prod-rebuild`; check `docker inspect ... .State.Health.Status` |
| No batch concurrency cap (S-6) | A large variant request saturates the host | Not yet implemented — see `docs/current/mission-batch-concurrency-benchmark.md` |
| Host reboot | Dev stack has `restart: unless-stopped` since 2026-10-15 and recovers; other stacks vary | `make status` |
| API memory is unbounded | A leak in a judge-facing endpoint could affect `banking-agent` or `kavita` | Owner-accepted; watch `docker stats` |

### Recommended fix, not yet applied

Point the product stack at the production `Dockerfile`, which already exists,
has no `--reload`, and runs as non-root. That creates a real promotion boundary
and eliminates the crashed-worker class of failure. Until then, treat `src/` as
live production code.

---

## 9. Related

- `docs/current/environment-environments.md` — how the two environments differ
- `docs/current/demo-hardening-backlog.md` — public-exposure hardening status
- `docs/guides/security-deployment.md` — shared-key design and the credential decision
- `docs/current/mission-batch-concurrency-benchmark.md` — S-6
- `Makefile` — every target, with `make help`

## 10. Unverified

- `make promote` and `make revert` were smoke-tested for argument handling and
  build steps, not through a full publish-and-rollback cycle with a real
  regression.
- Reverting a commit that predates the `frontend/dist` build layout has not been
  tested.
- No CI runs these commands; they depend on local Docker state.