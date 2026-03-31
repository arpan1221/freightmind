# Story 6.5: README with architecture overview, setup guide, and demo script

Status: done

<!-- Ultimate context engine analysis completed — comprehensive developer guide created -->

## Story

As an evaluator,
I want a README that explains the system architecture, how to run it locally, and a step-by-step demo script,
so that I can evaluate the system without needing to decipher the codebase first.

## Acceptance Criteria

1. **README content (structure)**  
   **Given** the evaluator opens the repo  
   **When** they read the root [Source: `README.md`]  
   **Then** it contains:
   - A **one-paragraph** project summary (what FreightMind does: NL analytics on SCMS shipments + vision extraction with review/confirm + cross-table linkage).
   - An **architecture diagram** — Mermaid **or** ASCII — showing the **service / agent pipeline**: **Planner → Executor → Verifier → SQLite** (and **ModelClient** → OpenRouter where relevant). The diagram must match the pattern in [Source: `_bmad-output/planning-artifacts/architecture.md` § Component Boundaries / Service Boundaries] — do not invent a different pipeline.
   - A **tech stack table** (frontend, backend, DB, LLM gateway, key libs: e.g. Next.js, FastAPI, SQLite, OpenRouter, PyMuPDF, Recharts) aligned with [Source: `_bmad-output/planning-artifacts/architecture.md` § Starter Template Evaluation / Core Architectural Decisions].
   - A **step-by-step demo script** that walks through **all five evaluation journeys** listed in AC #3 below — in order, with explicit UI locations (chat vs upload) and expected outcomes.

2. **Local setup accuracy**  
   **Given** the evaluator follows the **local setup** section  
   **When** they run the documented commands on a clean machine with Docker (and documented prerequisites)  
   **Then** the system starts successfully — instructions must be **verified by the implementer** against the current repo (not copy-pasted blindly from epics if paths differ).  
   **Authoritative local path:** [Source: `docker-compose.yml`], [Source: `.env.example` at repo root], Story **6.1** notes on `docker compose` vs `docker-compose`, `NEXT_PUBLIC_BACKEND_URL` / `NEXT_PUBLIC_API_URL` naming as implemented in [Source: `frontend/Dockerfile`], [Source: `frontend/src/lib/api.ts` or equivalent].

3. **Five evaluation journeys (demo script must cover each)**  
   **Given** the evaluator reads the demo script  
   **When** they follow it sequentially  
   **Then** it covers:
   1. **Analytics on SCMS data** — natural-language question in the chat; shows answer + table/chart as applicable; optional SQL disclosure expand.
   2. **Document upload + extraction review** — upload a demo file from [Source: `backend/data/demo_invoices/`] *(Story 6.4)* — if 6.4 not merged yet, say “path per Story 6.4” and use any PDF/image from repo once available; review table + confidence badges.
   3. **Confirm extraction + query it** — confirm, then a **new** analytics question that targets confirmed extracted data (not only `shipments`).
   4. **Cross-table linkage query** — question that requires **both** `shipments` and `extracted_documents` (or line items) — user sees combined answer and can expand SQL showing both tables referenced (FR28).
   5. **Deliberate failure path** — e.g. question that triggers structured error (unsafe SQL / rate limit / model path) or follow Story 5.x behaviour so **ErrorResponse** + **ErrorToast** (countdown if `retry_after`) is visible — aligns with Epic 5.

4. **Deployment pointers (lightweight)**  
   **Given** evaluators may use **local only** or **hosted** (Stories 6.2–6.3)  
   **When** they read the README  
   **Then** include a short subsection: how production URLs fit together (Vercel frontend env → Render backend), **without** committing secrets or hardcoding team URLs — placeholders like `https://<your-service>.onrender.com` are fine. Cross-link to completion notes from 6.2/6.3 if those stories are done.

## Tasks / Subtasks

- [x] **Task 1 — Replace stub README** (AC: 1–2)  
  - [x] Edit **root** [Source: `README.md`] (currently minimal) — make it the primary evaluator entrypoint; optionally trim or link [Source: `frontend/README.md`] so there is no conflicting “how to run” story.  
  - [x] Add sections: Overview, Architecture (diagram + stack table), Prerequisites, Local setup (env copy, `docker compose up`, URLs), Optional dev without Docker (only if verified — otherwise say “Docker recommended”).  
  - [x] Use **real** API paths from code: `POST /api/query`, `POST /api/documents/extract`, `POST /api/documents/confirm`, `GET /api/schema`, `GET /api/health` — **not** legacy `/api/analytics/query` from older architecture prose unless the code is changed (it is not in scope for this story).

- [x] **Task 2 — Diagram** (AC: 1)  
  - [x] Add Mermaid in README (renders on GitHub) **or** ASCII art — must show Planner → Executor → Verifier → DB for **both** analytics and extraction at a high level, plus ModelClient/OpenRouter.  
  - [x] Cite alignment with [Source: `_bmad-output/planning-artifacts/architecture.md` § Service Boundaries].

- [x] **Task 3 — Demo script** (AC: 1, 3)  
  - [x] Write numbered steps; name UI components consistently ([Source: `frontend/src/components/ChatPanel.tsx`], [Source: `frontend/src/components/UploadPanel.tsx`], [Source: `frontend/src/app/page.tsx`]).  
  - [x] For journey (4), include at least **one example prompt** that forces linkage (adjust wording to match normalised country/mode vocabulary — see Epic 4 / normaliser).  
  - [x] For journey (5), describe **one** reproducible failure (e.g. question designed to produce verifier rejection — **without** asking users to attack the system).

