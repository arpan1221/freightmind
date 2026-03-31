# Story 6.4: Synthetic freight invoice demo files

Status: done

<!-- Ultimate context engine analysis completed — comprehensive developer guide created -->

## Story

As an evaluator,
I want 5–6 synthetic freight invoice files (mix of PDF and image formats) ready to upload,
so that I can demonstrate the Vision Extraction agent without needing to source my own documents.

## Acceptance Criteria

1. **Repo location and upload behaviour (Epic 6.4, FR9–FR18)**  
   **Given** the demo invoices are included in the repo under `backend/data/demo_invoices/`  
   **When** each file is uploaded via the upload panel (`POST /extract` — [Source: `backend/app/api/routes/extraction.py`])  
   **Then** the extraction pipeline returns **plausible** freight fields: shipment mode, origin/destination country, weight, cost, dates (aligned with [Source: `backend/app/prompts/extraction_fields.txt`])  

2. **Confidence badge demo (FR14)**  
   **And** at least **one** invoice is designed so that, after vision extraction, **at least one header field** resolves to per-field confidence **`LOW`** or **`NOT_FOUND`** — so the Upload Panel can demonstrate colour-coded confidence badges ([Source: `frontend/src/components/ConfidenceBadge.tsx`], [Source: `backend/app/agents/extraction/`]).  
   **Implementation note:** This is usually achieved by making one field faint, cropped, ambiguous, or omitted on purpose in that asset — the model must actually return LOW/NOT_FOUND; if live model behaviour is non-deterministic, document which file is intended for this and re-test.

3. **Linkage-ready invoice (FR25–FR28, Epic 4)**  
   **And** at least **one** invoice uses **shipment mode** and **destination country** values that, after normalisation, match vocabulary present in the loaded SCMS dataset so a **cross-table** analytics question is meaningful post-confirm (e.g. compare uploaded row to dataset averages).  
   **Canonical dataset modes** include: `Air`, `Ocean`, `Truck`, `Air Charter` ([Source: `DATASET_SCHEMA.md` § Raw CSV columns]).  
   **Normaliser** maps free-text to canonical strings — prefer invoice text that normalises to a mode/country pair that appears in **`shipments`** (e.g. **Air** + **Nigeria**) — see [Source: `backend/app/agents/extraction/normaliser.py`] (`_MODE_MAP`, `_COUNTRY_MAP`).  
   **Critical:** Linkage correctness depends on `destination_country` and `shipment_mode` matching dataset vocabulary after the verifier/normaliser — see [Source: `_bmad-output/planning-artifacts/architecture.md`] § Linkage correctness dependency.

4. **Format mix (FR9, FR10)**  
   **Given** the invoices are inspected  
   **When** the formats are checked  
   **Then** the set includes **at least 2 PDFs** and **at least 1** raster image (**PNG** or **JPG**) to exercise both upload paths  

5. **Count**  
   **And** the set contains **5–6** distinct files total (epic requirement)

## Tasks / Subtasks

- [x] **Task 1 — Inventory & naming (AC: 1, 4, 5)**  
  - [x] Create `backend/data/demo_invoices/` and add **5–6** files with clear names (e.g. `demo-01-air-nigeria.pdf`, `demo-02-ocean-ambiguous-field.png`).  
  - [x] Ensure **≥2** `.pdf` and **≥1** `.png` or `.jpg` (case-insensitive extensions OK).  
  - [x] Keep total repo weight reasonable (compress images; avoid multi‑MB assets without need).

- [x] **Task 2 — Content design (AC: 1–3)**  
  - [x] Each asset: **synthetic only** — fictional shipper/consignee/carrier names, fake invoice numbers, no real credentials or logos subject to third-party rights.  
  - [x] Populate visible labels for the 13 header fields where appropriate so the vision model can fill JSON per [Source: `backend/app/prompts/extraction_fields.txt`].  
  - [x] For **linkage invoice(s):** include legible text for **mode** + **destination** that normalises to values present in SCMS (spot-check against [Source: `backend/data/SCMS_Delivery_History_Dataset.csv`] or `normaliser` output).  
  - [x] For **LOW/NOT_FOUND demo:** one file deliberately weakens or omits one header field visually.

- [x] **Task 3 — Optional manifest (handoff to Story 6.5)**  
  - [x] Add `backend/data/demo_invoices/README.md` listing each file, intended scenario (linkage / confidence demo / generic), and suggested upload order — supports README demo script in **6.5**.

- [x] **Task 4 — Verification**  
  - [x] Document manual verification in `backend/data/demo_invoices/README.md`: upload order, which file is linkage (**Air** + **Nigeria**), which target **LOW** vs **NOT_FOUND**, and a cross-table smoke query after confirm (live `OPENROUTER_API_KEY` required to validate model output — not run in CI).  
  - [x] Layout intent for confidence demos: `demo-04-low-confidence-paymentterms.png` (microprint/low-contrast payment terms) and `demo-06-no-insurance-line.png` (no insurance line). Evaluator should confirm the vision model returns **LOW** / **NOT_FOUND** on the intended fields.  
  - [x] If live extraction is empty or implausible for any asset, re-run `generate_demo_invoices.py` and adjust text/layout; document in README if model-specific tuning is needed.

- [x] **Task 5 — Automated guardrail (optional but recommended)**  
  - [x] Add a small pytest (e.g. `backend/tests/test_story_6_4.py`) that asserts: directory exists, file count in [5,6], extension mix per AC4 — **no** live vision calls in CI.

### Review Findings

_Senior Developer Review (AI) — 2026-03-30_

**Outcome:** Approve (after patch)

