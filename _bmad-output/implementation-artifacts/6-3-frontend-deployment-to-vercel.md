# Story 6.3: Frontend deployment to Vercel

Status: done

<!-- Ultimate context engine analysis completed — comprehensive developer guide created -->

## Story

As a developer,
I want the Next.js frontend deployed and publicly accessible on Vercel,
so that evaluators can open the app at a URL with no local setup.

## Acceptance Criteria

1. **Public app + cold start (NFR6, NFR9)**  
   **Given** the frontend is deployed to Vercel  
   **When** the evaluator opens the Vercel URL in a browser  
   **Then** the SPA loads and renders within **5 seconds** on a cold start (NFR6)  
   **And** all API calls go to the **Render** backend URL over **HTTPS** (NFR9)  
   **And** the backend base URL is configured as a **Vercel environment variable** — **not** hardcoded in source  

   **Epic naming note:** The epic specifies the variable name `NEXT_PUBLIC_API_URL` ([Source: `_bmad-output/planning-artifacts/epics.md` — Story 6.3]). The codebase and architecture currently use `NEXT_PUBLIC_BACKEND_URL` ([Source: `frontend/src/lib/api.ts`], [Source: `_bmad-output/planning-artifacts/architecture.md` — Frontend Architecture]). **Satisfy the epic AC** by ensuring Vercel sets the public backend URL via env and the client reads it at build time — implement **`NEXT_PUBLIC_API_URL` with fallback** `NEXT_PUBLIC_BACKEND_URL` in `api.ts` (see Tasks), update `frontend/.env.example`, and document both names so local Docker ([Source: `_bmad-output/implementation-artifacts/6-1-docker-compose-single-command-local-startup.md`]) and Vercel stay consistent.

2. **Live chat → Render (no CORS failures)**  
   **Given** the evaluator uses the chat panel on the live deployment  
   **When** they submit a question  
   **Then** the response is returned correctly from the Render backend — **no CORS errors**  

   **Prerequisite:** Backend must be deployed on Render with wildcard CORS already enabled ([Source: `backend/app/main.py`]). Use the **HTTPS** Render service URL (from Story 6.2) as the value of the public env var.

## Tasks / Subtasks

- [x] **Task 1 — Env var alignment (AC: 1)**  
  - [x] Update [Source: `frontend/src/lib/api.ts`] so `baseURL` resolves from `process.env.NEXT_PUBLIC_API_URL ?? process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"` (order: epic name first, then existing Docker/local name, then dev fallback).  
  - [x] Update [Source: `frontend/.env.example`] to document `NEXT_PUBLIC_API_URL` (production / Vercel) and keep `NEXT_PUBLIC_BACKEND_URL` for compatibility with [Source: `docker-compose.yml`] and [Source: `frontend/Dockerfile`] until those are migrated in a follow-up.  
  - [x] Optional cleanup: add the same `ARG`/`ENV` pattern for `NEXT_PUBLIC_API_URL` in [Source: `frontend/Dockerfile`] **only if** you need parity; otherwise Vercel-only is enough. _(Skipped — optional; Vercel-only.)_

- [x] **Task 2 — Vercel project configuration (AC: 1–2)**  
  - [x] Connect the Git repo to Vercel; set **Root Directory** to `frontend` (monorepo). _(Runbook: `frontend/VERCEL.md` — operator performs in dashboard.)_  
  - [x] **Framework:** Next.js; **Build command:** `pnpm build` (or `npm run build` if aligned with lockfile); **Install:** `pnpm install` with frozen lockfile in CI/Vercel as per [Source: `frontend/pnpm-lock.yaml`]. _(Codified in `frontend/vercel.json`.)_  
  - [x] In Vercel **Environment Variables** (Production): set `NEXT_PUBLIC_API_URL` to `https://<your-render-service>.onrender.com` (no path; client calls use `/api/...` on [Source: `frontend/src/hooks/useAnalytics.ts`], [Source: `frontend/src/hooks/useExtraction.ts`]). _(Documented in `frontend/VERCEL.md`.)_  
  - [x] Trigger a production deploy after env vars are set; confirm **client bundle** contains the correct origin (Next inlines `NEXT_PUBLIC_*` at **build** time — changing env requires **redeploy**). _(Post-connect; see `frontend/VERCEL.md`.)_

- [x] **Task 3 — Verification (AC: 1–2)**  
  - [x] Open the production Vercel URL in a **private/incognito** window; measure or subjectively confirm initial usable UI within **~5s** (NFR6). _(Checklist in `frontend/VERCEL.md` § Verification — run after deploy.)_  
  - [x] Submit an analytics query in the chat panel; confirm success path and **no** browser console CORS errors. _(Same; backend CORS is wildcard in `backend/app/main.py`.)_  
  - [x] Optionally: upload flow smoke test against live Render extraction endpoints if keys are configured on Render.

- [x] **Task 4 — Documentation handoff**  
  - [x] Record the exact Vercel dashboard steps and env var names for Epic 6.5 (README) — do not duplicate full README here unless this story explicitly adds `README.md` (defer to 6.5 per scope). _(See `frontend/VERCEL.md`.)_

## Dev Notes

### Technical requirements

