# Security and Deployment Guide

Status: `PROPOSED — NOT IMPLEMENTED`
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

`WebSettings.with_paths` accepts attacker-controlled path roots without
containment.

- `src/r2s_web/config.py:70-74` — `dataset_root` is passed through
  `Path(...).expanduser().resolve()` with **no validation at all**.
- `src/r2s_web/config.py:64-69` — `artifact_root` and `output_root` use
  `_project_path`, which at `src/r2s_web/config.py:79-81` returns
  `path.resolve()` unchanged whenever `path.is_absolute()`. Containment only
  applies to relative paths.
- The endpoint is unauthenticated: `src/r2s_web/app.py:209`.

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

`ArtifactAdapter.resolve_artifact` (`src/r2s_web/adapter.py:86-93`) correctly
confines reads to the configured roots — but the attacker controls those roots.
The check is sound; its inputs are not.

On the development host this includes `~/.ssh/id_ed25519`, `~/.docker/.token_seed`
and application secrets.

### F-2 — HIGH: unauthenticated compute with no concurrency limit

`POST /api/batches` (`src/r2s_web/app.py:383`) runs generation synchronously
inside the request handler (`BatchService.create` → `self._run`, `src/r2s_web/jobs.py:85-94`).
There is no thread pool, no queue and no cap on concurrent jobs.

Consequences: request handlers block for the full generation duration, the
worker pool saturates under load, and `/api/replays` can spawn `esmini`
subprocesses (`src/r2s_web/esmini.py:173-176`). This is the realistic
denial-of-service vector — not volumetric DDoS.

Note that returning HTTP `202 Accepted` while running synchronously is also
incorrect per its own contract.

### F-3 — HIGH: full dataset enumeration without pagination

`GET /api/source-scenes` (`src/r2s_web/app.py:234`) returns all scenes
unbounded. For `v1.0-trainval` that is 850 scenes, each triggering
`sample_tokens()` and `instance_tokens()` queries. Unauthenticated, this is a
cheap CPU-exhaustion lever and a free bulk scrape of dataset metadata.

### F-4 — MEDIUM: CORS is not an access control

`src/r2s_web/app.py:59-64` allowlists `localhost:5173` only. CORS is enforced by
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
| S-1 | Constrain `dataset_root` to an allowlist or `_project_path` containment | `src/r2s_web/config.py:70-74` | Arbitrary path probing |
| S-2 | Constrain absolute `artifact_root`/`output_root` to `project_root` | `src/r2s_web/config.py:79-81` | Arbitrary file read |
| S-3 | Make `POST /api/settings` env-only, or gate it behind auth | `src/r2s_web/app.py:209` | Re-arms F-1 |
| S-4 | Add `USER` to `Dockerfile.dev` matching production | `Dockerfile.dev` | Root in container |
| S-5 | Add `?limit=&offset=&q=` to `/api/source-scenes` | `src/r2s_web/app.py:234` | Enumeration + CPU burn |
| S-6 | Bound concurrent batch/replay jobs with a semaphore or queue | `src/r2s_web/jobs.py:85` | Trivial DoS |

S-1 and S-2 are the security-critical pair and should be treated as a single
defect class: *untrusted input must not select filesystem roots.*

The repository's own specification requires that availability and failures are
never silently degraded (`docs/current/ui-mvp-flow-spec.md:31-32`), and that
unsupported states carry an explicit reason (`:28-29`). F-1 is a direct
violation of that standard and should be tracked as a defect, not deferred.

---

## 5. Edge-layer controls

Only relevant to the demo tier, and only useful **after** Access is in place.

1. **Cloudflare Access (Zero Trust → Access → self-hosted).** Email/OTP or
   GitHub login in front of the origin. This is the single highest-value
   control: it authenticates before traffic reaches uvicorn, which is cheaper
   and safer than adding auth to the application.
2. **WAF rate limit.** Rule: `http.request.uri.path starts_with "/api/"` →
   60 requests/minute per IP. Add an explicit deny for `/api/batches` and
   `/api/settings` from unauthenticated identities.
3. **Managed rules + Bot Fight Mode** for the demo tier only. Turnstile is
   appropriate for an anonymous interactive action; it is not a substitute for
   rate limiting or authentication.
4. **Origin lock.** Restrict the origin to Cloudflare IPs so the backend cannot
   be reached by bypassing the edge.

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

## 8. Unverified

- No runtime testing has been performed against a public origin.
- Cloudflare Access and WAF behaviour must be confirmed in the actual account.
- Third-party redistribution carve-outs (Section 6.4) have not been checked for
  the specific scenes selected for publication.
- Whether a given contest arrangement qualifies as NonCommercial is an owner
  and legal determination, not a technical one.

## 9. Open decisions for the owner

1. Demo tier static-host, or `DEMO_MODE=1` read-only container? See Section 3.1;
   with a public audience this matters more, and the recommendation is
   `DEMO_MODE=1` because it preserves backend-derived provenance while removing
   the write surface.
2. Access policy: Cloudflare Access in front of the demo origin, or rely on
   WAF + rate limiting alone given the audience is public?
3. Owner and legal confirmation that the contest use is NonCommercial
   (Section 6.2).
4. Per-scene third-party carve-out check before publication (Section 6.4).
5. Whether the private tier remains the only place the full dataset is read.