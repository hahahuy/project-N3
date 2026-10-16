# Security and Deployment Guide

Status: `CURRENT — LOCAL-TRUST APPLICATION; PUBLIC EXPOSURE STILL REQUIRES HARDENING`
Scope: public exposure of the Real2Scenario web application.
Authority: this document proposes changes. It does not modify current Plan A
scope, scientific contracts, or acceptance criteria.

Related: `docs/current/artifact-policy.md`, `docs/current/ui-mvp-flow-spec.md`,
`docs/guides/datastreaming.md`, `README.md` (deployment sections).

---

## 1. Summary

The current web application is a **single-user, local-trust deployment**. It has
no authentication, no authorization, no rate limiting and no multi-tenant
isolation. It is safe on loopback and on a trusted Tailscale network.

It is **not safe on the public internet as written**. Exposing the API directly
is equivalent to giving away remote code execution and arbitrary file read on
the host, independent of any bot or DDoS protection.

This guide recommends a two-tier deployment: a public read-only demo tier, and a
private full-capability tier that is never routed publicly.

---

## 2. Findings

Severity is rated for the case where the API is reachable by an unauthenticated
remote party.

### F-1 — CRITICAL: arbitrary file read via `POST /api/settings`

The settings endpoint is unauthenticated, so filesystem-root selection must be
confined even in the local-trust application.

- `src/r2s_web/config.py` confines artifact, output and dataset roots to the
  project root, existing configured roots or operator-declared extra roots.
- `POST /api/settings` remains unauthenticated and therefore must not be
  treated as a public deployment boundary.

An attacker can re-point the roots and then read files through the artifact
endpoint:

```bash
# 1. re-point the artifact root at an arbitrary absolute directory
curl -X POST http://target/api/settings \
  -H 'Content-Type: application/json' \
  -d '{"artifact_root": "/etc"}'

# 2. read any file under the new root
curl http://target/api/artifacts/passwd
```

`ArtifactAdapter.resolve_artifact` (`src/r2s_web/adapter.py:87-94`) correctly
confines reads to the configured roots — but the attacker controls those roots.
The check is sound; its inputs are not.

On the development host this includes `~/.ssh/id_ed25519`, `~/.docker/.token_seed`
and application secrets.

### F-2 — HIGH: unauthenticated compute with no concurrency limit

`POST /api/batches` (`src/r2s_web/app.py:843`) runs generation synchronously
 inside the request handler (`BatchService.create` → `self._run`, `src/r2s_web/jobs.py:86-95`).
There is no thread pool, no queue and no cap on concurrent jobs.

Consequences: request handlers block for the full generation duration, the
worker pool saturates under load, and `/api/replays` can spawn `esmini`
 subprocesses (`src/r2s_web/esmini.py:175-183`). This is the realistic
denial-of-service vector — not volumetric DDoS.

Note that returning HTTP `202 Accepted` while running synchronously is also
incorrect per its own contract.

### F-3 — HIGH: full dataset enumeration without pagination

`GET /api/source-scenes` (`src/r2s_web/app.py:409`) returns all scenes
unbounded. For `v1.0-trainval` that is 850 scenes, each triggering
`sample_tokens()` and `instance_tokens()` queries. Unauthenticated, this is a
cheap CPU-exhaustion lever and a free bulk scrape of dataset metadata.

### F-4 — MEDIUM: CORS is not an access control

`src/r2s_web/app.py:100-105` allowlists `localhost:5173` only. CORS is enforced by
browsers; `curl`, scripts and server-side clients ignore it. It prevents
accidental cross-origin use from a browser and provides no protection against
direct requests.

### F-5 — MEDIUM: dev container runs as root without a cache boundary

`Dockerfile.dev` declares no `USER`, so the container runs as root. By contrast
`Dockerfile` (production) correctly creates and switches to `appuser`. Any
process compromise in the dev container starts as root inside the container,
against a bind-mounted project tree.

### F-6 — INFORMATIONAL: local-trust assumptions are load-bearing

The design intent is documented and consistent: `README.md:169-171` states the
container is "intentionally a single-user local deployment... it does not add a
database, queue, or shared storage service". These are correct choices for the
stated scope. They become liabilities only under public exposure.

---

## 3. Recommended architecture

