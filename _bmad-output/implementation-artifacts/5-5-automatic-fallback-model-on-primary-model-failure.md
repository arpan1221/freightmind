# Story 5.5: Automatic fallback model on primary model failure

Status: review

<!-- Ultimate context engine analysis completed — comprehensive developer guide created -->

## Story

As a logistics analyst,
I want the system to automatically switch to a backup model when the primary model is unavailable,
so that temporary model outages don't fully block my queries.

## Acceptance Criteria

1. **Analytics / text modality (FR33)**  
   **Given** the primary analytics model (`settings.analytics_model`, Llama 3.3 70B class) fails **after all retries are exhausted** per Story **5.2** (and any transient handling in **5.3** does not apply — e.g. not a 429)  
   **When** `ModelClient` finishes the failed primary phase  
   **Then** it **automatically** issues the **same logical request** (same `messages`, temperature, validation hook) against the **configured fallback text model** (DeepSeek R1 — see Dev Notes for OpenRouter id)  
   **And** structured logging records **`model_name`** as the **actual model id string used in the API call**, **`fallback: true`**, and preserves **`retry_count`** semantics for attempts on the **fallback** phase (see Dev Notes).

2. **Vision modality (FR33)**  
   **Given** the primary vision model (`settings.vision_model`) fails after all retries are exhausted  
   **When** `ModelClient` finishes the failed primary phase  
   **Then** it automatically retries using the **configured fallback vision model** (Nemotron Nano VL — see Dev Notes).

3. **Double failure**  
   **Given** both primary **and** fallback models fail (after each side’s retry/fallback rules complete)  
   **When** there is no successful response to return  
   **Then** callers receive a path to an **`ErrorResponse`** with **`error_type: "model_unavailable"`** (Story **5.1** / **5.3**) — **no unhandled exception** and no raw OpenRouter payload leaked to the client.

4. **Gateway & cache**  
   **Given** `ModelClient` is the sole LLM gateway  
   **When** implementing fallback  
   **Then** do **not** bypass `ModelClient` from analytics or extraction agents; cache keys must remain correct (fallback uses a **different** `model` → different cache key from primary).

## Tasks / Subtasks

- [x] **Task 1 — Configuration (AC: 1–2)**  
  - [x] Add **`analytics_model_fallback`** and **`vision_model_fallback`** to `backend/app/core/config.py` with defaults aligned to [TECH_DECISIONS.md](../../TECH_DECISIONS.md) (`deepseek/deepseek-r1-0528:free`, `nvidia/nemotron-nano-2-vl:free`).  
  - [x] Document env var names in code (Pydantic Settings / `.env` example if the repo has one).  
  - [x] If `vision_model` in config still differs from TD-3 (primary vision), note alignment as a **separate small fix** or explicit follow-up — do not silently ignore product primary vs fallback pairing.

- [x] **Task 2 — `ModelClient` behaviour (AC: 1–4)**  
  - [x] After **primary** model exhausts failures (API errors, empty response, validation failures — same conditions that end the 5.2 loop on primary), invoke **one fallback phase** using the appropriate fallback id for the **modality** (infer from whether the requested `model` argument equals `settings.analytics_model` vs `settings.vision_model`, or add an explicit optional parameter `modality: Literal["analytics","vision"] | None` if inference is brittle).  
  - [x] On **successful** fallback response, log with **`fallback: true`** and **`model_name`** = fallback model id.  
  - [x] Ensure **cache**: primary miss + fallback success writes cache under the **fallback** model id key (natural if `make_cache_key` includes `model`).  
  - [x] Update module docstring: remove “fallback not implemented” once done.

- [x] **Task 3 — Error mapping (AC: 3)**  
  - [x] Raise or return a failure that route / global handlers map to **`model_unavailable`** per Stories **5.1**–**5.3** (reuse existing exception types if already introduced).  
  - [x] Do not conflate with **`rate_limit`** (429) — fallback is for **non-429** primary failure after retries.

- [x] **Task 4 — Tests**  
  - [x] Add **`backend/tests/test_story_5_5.py`**: mock `AsyncOpenAI` / completions so primary fails (or raises) through the **full** primary attempt budget, then succeeds on **first** fallback call — assert fallback model id passed to `create()`.  
  - [x] Assert log `extra` includes **`fallback: true`** on fallback success path (caplog or mock logger).  
  - [x] Case: primary fails, fallback fails → assert **`model_unavailable`** path (exception or structured result per 5.1 integration).  
  - [x] No live OpenRouter in CI.

## Dev Notes

### Ordering: retries vs fallback

- **Story 5.2** defines **retry with corrective instruction** on the **same** model (1s → 2s → 4s).  
- **This story:** only after that primary **phase** is exhausted should the client **switch model id** to the fallback and run the **fallback phase** (reuse the same internal retry/validate contract as primary unless the team explicitly documents “single shot on fallback” — prefer **symmetric** behaviour so transient fallback failures also get retries).

### Model IDs (authoritative for implementation)

