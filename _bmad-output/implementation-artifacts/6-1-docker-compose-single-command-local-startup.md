# Story 6.1: Docker Compose — single command local startup

Status: done

<!-- Ultimate context engine analysis completed — comprehensive developer guide created -->

## Story

As a developer,
I want a `docker-compose.yml` at the repo root that wires the backend and frontend together,
so that the full system can be started locally with a single command from a cold clone.

## Acceptance Criteria

1. **Cold clone + env + single command (FR / Epic 6.1)**  
   **Given** the developer clones the repo, copies `.env.example` to `.env` at the **repo root** (see [Source: `.env.example`]), and fills in `OPENROUTER_API_KEY`  
   **When** they run `docker compose up` or `docker-compose up` (document both in dev notes; Compose V2 vs legacy CLI)  
   **Then** both the backend (host port **8000**) and frontend (host port **3000**) start without errors  
   **And** the frontend running in the **browser** can successfully call backend API routes (CORS `allow_origins=["*"]` — already in [Source: `backend/app/main.py`])  
   **And** `GET http://localhost:8000/api/health` returns JSON that includes **`"status": "ok"`** when the database is connected and the OpenRouter reachability check succeeds  

   **Note:** The live `HealthResponse` also includes `database` and `model` fields ([Source: `backend/app/schemas/common.py`, `backend/app/api/routes/system.py`]). The epic’s minimal `{"status": "ok"}` check should be interpreted as: response body must contain `status: "ok"` in the healthy case — do not strip extra fields.

2. **Cold build — no manual install steps**  
   **Given** the developer runs compose on a machine that has **never** built these images  
   **When** the build completes  
   **Then** dependencies are installed from **`backend/pyproject.toml` + `backend/uv.lock`** and **`frontend/package.json` + `frontend/pnpm-lock.yaml`** via the Dockerfiles — **no** host-side `uv sync` / `pnpm install` required  

3. **Browser → API URL (critical)**  
   **Given** the user opens `http://localhost:3000` on the host  
   **When** the SPA calls the API from client-side JavaScript  
   **Then** `NEXT_PUBLIC_BACKEND_URL` baked at **frontend image build** must resolve to the backend **as seen from the browser** — i.e. **`http://localhost:8000`**, not the Docker service name `http://backend:8000` (the browser does not resolve the Compose service DNS). Current [Source: `docker-compose.yml`] passes `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000` as a build arg — preserve or replace with equivalent; **do not** break this without an intentional alternative (e.g. reverse proxy on localhost).

## Tasks / Subtasks

- [x] **Task 1 — Baseline audit vs architecture (AC: 1–3)**  
  - [x] Compare root [Source: `docker-compose.yml`] to the canonical structure in [Source: `_bmad-output/planning-artifacts/architecture.md` § Infrastructure & Deployment — Docker Compose structure].  
  - [x] Resolve discrepancies: e.g. architecture snippet shows `env_file: ./backend/.env`; repo uses **root** `.env` via `env_file: .env` aligned with [Source: `.env.example`]. Pick one documented approach; update **either** compose **or** architecture snippet in README/story follow-up (Epic 6.5) — for this story, **working compose + root `.env.example` is authoritative** unless product owner prefers `backend/.env`.  
  - [x] Confirm `backend` service: `build: ./backend`, port `8000:8000`, cache volume `./backend/cache:/app/cache` matches [Source: `backend/Dockerfile`] `WORKDIR /app` and `CACHE_DIR` default `./cache`.

- [x] **Task 2 — Frontend service wiring (AC: 1, 3)**  
  - [x] Confirm `frontend` build args set `NEXT_PUBLIC_BACKEND_URL` for **host browser** access ([Source: `frontend/Dockerfile`] `ARG` / `ENV`).  
  - [x] Confirm `depends_on: [backend]` ordering; optional: `healthcheck` on backend for stricter startup (stretch, not required by epic).  
  - [x] Smoke: from host, open app and run one analytics request + one flow that hits API (e.g. health or schema) without CORS errors.

- [x] **Task 3 — Backend env in container (AC: 1–2)**  
  - [x] Verify `OPENROUTER_API_KEY` and paths in `.env` work inside container (`DATABASE_URL=sqlite:///./freightmind.db` → file under `/app` in container).  
  - [x] If SQLite file location causes permission or persistence issues, adjust **only** env or volume mounts — avoid unrelated refactors.

- [x] **Task 4 — Verification & docs handoff**  
  - [x] Document exact commands: `docker compose build --no-cache` (optional cold simulation), `docker compose up`, expected URLs.  
  - [x] Confirm `GET /api/health` returns `status: ok` with valid key and network (model check may fail in offline environments — if that yields `degraded`, document whether story accepts “degraded” or requires network; **default expectation:** with key + network, `status` is `ok`).  