```text
                    Public internet
                          |
                 Cloudflare (WAF + Access)
                          |
        +-----------------+------------------+
        |                                    |
   DEMO TIER                            PRIVATE TIER
   static / DEMO_MODE=1                 Tailscale only
   read-only, no dataset                full capability
   contest submission                   hhf-server:5173
```

### 3.1 Public demo tier

The contest-facing surface. Properties:

- **No dataset mount.** nuScenes is non-commercial (`data/v1.0-mini/LICENSE`);
  no raw or derived artifact is served publicly.
- **No compute.** Every `POST/*` route and `/api/source-scenes*` returns 404.
- **Pre-baked content.** 3–5 real imported scenarios committed as static JSON,
  rendered by the existing frontend.
- **No origin to attack.** Static hosting behind Cloudflare; there is no
  application server, no database and no filesystem write path.

This is also the better presentation: no spinner, no dataset warm-up, instant
load, and deterministic output for judges.

### 3.2 Private tool tier

The existing stack, unchanged, reachable only over Tailscale
(`README.md:185`). F-1 through F-6 remain contained by the network boundary
rather than by code changes. This is the correct place for the open-tool
audience who are willing to run the stack locally.

---

## 4. Mandatory code fixes before any exposure

These apply to both tiers and are small, independently testable changes.

| ID | Change | File | Risk if skipped |
|---|---|---|---|
| S-1 | Constrain `dataset_root` to an allowlist | `src/r2s_web/config.py:67-98` | Complete; keep public exposure gated |
| S-2 | Constrain artifact/output roots to allowed roots | `src/r2s_web/config.py:67-140` | Complete; keep public exposure gated |
| S-3 | Make `POST /api/settings` env-only, or gate it behind auth | `src/r2s_web/app.py:378-407` | Re-arms F-1 |
| S-4 | Add `USER` to `Dockerfile.dev` matching production | `Dockerfile.dev` | Root in container |
| S-5 | Add `?limit=&offset=&q=` to `/api/source-scenes` | `src/r2s_web/app.py:409-414` | Enumeration + CPU burn |
| S-6 | Bound concurrent batch/replay jobs with a semaphore or queue | `src/r2s_web/jobs.py:86-95` | Trivial DoS |

S-1 and S-2 are the security-critical pair and should be treated as a single
defect class: *untrusted input must not select filesystem roots.*

The repository's own specification requires that availability and failures are
never silently degraded (`docs/current/ui-mvp-flow-spec.md:31-32`), and that
unsupported states carry an explicit reason (`:28-29`). F-1 is a direct
violation of that standard and should be tracked as a defect, not deferred.

---

## 5. Edge-layer controls

### 5.1 Chosen model — shared key at the reverse proxy

**Implemented.** See `docs/current/demo-hardening-backlog.md` section 4 for
runtime verification and `compose.demo.yml`, `ops/nginx/demo.conf` and
`ops/scripts/generate-demo-credentials.sh` for the build.

The committee has confirmed that a **shared access key** is an acceptable form
of access control for the contest demo. This is simpler than Cloudflare Access
and requires **no application code changes**, because authentication is handled
entirely by the reverse proxy in front of the frontend container.

Layered model:

```text
Attacker
   ↓
[1] TLS terminator (cloudflared)      required: basic auth is not encryption
   ↓
[2] HTTP Basic auth                   shared contest key, htpasswd file
   ↓
[3] WAF rate limit                    per-IP caps on /api/*
   ↓
[4] Internal Docker network           uvicorn NOT published to the host
   ↓
[5] S-1/S-2 code fixes                last line: untrusted input cannot
uvicorn                               select filesystem roots
```

#### Nginx configuration

Reference shape, matching the existing stack layout at
`/opt/stacks/hahuy.site/nginx.conf`:

```nginx
server {
  listen 443 ssl;
  server_name project-n3-prod.<domain>;

  auth_basic           "Real2Scenario Contest Demo";
  auth_basic_user_file /etc/nginx/.htpasswd;

  location / {
    proxy_pass http://frontend:5173;
    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
```

Credential generation:

```bash
htpasswd -Bc /etc/nginx/.htpasswd judge
```

#### Non-negotiable rules

1. **The key must never reach the frontend bundle.** If it is embedded in the
   React build it is public — anyone can read it from DevTools. Basic auth at
   the proxy keeps it server-side and out of `frontend/dist`.