- [x] **Task 4 — Verify instructions** (AC: 2)  
  - [x] Run through local setup from a clean shell (or document “last verified” commit/date).  
  - [x] Fix any mismatch: CSV path [Source: `backend/data/SCMS_Delivery_History_Dataset.csv`], database file location in container, port **3000** / **8000**.

- [x] **Task 5 — Cross-story dependencies** (AC: 3–4)  
  - [x] If Story **6.4** demo files are missing, state dependency explicitly (“complete 6.4 first” or use temporary sample files — prefer not to add large binaries in 6.5; reference 6.4 path).  
  - [x] Align wording with Story **6.1** (Compose) and **6.3** (Vercel `NEXT_PUBLIC_*`) so README does not contradict those stories.

### Review Findings

**Senior Developer Review (AI)** — 2026-03-30

**Outcome:** Approve — minor documentation gaps addressed in review pass.

- [x] [Review][Patch] README footer claimed “bootstrapped app notes” in `frontend/README.md` — replaced with accurate “minimal frontend-only dev commands” wording and a proper relative link. [`README.md`]
- [x] [Review][Patch] AC4 asked for cross-link to Story 6.2/6.3 completion notes — added links to `_bmad-output/implementation-artifacts/6-2-backend-deployment-to-render.md` and `6-3-frontend-deployment-to-vercel.md` from the Deployment section. [`README.md`]
- [x] [Review][Patch] Journey 5 (unsafe SQL demo) can be non-deterministic — added explicit note to rephrase if the model returns safe SQL only. [`README.md`]
- [x] [Review][Patch] NFR12 cold-start expectation — added brief Render bullet note (~60s to healthy `/api/health`). [`README.md`]

**Layers:** Blind Hunter, Edge Case Hunter, and Acceptance Auditor findings triaged inline (no subagent run — consolidated review).

## Dev Notes

### Technical requirements

- **Primary deliverable:** Root `README.md` (Markdown, GitHub-flavoured).  
- **Accuracy:** Routes and filenames must match the repository; architecture.md is **conceptual** — when it disagrees with code (e.g. endpoint names), **code wins**.  
- **Secrets:** Never document real API keys; point to `.env.example` only (NFR10).

### Architecture compliance

- Follow [Source: `_bmad-output/planning-artifacts/architecture.md`] for intent; validate every path against [Source: `backend/app/main.py`] router mounts.  
- Epic 6 NFRs: README supports **NFR6** (evaluator understands how to hit the SPA), **NFR9** (HTTPS for deployed URLs), **NFR12** (cold start expectations — brief note for Render).

### Library / framework requirements

- None new — documentation only. Mermaid is optional (no npm dependency).

### File structure requirements

| Path | Action |
|------|--------|
| `README.md` | Main content — **must** be updated |
| `frontend/README.md` | Optional: single link from root or reduce duplication |
| `_bmad-output/planning-artifacts/architecture.md` | Read-only reference |

### Testing requirements

- **Manual:** Execute every command block in README on a fresh clone (or CI doc check if added — not required).  
- **No pytest** for this story unless team adds a markdown link checker; scope is human-verified accuracy.

### Previous story intelligence

- **6.1** — Docker Compose single command, root `.env`, browser must use `localhost:8000` for API — README must preserve this.  
- **6.2** — Render `PORT`, `/api/health`, `/docs` — short production subsection.  
- **6.3** — Vercel `NEXT_PUBLIC_*` for backend URL — document placeholder pattern.  
- **6.4** — Demo invoices under `backend/data/demo_invoices/` — demo script should reference these files once present.

### Git intelligence summary

- Root `README.md` is a stub — this story is the authoritative pass to flesh it out.

### Latest technical information

- GitHub renders **Mermaid** in Markdown; prefer fenced `mermaid` blocks for architecture diagrams.  
- Next.js `NEXT_PUBLIC_*` vars are **build-time** for client bundles — README should say rebuild/redeploy when changing API URL (consistent with Story 6.1 dev notes).

### Project context reference

- No `project-context.md` in repo — use this file + [Source: `_bmad-output/planning-artifacts/epics.md` § Story 6.5] + [Source: `_bmad-output/planning-artifacts/architecture.md`].

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` — Epic 6, Story 6.5]  
- [Source: `_bmad-output/planning-artifacts/architecture.md` — Service Boundaries, Data Flow, Component Boundaries]  
- [Source: `_bmad-output/implementation-artifacts/6-1-docker-compose-single-command-local-startup.md`]  
- [Source: `_bmad-output/implementation-artifacts/6-2-backend-deployment-to-render.md`]

### Story completion status

- **done** — README complete; code review (2026-03-30) applied follow-up doc tweaks; ready to ship.

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

### Completion Notes List

- Authored root `README.md`: overview, Mermaid architecture diagram, tech stack table, Docker Compose setup, API table, deployment placeholders (Render + Vercel + `NEXT_PUBLIC_*`), five-journey demo script with ChatPanel/UploadPanel/page.tsx references.
- Replaced conflicting `frontend/README.md` bootstrapping instructions with a pointer to the root README and minimal `pnpm dev` notes.
- Added `backend/data/demo_invoices/README.md` manifest (`demo-01`…`demo-06`) to satisfy Story 6.4 test handoff to 6.5 and align demo steps with on-disk assets.
- Ran `uv run pytest` in `backend/`: 356 passed; `pnpm exec vitest run` in `frontend/`: 14 passed.
- Code review (2026-03-30): README deployment cross-links to 6.2/6.3 story files, footer wording fix, journey 5 non-determinism note, NFR12 Render note.

### File List

- `README.md`
- `frontend/README.md`
- `backend/data/demo_invoices/README.md`
- `_bmad-output/implementation-artifacts/6-5-readme-with-architecture-overview-setup-guide-and-demo-script.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