| Role | Primary (intent) | Fallback OpenRouter id |
|------|-------------------|-------------------------|
| Text/SQL | `analytics_model` — `meta-llama/llama-3.3-70b-instruct` | `deepseek/deepseek-r1-0528:free` [Source: TECH_DECISIONS.md TD-2] |
| Vision | `vision_model` — align with TD-3 | `nvidia/nemotron-nano-2-vl:free` [Source: TECH_DECISIONS.md TD-3] |

Epics text uses short names (“DeepSeek R1”, “Nemotron Nano VL”); **logs and API calls must use the real OpenRouter model string**. Epic AC example `model_name: "deepseek-r1"` means **a stable, grep-friendly identifier** — implement as the **full** `model=` string (or document a normalized slug if product insists).

### Brownfield — current code

- [Source: `backend/app/services/model_client.py`] — single model per `call()`; no fallback; docstring defers retry/fallback to Epic 5.  
- Call sites: `app/api/routes/analytics.py` (analytics pipeline), `app/api/routes/documents.py` + `app/agents/extraction/executor.py` (vision). All must keep using **`ModelClient`** only.

### Dependencies

| Story | Why |
|-------|-----|
| **5.2** | Fallback runs **after** primary retries exhausted |
| **5.3** | 429 / timeout → structured errors; fallback must not mask rate limits |
| **5.1** | `ErrorResponse` + `model_unavailable` |

### Anti-patterns

- Do not add a second OpenRouter client outside `ModelClient`.  
- Do not cache a primary failure under the fallback key or vice versa.  
- Do not treat verifier/SQL errors as model fallback triggers — only LLM transport/parse/validation failures per `ModelClient` contract.

### Previous story intelligence

- [Source: `_bmad-output/implementation-artifacts/5-2-modelclient-retry-with-corrective-instruction.md`] — retry loop, `validate` hook, cache + retry interaction.  
- [Source: `_bmad-output/implementation-artifacts/5-4-invalid-or-unsafe-sql-structured-error-with-failed-query.md`] — keep failure domains separate (SQL vs LLM).

### Architecture compliance

- **Model Abstraction Layer** owns fallback [Source: `_bmad-output/planning-artifacts/architecture.md`].  
- **FR37** logging: `cache_hit`, `model_name`, `retry_count`; add **`fallback`** boolean for this story.

### Files likely touched

| Path | Role |
|------|------|
| `backend/app/core/config.py` | Fallback model settings |
| `backend/app/services/model_client.py` | Fallback phase after primary exhaustion |
| `backend/tests/test_story_5_5.py` | New |
| Possibly `backend/tests/test_story_1_6.py` | Adjust if cache/fallback tests overlap |

### Project context reference

No `project-context.md` in repo; use this file + `TECH_DECISIONS.md` + `epics.md` Story 5.5.

### References

- [Epics — Story 5.5](../planning-artifacts/epics.md)  
- [PRD — FR33](../planning-artifacts/prd.md)  
- [Architecture — ModelClient](../planning-artifacts/architecture.md)  
- [TECH_DECISIONS — TD-2, TD-3](../../TECH_DECISIONS.md)

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

_(none)_

### Completion Notes List

- Added `analytics_model_fallback` and `vision_model_fallback` to `Settings` with TECH_DECISIONS defaults; documented in `backend/.env.example`.
- `ModelClient.call()` wraps primary `_call_single_shot` / `_call_with_validation` in try/except: `RateLimitError` always propagates (no fallback). Any other failure with a configured `_fallback_for(model)` re-runs the same path with the fallback model id (full symmetric retry/validate behaviour on fallback).
- Logging: all relevant `extra` dicts include `fallback: bool` (`True` on fallback phase). Double failure raises `ModelUnavailableError` for HTTP handlers.
- Primary vision id remains `qwen/qwen2.5-vl-72b-instruct` in config (differs from TD-3 naming); follow-up alignment noted in story Dev Notes — not changed in this story.

### File List

- `backend/app/core/config.py`
- `backend/.env.example`
- `backend/app/services/model_client.py`
- `backend/tests/test_story_5_5.py`

### Change Log

- Story 5.5: configurable fallback models; automatic fallback after primary failure; tests.

### Review Findings

- [x] [Review][Defer] Misconfigured env where `ANALYTICS_MODEL` equals `ANALYTICS_MODEL_FALLBACK` (or vision pair) forces a redundant second full phase on primary failure — low risk; consider a startup warning or `model_validator` later [`backend/app/services/model_client.py` / `config.py`] — deferred, pre-existing ops hygiene
- [x] [Review][Defer] Optional FastAPI integration test asserting HTTP 503 + `error_type: model_unavailable` after simulated double model failure — story AC3 satisfied by `ModelUnavailableError` + `main.py` handler; extra test deferred

---

## Story completion status

- **Status:** done  
- **Note:** Code review (2026-03-31): no patch or decision items; deferrals recorded above. Implementation complete; backend pytest 350 passed.
