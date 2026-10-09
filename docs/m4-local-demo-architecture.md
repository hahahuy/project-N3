# M4 Local Web Demo Architecture

## Decision

M4 is a local, browser-based demo that runs on the current machine. It is not
the first version of the shared internal platform.

The demo uses a FastAPI backend and a React frontend so the web boundary is
real from the beginning. Generation, validation, ranking, export, and optional
esmini replay run as local processes using the machine's CPU and installed
tools. The browser connects to `localhost`.

This keeps M4 small while preserving a migration path to a customer-facing
deployment later.

## M4 Scope

```text
React browser
    |
    | localhost HTTP/JSON
    v
FastAPI application
    |
    +-- load local scenario artifacts
    +-- invoke existing real2scenario APIs
    +-- run bounded local jobs
    +-- expose job status and artifact links
    |
    v
Local filesystem
    +-- canonical scenario JSON
    +-- generated variant JSON
    +-- OpenSCENARIO XML
    +-- replay CSV and reports
```

M4 should include:

- A local startup command for the API and frontend.
- Scenario loading and provenance display.
- Recorded, replayed, and generated trajectory views.
- Deterministic batch configuration and generation.
- Validation before ranking.
- Separate valid, invalid, and simulator-failed states.
- Artifact export/download from the local output directory.
- Synthetic-fixture smoke tests and one documented local-data demo path.

M4 should not include:

- Shared-server deployment.
- Object storage or PostgreSQL.
- Distributed job queues or worker pools.
- Customer authentication or multi-user permissions.
- A workstation execution agent.
- Required GPU infrastructure.

For a single-user local demo, authentication is intentionally omitted. The
later internal platform may add simple local accounts, project membership, and
roles without changing the scenario or report contracts.

## Boundary Rules

FastAPI is an orchestration boundary, not a second domain implementation. It
must call public functions from `real2scenario` and must not duplicate:

- Trajectory transformation math.
- Variant ID generation.
- Validation thresholds.
- TTC or ranking calculations.
- Report reconciliation.

The backend adapter should map domain objects to API response models. A local
job record should preserve the input scenario ID, configuration, seed, software
versions, status, errors, and output artifact paths.

The frontend should consume API responses rather than read Python artifacts or
filesystem paths directly. This makes the later shared deployment a transport
and infrastructure change instead of a UI rewrite.

## User-Visible Workflow

The user should experience one browser flow rather than separate technical
tools:

1. Open the local web application.
2. Select a scenario artifact from the local catalog.
3. Inspect provenance, actors, duration, coordinate frame, and recorded path.
4. Inspect baseline replay and fidelity metrics when replay output exists.
5. Configure speed, gap, timing, batch size, and seed.
6. Start generation from the browser and watch the local job status.
7. Review validation results before any ranking score.
8. Inspect valid, invalid, and simulator-failed results separately.
9. Open a result detail view with path overlays, metrics, configuration, and
   provenance.
10. Download the selected JSON, `.xosc`, trace, and report artifacts.

React owns presentation and user interaction. FastAPI owns loading, invoking
the canonical APIs, running local operations, and returning structured status
and artifact references. The browser never imports Python code or interprets
the local artifact directory itself.

## Deferred Platform Add-On

The future customer/internal platform can add these components behind the same
API and job contracts:

```text
React browser
    |
    v
FastAPI service with local accounts and project permissions
    |
    +-- PostgreSQL metadata
    +-- S3-compatible object storage
    +-- queued worker execution
    +-- optional local-agent execution backend
```

The deferred platform should provide:

- Local accounts with secure password hashing and session/token handling.
- Project-level permissions: owner, editor, and viewer.
- Persistent job history and audit metadata.
- Object storage behind an `ArtifactStore` interface.
- Server-side workers with bounded concurrency.
- An optional local-agent backend for customer machines with private data or
  specialized CPU/GPU requirements.

The local demo should define interfaces and stable identifiers where cheap, but
must not implement these platform components prematurely.

## Compute Policy

M4 uses CPU execution on the current machine. Browser-side GPU acceleration may
be used naturally for rendering charts or WebGL views, but no GPU is required
to run the pipeline.

Server GPU and workstation-agent execution remain add-ons. They should only be
implemented after profiling or customer data policy demonstrates a need.

## Storage Policy

M4 uses a project-relative local output directory and must avoid absolute paths
in committed artifacts or documentation. The artifact layout should remain
compatible with a future `ArtifactStore` abstraction.

The platform migration will move large files to S3-compatible storage while
keeping searchable metadata in a database. That migration is outside M4.

## Acceptance Boundary

M4 is successful when a reviewer can start the local web application, load a
known fixture, generate and validate a deterministic batch, inspect ranking and
replay information, and download the resulting artifacts without editing files
or using a second terminal after startup.

Customer deployment, multi-user access, private shared storage, and hybrid
execution are explicitly post-M4 add-ons.