2. **TLS is mandatory.** HTTP Basic sends credentials base64-encoded on every
   request. That is encoding, not encryption. Over plain HTTP the key is
   equivalent to plaintext.
3. **Only the key is a secret.** HTTP Basic auth always requires
   `user:password`, and nginx rejects an entry with an empty username (a correct
   key still returns 401 — verified). The username is therefore a fixed,
   non-secret constant, `r2s`. Judges receive exactly one string, the key, in
   any of these forms:

   ```text
   Browser prompt    username: r2s      password: <KEY>
   One-line form     r2s:<KEY>
   curl              curl -u 'r2s:<KEY>' https://project-n3.hahuy.cloud/
   ```

   The credential is stored at `ops/demo/secrets/htpasswd`, mode `0600`, with an
   ACL granting nginx workers (uid 101) read. It is gitignored and never enters
   the frontend bundle.

4. **The API port must not be published to the host.** `compose.dev.yml`
   currently binds `0.0.0.0:${R2S_WEB_API_PORT:-8001}:8000`. If that stays,
   the key protects nothing, because the backend can be reached directly and the
   proxy bypassed. The demo stack must place `api` and `frontend` on an
   internal-only network with no host port binding.
4. **Use a dedicated password.** Do not reuse a credential from another service
   on this host.
5. **Assume credential leakage in shared environments.** Browsers cache Basic
   auth credentials for the session. Share the URL with judges, not a shared
   workstation profile.

#### What this model does and does not solve

Solves:

- Anonymous internet access to the workspace and API.
- Bulk scraping of scenario metadata by unaffiliated parties.
- Casual abuse and drive-by load.

Does not solve:

- Revocation is manual — rotate by regenerating `htpasswd` and reloading nginx.
  Acceptable for a contest window, not for an open-ended public service.
- Brute force. Mitigate with WAF rate limiting and a high-entropy password.
- Resource exhaustion by an authenticated user. A judge who requests a
  1000-variant batch still saturates the host. **S-6 remains required.**
- Per-user identity. A shared key cannot rate-limit per person.

#### Effect on the S-series priority

The abuse surface shrinks from "anonymous internet" to "holders of a shared
credential". This re-prioritises but does not remove the remaining work:

| Item | Before | After |
|---|---|---|
| S-1/S-2 | critical | complete — committed to `HEAD` |
| S-6 batch job cap | critical | **recommended, not a launch blocker** |
| S-7 point-cloud bandwidth | high | medium |
| WAF rate limit | high | medium — cheap insurance, keep |
| D-3/S-5 pagination | high | **unchanged** — not a security control |

### 5.2 Decision — hashed Basic auth retained

Status: `DECIDED 2026-10-15 / do not redesign without a new decision`

An alternative was evaluated and **rejected**. This section exists so the
decision is not silently reversed by a later agent who mistakes a cosmetic
improvement for a security one.

#### Options considered

| | Hashed Basic auth (**chosen**) | Plaintext key in nginx config | Auth moved into FastAPI |
|---|---|---|---|
| Scraper can extract the key | No | No | No |
| Host file read yields | **hash** | **key** | key, or env var |
| `nginx -T` reveals the key | No | **Yes** — verified | n/a |
| `docker inspect` reveals the key | No | No | **Yes**, if stored in env |
| Key sits inside the app trust boundary | **No** | No | Yes |
| Single-field browser login possible | No | Yes | Yes |

#### Why hashed Basic auth won

A scraper cannot extract the key in **any** of these designs; they receive `401`
and stop. The difference is what happens after a host compromise:

- **Chosen:** the attacker obtains an APR1 hash and must still crack it
  offline. APR1 is MD5-based and weak against GPUs, but the key carries ~131
  bits of entropy, so this step is not practical. Hashing buys a real stage.
- **Plaintext nginx:** `nginx -T` prints the key verbatim from an included file.
  Verified on `nginx:1.27-alpine`:
  ```
  set $demo_key "PLAINTEXT_SECRET_abc123";   # appears in nginx -T output
  ```
  Anyone who can run that command has the key outright.
- **FastAPI:** no storage-security gain — an env var is printed by
  `docker inspect` (verified on this host), and a file is equivalent to the nginx
  case. It costs real protection by moving the key inside the application's
  trust boundary, where any future path traversal or SSRF becomes a credential
  leak. This codebase has had exactly such a bug: F-1, arbitrary file read via
  `POST /api/settings`, since fixed by S-1/S-2.