- [x] [Review][Patch] Strengthen README manifest test — `test_demo_readme_manifest_exists` only checks for `demo-01` / `01-`; add assertions that README mentions linkage and cross-table (or `Nigeria` + `Air`) so Story 6.5 handoff content cannot regress silently [`backend/tests/test_story_6_4.py` ~36–41]

- [x] [Review][Defer] AC1–AC2 empirical validation — Plausible extraction and actual **LOW**/**NOT_FOUND** from the vision model are not proven by automated tests; README documents manual OpenRouter verification. Accept for PoC; confirm before a graded demo.

- [x] [Review][Defer] Generator robustness — `generate_demo_invoices.py` has no `try`/`except` around `save`/`unlink`/`pix.save`; a full disk or permission error yields an opaque traceback. Low priority for a one-off dev script.

- [x] [Review][Defer] No CI smoke that runs the generator — Regeneration could break without detection; optional follow-up: tmpdir smoke invoking `main()` or subprocess.

## Dev Notes

### Technical requirements

- **Assets are data, not runtime code:** Prefer **checked-in** PDF/PNG/JPG binaries.  
- **PDF creation:** If generating programmatically, **PyMuPDF** is already a dependency ([Source: `backend/pyproject.toml`]) — acceptable for one-off scripts under e.g. `backend/scripts/` (do not add heavy deps unless necessary). Hand-drawn exports from any tool are fine.  
- **Raster images:** If you need scripted image generation, adding **Pillow** to **dev** only is acceptable; otherwise export PNGs from a design tool and commit binaries.  
- **Do not** wire these paths into application startup — they are **evaluator-facing samples**, not auto-loaded DB seeds (contrast: [Source: `backend/data/`] SCMS CSV load in lifespan).

### Architecture compliance

- **Extraction pipeline:** Vision → JSON with per-field confidence → normaliser → verifier — unchanged; demo files must **feed** this pipeline realistically ([Source: `backend/app/agents/extraction/`]).  
- **No secrets** in filenames or embedded metadata.

### Library / framework requirements

- **No new production dependencies** required for checked-in static files.  
- Optional script-only deps (e.g. Pillow) → `[dependency-groups] dev` only.

### File structure requirements

| Path | Role |
|------|------|
| `backend/data/demo_invoices/` | **Primary deliverable** — synthetic invoice PDFs/images |
| `backend/data/demo_invoices/README.md` | Optional index for evaluators (recommended) |
| `backend/scripts/` (optional) | One-off generators — gitignore scratch output if any |

### Testing requirements

- Manual: full upload → review → confirm → analytics path for linkage file.  
- Automated: lightweight **inventory** test only (optional); do not assert LLM outputs in CI.

### Previous story intelligence

- **Story 6.1** ([Source: `_bmad-output/implementation-artifacts/6-1-docker-compose-single-command-local-startup.md`]) — local stack via Compose; use the same stack to manually verify uploads.  
- **Epics 3–5** — extraction, confidence UI, structured errors; demo should exercise badges and not assume perfect HIGH on every field.  
- **No story file for 6.2 / 6.3** in repo yet — deployment stories are parallel concerns; demo files are **environment-agnostic**.

### Git intelligence summary

- Rely on repo layout and epics as source of truth; no special commit pattern required.

### Latest technical information

- Vision model behaviour may vary slightly by provider/model version — **re-test** after changing `VISION_MODEL` / OpenRouter settings in [Source: `backend/app/core/config.py`].

### Project context reference

- No `project-context.md` in repo — use [Source: `_bmad-output/planning-artifacts/epics.md` § Story 6.4], [Source: `DATASET_SCHEMA.md`], and this file.

### Story completion status

- **done** — Code review 2026-03-30: README test strengthened; deferred items tracked in `deferred-work.md`.

## Dev Agent Record

### Agent Model Used

Cursor agent (implementation)

### Debug Log References

### Completion Notes List

- Added six synthetic invoices (3 PDF, 2 PNG, 1 JPG) under `backend/data/demo_invoices/` with `demo-01-air-nigeria-linkage.pdf` for **Air + Nigeria** linkage; `demo-04-low-confidence-paymentterms.png` (microprint payment terms); `demo-06-no-insurance-line.png` (omitted insurance line for NOT_FOUND intent).
- Added `backend/scripts/generate_demo_invoices.py` (PyMuPDF) to regenerate assets deterministically.
- Added `backend/tests/test_story_6_4.py` for directory/count/extension/README guardrails (no vision calls).
- README lists upload order and manual verification steps for evaluators (vision output may vary).

### File List

- `backend/data/demo_invoices/demo-01-air-nigeria-linkage.pdf`
- `backend/data/demo_invoices/demo-02-ocean-vietnam.pdf`
- `backend/data/demo_invoices/demo-03-truck-zambia.pdf`
- `backend/data/demo_invoices/demo-04-low-confidence-paymentterms.png`
- `backend/data/demo_invoices/demo-05-air-charter-haiti.jpg`
- `backend/data/demo_invoices/demo-06-no-insurance-line.png`
- `backend/data/demo_invoices/README.md`
- `backend/scripts/generate_demo_invoices.py`
- `backend/tests/test_story_6_4.py`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/deferred-work.md` (deferred review follow-ups)
- `backend/tests/test_story_6_4.py` (post-review: README linkage assertions)

### Change Log

- 2026-03-30 — Story 6.4: demo invoice assets, generator script, inventory pytest, README manifest; sprint `6-4` → review.
- 2026-03-30 — Code review: strengthened `test_demo_readme_manifest_exists`; story → **done**; sprint `6-4` → **done**.
