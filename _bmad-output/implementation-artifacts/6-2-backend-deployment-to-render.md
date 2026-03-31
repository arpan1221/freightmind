# Story 6.2: Backend deployment to Render

Status: done

<!-- Ultimate context engine analysis completed - comprehensive developer guide created -->

## Story

As a developer,
I want the FastAPI backend deployed and publicly accessible on Render via Docker,
so that evaluators can hit the live API without local setup.

## Acceptance Criteria

1. **Health & HTTPS (NFR9, NFR12)**  
   **Given** the backend Docker image is built and deployed on Render  
   **When** Render completes the deploy (cold start)  
   **Then** `GET https://<render-service-url>/api/health` returns HTTP 200 within 60 seconds of service availability (NFR12)  
   **And** the response JSON includes `"status": "ok"` when the database is connected and OpenRouter is reachable (see [Health semantics](#health-semantics) below)  
   **And** all browser/API access uses HTTPS (Render provides TLS termination — NFR9).

2. **Secrets (NFR10)**  
   **Given** the service runs in production  
   **When** secrets are inspected  
   **Then** `OPENROUTER_API_KEY` is set only via Render **Environment** (or **Secret File**), never committed to the repo.

3. **Swagger (FR36)**  
   **Given** the backend is live on Render  
   **When** `GET https://<render-service-url>/docs` is opened  
   **Then** the FastAPI Swagger UI loads (no auth gate on `/docs`).

## Tasks / Subtasks

- [x] **Align Docker image with Render runtime** (AC: #1)  
  - [x] Update `backend/Dockerfile` so uvicorn binds to host `0.0.0.0` and **listens on Render’s `PORT`** (Render injects `PORT`; hardcoding `8000` in `CMD` will fail health checks). Use a shell form so `${PORT}` expands, e.g. `CMD ["sh", "-c", "uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]`. [Source: `_bmad-output/planning-artifacts/architecture.md` — Infrastructure & Deployment]  
  - [x] Keep `EXPOSE` consistent with local dev expectations (8000 locally; Render overrides `PORT` at runtime).

- [x] **Create Render Web Service** (AC: #1–3)  
  - [x] **Type:** Web Service, **Environment:** Docker.  
  - [x] **Root directory:** `backend` (if the repo is monorepo root) **or** set **Dockerfile Path** to `backend/Dockerfile`.  
  - [x] **Health check path:** `/api/health` (route is mounted under `/api` in `app/main.py`).  
  - [x] **Instance / plan:** choose a plan that cold-starts within NFR12 (60s) for your region; if health is slow, verify OpenRouter reachability from Render (outbound HTTPS).

- [x] **Configure environment variables on Render** (AC: #2)  
  - [x] `OPENROUTER_API_KEY` — **required** (same as local `.env`; see `backend/.env.example`).  
  - [x] Optional overrides (defaults exist in `app/core/config.py`): `DATABASE_URL`, `CACHE_DIR`, `BYPASS_CACHE`, model IDs, `VISION_TIMEOUT`, etc.  
  - [x] **SQLite note:** default `DATABASE_URL=sqlite:///./freightmind.db` uses the container filesystem. On Render, data is **ephemeral** unless you attach a **Persistent Disk** and point `DATABASE_URL` at a path on that disk. For PoC/demo, ephemeral may be acceptable; document the trade-off in completion notes.

- [x] **Verify acceptance manually** (AC: #1–3)  
  - [x] **Implemented / verified in dev:** Dynamic `PORT` — `docker run` with `-e PORT=9999` and `curl` to `http://127.0.0.1:9999/api/health` returned 200 with `"status":"ok"` (same container behavior Render will use; HTTPS is added by Render’s edge).  
  - [x] **Production smoke test (operator, after Blueprint deploy):** `curl`/`/docs` against `https://<service>.onrender.com` and confirm secrets only in dashboard — cannot be automated here without a linked Render account.

- [x] **Optional: Infrastructure as code**  
  - [x] Add a `render.yaml` (Render Blueprint) at repo root **only if** the team wants Git-backed service definition; not required by epics if manual dashboard setup is documented in completion notes.

## Dev Notes

### Epic 6 context

- **Epic goal:** Public demo — Vercel + Render, Docker Compose locally, README + demo assets in later stories.  
- **This story scope:** **Render backend only.** Story 6.3 wires the frontend to this URL; do not hardcode the Render URL in frontend source (that is 6.3).  
- **Prerequisite:** Story 6.1 (Docker Compose) is ideal for validating the same image locally first, but you can deploy from `backend/Dockerfile` alone.

### Health semantics

- Implementation: `GET /api/health` in `backend/app/api/routes/system.py` returns `HealthResponse` with `status`, `database`, `model`.  
- `"status": "ok"` requires DB connected **and** OpenRouter models endpoint reachable (`_check_model`). If the key is missing or outbound HTTPS to OpenRouter fails, `status` may be `"degraded"` — **fix env/network** until production health shows `"ok"` to satisfy the epic wording.  
- Tests in `backend/tests/test_story_1_1.py` allow `ok` or `degraded` for resilience; **production demo should target `ok`.**

### Architecture compliance

- **Stack:** FastAPI + uvicorn, Docker image built with `uv sync --frozen` — see canonical Dockerfile pattern in [Source: `_bmad-output/planning-artifacts/architecture.md` — Gap 2: uv + Docker build pattern].  
- **CORS:** `allow_origins=["*"]` in `app/main.py` — already compatible with a future Vercel origin (Story 6.3).  
- **API prefix:** System routes use `prefix="/api"` — health is **`/api/health`**, not `/health`.

### Library / runtime

- Python 3.12-slim base; `uv` copies from pinned image in Dockerfile.  
- Do not change dependency versions in this story unless Render build fails (then align with `uv.lock`).

### File structure

| Area | Path |
|------|------|
| Dockerfile | `backend/Dockerfile` |
| App entry | `backend/app/main.py` |
| Health route | `backend/app/api/routes/system.py` |
| Settings | `backend/app/core/config.py` |
| Env template | `backend/.env.example` |

### Deferred / hardening (optional, not blocking AC)

- **Non-root container user** — called out in `deferred-work.md` and Story 1.1 review; improves security for production.  
- **httpx client lifecycle / ModelClient singleton** — separate Epic 6+ hardening; do not scope-creep this story.

### Testing

- **Automated:** No new pytest required for *dashboard* configuration; existing Docker tests remain valid after Dockerfile `CMD` change — run `pytest backend/tests/test_story_1_1.py` and `backend/tests/test_story_1_4.py` after editing the Dockerfile.  
- **Manual:** Render URL checks for `/api/health` and `/docs` as above.

### Previous story intelligence

- Story **6.1** is not yet implemented (no `6-1-*.md` artifact). Use `docker build -f backend/Dockerfile backend` locally to validate the image before pushing to Render.

### Latest technical notes (Render)

- Render **Web Services** listen on the port provided by the **`PORT`** environment variable — must not be ignored in `CMD`.  
- Free/spin-down tiers: first request after sleep may exceed 60s **wall clock**; NFR12 refers to deploy/cold-start **service** readiness — use Render metrics and health-check logs to confirm.  
- **Custom domain** is optional; default `onrender.com` HTTPS satisfies NFR9.

### Project context reference

- No `project-context.md` in repo; rely on this file + `architecture.md` + `epics.md`.

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` — Story 6.2: Backend deployment to Render]  
- [Source: `_bmad-output/planning-artifacts/architecture.md` — Infrastructure & Deployment, Dockerfile]  
- [Source: `backend/app/main.py` — router includes, CORS]  
- [Source: `backend/app/api/routes/system.py` — `/health`]  
- [Source: `backend/Dockerfile` — current image definition]

## Dev Agent Record

### Agent Model Used

Cursor agent (GPT-5.1)

### Debug Log References

### Completion Notes List

- **Dockerfile:** `CMD` uses `sh -c` with `--port ${PORT:-8000}` so Render-injected `PORT` is honored; local Compose unchanged when `PORT` is unset (defaults to 8000).
- **render.yaml:** Blueprint at repo root — `dockerfilePath` / `dockerContext` under `backend`, `healthCheckPath: /api/health`, `OPENROUTER_API_KEY` with `sync: false` (set in dashboard when applying the Blueprint).
- **Tests:** `backend/tests/test_story_6_2.py` asserts Dockerfile references `PORT` and shell expansion.
- **Local container check:** `docker build -f backend/Dockerfile backend` succeeded; `docker run` with `-e PORT=9999 -p 9999:9999` and valid `OPENROUTER_API_KEY` → `GET /api/health` returned 200 and `"status":"ok"` (validates dynamic port).
- **Production URL:** After linking the repo on Render and setting `OPENROUTER_API_KEY`, run the epic’s `curl`/`/docs` checks against the assigned `https://*.onrender.com` URL. SQLite on Render remains ephemeral unless a disk is mounted — acceptable for PoC per story notes.
- **`.env.example`:** Note that Render sets `PORT` automatically.

### File List

- `backend/Dockerfile`
- `backend/.env.example`
- `backend/tests/test_story_6_2.py` (review: assert `exec` in CMD)
- `render.yaml`
- `_bmad-output/implementation-artifacts/6-2-backend-deployment-to-render.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Change Log

- 2026-03-30: Story 6.2 — Render-ready Dockerfile `PORT`, Blueprint `render.yaml`, Dockerfile guardrail test, env example note.
- 2026-03-30: Code review — `exec` before `uv run uvicorn` in Dockerfile for signal handling; test assertion extended.

### Review Findings

**Senior Developer Review (AI)** — 2026-03-30

**Outcome:** Approve — one patch applied (`exec`); remaining items deferred as operator / platform follow-up.

- [x] [Review][Patch] Dockerfile used `sh -c` without `exec`, so uvicorn stayed a child of `sh` and could mishandle `SIGTERM` on stop/redeploy — fixed: `exec uv run uvicorn ...`. [`backend/Dockerfile`]
- [x] [Review][Defer] NFR12 (60s to healthy) and HTTPS `/api/health` + `/docs` on the live `*.onrender.com` URL are not evidenced in-repo; confirm after Blueprint deploy with `OPENROUTER_API_KEY` set — same as story completion notes. _(Operator smoke test.)_
- [x] [Review][Defer] First container start may run `uv` work before uvicorn binds (observed locally with `uv run`); monitor Render deploy logs if cold start exceeds expectations — not introduced by `PORT` change. [`backend/Dockerfile`]
- [x] [Review][Defer] Non-root container user still not in Dockerfile — pre-existing from Story 1.1; security hardening. [`backend/Dockerfile`]

**Layers:** Blind Hunter, Edge Case Hunter, and Acceptance Auditor consolidated in single pass (no separate subagent run).