The only thing given up is a single-field browser prompt, which is cosmetic.

#### Current credential handling

| Property | Value |
|---|---|
| Location | `ops/demo/secrets/htpasswd` |
| Content | `r2s:$apr1$...` — username plus hash, never the key |
| Permissions | `0600`, plus an ACL granting nginx workers (uid 101) read |
| Git | ignored; a `git add -An` never selects it |
| Username | fixed constant `r2s`, not a secret |
| Logged | username only; verified 0 matches for the key or `Authorization` |

#### Leak vectors that outrank this design

Neither is about where the credential is stored:

1. **Browser credential caching.** HTTP Basic credentials persist for the
   session and may reach the OS credential store. On a shared machine the next
   person is authenticated. This is the most likely real leak.
2. **Embedding the key in a URL** — `https://r2s:KEY@host/`. It lands in
   browser history, clipboard, screenshots and chat. Give judges the bare key and
   have them type it into the prompt.
3. **Logging changes.** If anyone adds `$http_authorization` to a log format, or
   enables nginx debug logging, the key begins appearing in log files. The logs
   are clean today. **Do not add the `Authorization` header to any log format.**

#### If single-field login is ever genuinely required

The only design that provides it without persisting the key in plaintext:

```text
browser posts key -> FastAPI compares against a stored hash -> signed cookie
nginx auth_request validates the cookie
```

The key is never stored in plaintext and nginx only ever sees an opaque cookie.
This was not implemented: it adds an auth endpoint, session handling and cookie
flags, and puts auth logic inside the application — the property this decision
deliberately avoids. Raise it as a new decision rather than a refactor.

### 5.3 Cloudflare Access (alternative, not selected)

Retained for reference. Email/OTP or GitHub login in front of the origin. This
avoids the Basic-auth caching and revocation limitations but adds a per-judge
sign-in step and requires no shared secret. Not selected because the committee
accepted a key and the proxy approach requires no application changes.

### 5.4 Remaining edge controls

1. **WAF rate limit.** Rule: `http.request.uri.path starts_with "/api/"` →
   60 requests/minute per IP.
2. **Managed rules + Bot Fight Mode** for the demo tier only. Turnstile is
   appropriate for an anonymous interactive action; it is not a substitute for
   rate limiting or authentication.
3. **Origin lock.** If Cloudflare proxies the origin, restrict inbound to
   Cloudflare IPs so the edge cannot be bypassed.

Note that Cloudflare free plans do not cover arbitrary TCP; this design is
HTTP-only, which matches the application.

---

## 6. Licensing constraints on any public tier

Grounded in the license text at `data/v1.0-mini/LICENSE`, which is CC
BY-NC-SA 4.0 **plus additional Dataset Terms which prevail where they conflict**
(line 32).

**6.1 What the license actually permits.** Two clauses matter and both are
favourable to you:

- Line 286-293 — the grant is to "reproduce and Share the Licensed Material,
  in whole or in part, for NonCommercial purposes only" and to "produce,
  reproduce, and Share **Adapted Material** for NonCommercial purposes only."
- Line 262-268 — "Share" is defined broadly: "provide material to the public...
  including in ways that members of the public may access the material from a
  place and at a time individually chosen by them."

So publishing derived scenario JSON to a public website **is expressly
allowed**, provided it is NonCommercial. Line 21-22 confirms derived data in
any format, "tables and charts", is subject to these terms.

**6.2 The three real constraints.**

1. **NonCommercial (NC).** Not primarily directed toward commercial advantage or
   monetary compensation (line 254-255). A contest demo with no revenue and no
   sponsorship by a for-profit party is NC. A demo whose purpose is to attract
   customers or investors is not.
2. **Attribution (BY).** Must credit nuScenes/Motional and note the license.
   One line in the site footer and a `NOTICE` entry covers this.
3. **ShareAlike (SA).** Line 414-424: if you Share Adapted Material, you must
   license that adaptation under CC BY-NC-SA 4.0 **or a compatible license**, and
   may not impose further restrictions.

**6.3 The ShareAlike trap — this is the one that actually bites.**

`project-N3` source is Apache-2.0. That is unaffected — your *code* is yours.
But if the demo site serves trajectories derived from nuScenes, those
**derived data files become CC BY-NC-SA 4.0**, not Apache-2.0.