- [x] **Task 5 — Tests (lightweight)**  
  - [x] Prefer **manual verification checklist** for this story (compose E2E is often CI-heavy). If CI exists: optional script that curls `/api/health` after `compose up -d` — only add if repo already patterns integration tests similarly.

### Review Findings

- [x] [Review][Patch] Track contract test and health script in git — `backend/tests/test_story_6_1.py` and `scripts/verify-compose-health.sh` are still untracked (`git status` shows `??`); CI will not run the pytest contract until they are committed. — **Resolved 2026-03-31:** committed in `56fdab6`.

## Dev Notes

### Technical requirements

- **Stack:** Docker Compose at repo root; backend [Source: `backend/Dockerfile`] (Python 3.12 + uv); frontend [Source: `frontend/Dockerfile`] (Node 22 + pnpm, Next `output: "standalone"` — [Source: `frontend/next.config.ts`]).  
- **CORS:** Already wildcard — no change required unless compose exposes a new origin pattern.  
- **Ports:** Backend `8000`, frontend `3000` — must match epic and evaluator expectations.

### Architecture compliance

- Follow [Source: `_bmad-output/planning-artifacts/architecture.md`] — Infrastructure & Deployment; canonical Dockerfiles in Gap 2. Align documented `env_file` path with implementation to avoid evaluator confusion.  
- NFRs touched: **NFR6 / NFR9 / NFR12** are listed for Epic 6 overall; **6.1** is local-only — focus on cold-start developer experience.

### Library / framework requirements

- **Docker Compose:** v2 plugin (`docker compose`) is standard; keep `docker-compose.yml` filename for compatibility.  
- **No new runtime dependencies** for this story unless required to fix a broken build.

### File structure requirements

| Path | Role |
|------|------|
| `docker-compose.yml` | Root orchestration — primary edit surface |
| `.env.example` | Template for root `.env` consumed by compose |
| `backend/Dockerfile` | Backend image — verify paths and `uv sync --frozen` |
| `frontend/Dockerfile` | Frontend image — standalone output |
| `backend/.env.example` | Backend-local docs; may duplicate root — clarify in notes if both exist |

### Testing requirements

- Manual: cold clone simulation, build, `up`, browser smoke, `curl` health.  
- Automated: optional; do not block on full E2E if not already in project.

### Previous story intelligence

- **Epic 5 complete** — structured `ErrorResponse`, rate limits, toasts. Compose work must **not** regress API contracts or env var names used by [Source: `backend/app/core/config.py`].  
- **No prior Epic 6 story** — this is the first deployment epic story; no in-epic predecessor file.

### Git intelligence summary

- Recent history is sparse in clone; rely on **repo files** and **epics** as source of truth rather than commit patterns.

### Latest technical information

- Prefer **Docker Compose specification** compatible with Docker Engine / Compose V2.  
- `NEXT_PUBLIC_*` is inlined at **Next.js build time** — changing API URL requires **rebuild** of the frontend image, not runtime env alone for client-side fetch URL.

### Project context reference

- No `project-context.md` in repo — use [Source: `_bmad-output/planning-artifacts/epics.md` Epic 6], [Source: `_bmad-output/planning-artifacts/architecture.md`], and this file.

### Story completion status

- **done** — Code review patch applied: contract test + `verify-compose-health.sh` committed (`56fdab6`).

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

- `docker compose config -q` — valid compose file  
- `docker compose build` — backend + frontend images built successfully  
- `docker compose up -d` + `curl http://localhost:8000/api/health` — `{"status":"ok","database":"connected","model":"reachable"}`  

### Completion Notes List

- Aligned **architecture.md** Docker Compose snippet with repo root `env_file: .env` and frontend build arg `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000`; added short evaluator note on browser vs Docker DNS.  
- Added top-of-file comments to **docker-compose.yml** and expanded **`.env.example`** / **`backend/.env.example`** for single-command local startup.  
- Added **`backend/tests/test_story_6_1.py`** — contract tests for compose wiring.  
- Added **`scripts/verify-compose-health.sh`** — optional host curl helper after `compose up`.  
- Verified full **`pytest`** (353 tests) and **`pnpm vitest run`** (11 tests) pass; new tests only in `test_story_6_1.py`.  

### File List

- `docker-compose.yml`
- `.env.example`
- `backend/.env.example`
- `_bmad-output/planning-artifacts/architecture.md`
- `backend/tests/test_story_6_1.py`
- `scripts/verify-compose-health.sh`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/6-1-docker-compose-single-command-local-startup.md`

## Change Log

- **2026-03-30:** Story 6.1 — Documented and aligned Docker Compose with architecture; compose contract tests; health verification script; manual docker build + smoke curl verified.
- **2026-03-31:** Code review — committed `backend/tests/test_story_6_1.py` and `scripts/verify-compose-health.sh` (`56fdab6`); story marked done.