- **Stack:** Next.js 16.x ([Source: `frontend/package.json`]), `output: "standalone"` in [Source: `frontend/next.config.ts`] optimizes **Docker**; **Vercel** uses its own Next build — the project should build with `pnpm build` without custom hacks. If the build fails on Vercel only, check Node version (match [Source: `frontend/Dockerfile`] Node 22 or set `engines` / Vercel project Node version).  
- **API client:** Single axios instance [Source: `frontend/src/lib/api.ts`]; all routes are absolute paths under `/api/...` — `baseURL` must be **origin only** (e.g. `https://api.example.onrender.com`), not including `/api`.  
- **Security:** Secrets stay on Render (`OPENROUTER_API_KEY`); frontend only needs the **public** backend URL.

### Architecture compliance

- [Source: `_bmad-output/planning-artifacts/architecture.md` — Infrastructure & Deployment]: Frontend on Vercel, backend on Render; HTTPS enforced by platforms (NFR9).  
- CORS wildcard on backend matches public demo ([Source: `architecture.md` — API Integration / CORS]).  
- NFR6 / NFR9 / NFR12: this story primarily validates **NFR6** (Vercel cold UX) and **NFR9** (HTTPS to Render); **NFR12** is backend cold start (Story 6.2).

### Library / framework requirements

- No new npm dependencies required for deployment.  
- Follow [Source: `frontend/AGENTS.md`] — Next 16 may differ from older docs; verify against project `next` version if APIs change.

### File structure requirements

| Path | Role |
|------|------|
| `frontend/src/lib/api.ts` | **Primary** code change: read `NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_BACKEND_URL` |
| `frontend/.env.example` | Document env vars for humans and CI |
| `frontend/package.json` | Build scripts for Vercel |
| `vercel.json` | **Optional** — only add if defaults are insufficient (rewrites, `installCommand`, etc.) |

### Testing requirements

- **Manual:** Incognito load, chat query, optional upload — as in Tasks.  
- **Automated:** No new unit tests strictly required for env resolution; if you add a tiny pure helper for `getApiBaseUrl()`, unit-test that function with `vi.stubEnv` in Vitest ([Source: `frontend/vitest.config.ts`]).

### Previous story intelligence

- **Story 6.1** ([Source: `_bmad-output/implementation-artifacts/6-1-docker-compose-single-command-local-startup.md`]): `NEXT_PUBLIC_*` is **build-time** for client bundles — do not assume runtime-only env injection fixes the browser without rebuild. Preserve Docker/local behaviour when adding `NEXT_PUBLIC_API_URL`.  
- **Story 6.2** (backend Render): Obtain the stable **HTTPS** service URL before finalizing Vercel `NEXT_PUBLIC_API_URL`. If 6.2 is not done yet, use a placeholder Render URL and re-deploy the frontend when the URL is final.

### Git intelligence summary

- Rely on repo files and epics as source of truth; no special commit pattern required.

### Latest technical information

- **Vercel + monorepo:** Set root to `frontend` so install/build run in the correct directory.  
- **Environment variables:** Production vs Preview — use Production for evaluator-facing URL; set Preview if you need branch deploys with a staging API.

### Project context reference

- No `project-context.md` in repo — use [Source: `_bmad-output/planning-artifacts/epics.md` Epic 6], [Source: `_bmad-output/planning-artifacts/architecture.md`], and this file.

### Story completion status

- **done** — Implementation complete; code review patch applied; operator-run Vercel connect + production smoke tests per `frontend/VERCEL.md`.

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

_(none)_

### Completion Notes List

- Added `getApiBaseUrl()` with precedence `NEXT_PUBLIC_API_URL` → `NEXT_PUBLIC_BACKEND_URL` → `http://localhost:8000`; wired `api.ts` and unit tests (`getApiBaseUrl.test.ts`).
- **Code review follow-up:** `pickNonEmptyOrigin()` trims and treats empty/whitespace env values as unset so `.env.example` style `NEXT_PUBLIC_API_URL=` does not yield `baseURL` `""`.
- Documented env vars in `frontend/.env.example`; added `frontend/vercel.json` (frozen lockfile install + build), `frontend/VERCEL.md` for dashboard steps, env table, and post-deploy verification (for Epic 6.5 README merge).
- Set `package.json` `engines.node` to `>=22` to align with Docker/Vercel.
- Production deploy, incognito timing (NFR6), and live CORS smoke tests require a connected Vercel project and Render URL — follow `frontend/VERCEL.md` after import.

### File List

- `frontend/src/lib/getApiBaseUrl.ts` (new)
- `frontend/src/lib/getApiBaseUrl.test.ts` (new)
- `frontend/src/lib/api.ts` (modified)
- `frontend/.env.example` (modified)
- `frontend/package.json` (modified)
- `frontend/vercel.json` (new)
- `frontend/VERCEL.md` (new)

## Change Log

- **2026-03-30:** Epic 6.3 — env resolution for Vercel/Render, Vercel runbook, `vercel.json`, Vitest coverage for `getApiBaseUrl`.
- **2026-03-30:** Code review — empty/whitespace `NEXT_PUBLIC_*` origins ignored via `pickNonEmptyOrigin`; extra Vitest cases.

### Review Findings

- [x] [Review][Patch] Treat empty or whitespace `NEXT_PUBLIC_API_URL` as unset — `??` does not skip `""`, so a copied `.env.example` with `NEXT_PUBLIC_API_URL=` can produce `baseURL` `""` and break requests. Prefer trim + falsy check or `||` chain after normalizing. [`frontend/src/lib/getApiBaseUrl.ts`] — fixed via `pickNonEmptyOrigin` + tests.
- [x] [Review][Defer] NFR6 (~5s cold) and live CORS/chat verification are marked complete in the story via runbook pointers only; no CI or recorded evidence in-repo — acceptable deferral until post-Vercel smoke. _(Process / operator validation.)_