Practical consequence: you may not serve derived scenario JSON as
"unrestricted, do anything" assets, and you must not wrap it in terms that
claim more permissiveness than NC/SA. Keep the split clean:

- Code and pipeline → Apache-2.0 (unchanged).
- Derived scenario data files → CC BY-NC-SA 4.0, attributed, non-commercial,
  share-alike.
- Document this per-file or in the site footer. Do not mix them in one
  directory without a licence marker.

**6.4 What is still prohibited.**

- **Third-party carve-outs.** Lines 40-44: "Some datasets and indicators are
  provided by third parties and may not be redistributed or reused without the
  consent of the original data provider." If any nuScenes sample carries
  third-party content, it is out of scope regardless of the NC/SA grant. Check
  the specific scenes you plan to publish.
- **Endorsement and association.** Lines 61-72: you may not imply Motional
  participates in, sponsors or endorses your use, nor use their marks. Do not
  name the contest partner in a way that implies endorsement.
- **Warranty and takedown.** Lines 96-115 disclaim accuracy; lines 122-135 give
  Motional broad indemnity. Practical effect: publish a clear statement that
  demo artifacts are research outputs, not validated ground truth — which
  matches how your own docs already label results `PROVISIONAL`.
- **Termination.** Lines 74-80: access can be terminated at any time. A live
  contest demo should not hard-depend on dataset availability at runtime.

**6.5 Recommended posture for a public contest demo.**

Ship derived scenario JSON with an explicit CC BY-NC-SA 4.0 + attribution
notice. Verify the specific scenes have no third-party restrictions. Keep raw
nuScenes (camera images, LiDAR point clouds, sweeps) off the public tier
entirely — the license permits sharing them too, but they are large, they carry
the third-party risk, and they are not needed to show the workspace.

Note that `docs/current/platform-direction.md:79-80` states the platform
direction does not authorize publishing restricted data. That is a statement
about the *platform* scope, not a prohibition on an NC public demo. This guide
does not change Plan A acceptance criteria.

---

## 7. Verification

Per `docs/README.md`, no `DONE` claim from unit tests alone. Required evidence:

- Test proving S-1/S-2 reject `../`, absolute-outside-root and symlink-escape
  payloads with a verbatim API reason.
- Test proving S-6 caps concurrency under parallel requests.
- Unauthenticated `/api/batches` and `/api/settings` return 403 or 404.
- WAF rule screenshot with observed rate-limit events.
- Basic auth: unauthenticated request to the demo origin returns 401; the
  correct credential returns 200.
- Origin isolation: prove the API port is not reachable from the host network
  and not reachable without credentials. This is the control that makes the key
  meaningful; it must be verified explicitly, not assumed.
- TLS: confirm the demo origin serves HTTPS only and rejects plain HTTP.

## 8. Unverified

- No runtime testing has been performed against a public origin.
- The Basic-auth deployment in Section 5.1 is **documented but not built**. No
  demo stack, htpasswd credential or internal-only network exists yet.
- Origin isolation (API port unpublished) is **not yet true**: `compose.dev.yml`
  still binds `0.0.0.0:${R2S_WEB_API_PORT:-8001}:8000`.
- Third-party redistribution carve-outs (Section 6.4) have not been checked for
  the specific scenes selected for publication.
- Whether a given contest arrangement qualifies as NonCommercial is an owner
  and legal determination, not a technical one.

## 9. Open decisions for the owner

1. Demo tier shape. Recommendation remains `DEMO_MODE=1`; see Section 3.1 for
   the trade-off against full capability.
2. Access control. **Resolved: shared key via reverse proxy Basic auth
   (Section 5.1).** Remaining choice is whether the key is one shared credential
   or one per judge. Per-judge improves revocation and auditability at the cost
   of distribution overhead.
3. Owner and legal confirmation that the contest use is NonCommercial
   (Section 6.2).
4. Per-scene third-party carve-out check before publication (Section 6.4).
5. Whether the private tier remains the only place the full dataset is read.
6. `docs/current/project-status.md:116` states the project must not claim
   *public nuScenes artifact release*. Publishing derived scenario JSON to a
   contest demo appears to conflict with that line. This requires an explicit
   owner decision recorded in `docs/current/decisions.md`; it is not resolved
   by this guide.
