# Story 5.6: Error toast UI with countdown timer

Status: done

<!-- Ultimate context engine analysis completed — comprehensive developer guide created -->

## Story

As a logistics analyst,
I want to see a clear error toast when something goes wrong, with a countdown timer when I need to wait before retrying,
so that I'm informed of failures without being left staring at a broken UI.

## Acceptance Criteria

1. **Structured errors surface as a toast (UX-DR4)**  
   **Given** any API call returns an HTTP error whose JSON body matches the backend `ErrorResponse` shape (`error`, `error_type`, `message`, optional `detail`, optional `retry_after`)  
   **When** the frontend receives it (typically via Axios on 4xx/5xx)  
   **Then** an **error toast** is shown with the server’s **`message`** string — not a generic Axios/network string unless the body is not parseable.

2. **Rate limit: countdown + retry affordance (FR31, UX-DR4)**  
   **Given** the parsed error includes **`retry_after`** as a positive integer (seconds)  
   **When** the toast is shown  
   **Then** a **visible countdown** ticks from `retry_after` down to `0` at one-second granularity (or smoother UX if implemented, but must reach zero correctly).

3. **Countdown ends → user can retry**  
   **Given** the countdown is active for a **rate-limited** action  
   **When** the countdown reaches **zero**  
   **Then** the toast **updates** to indicate the user may retry (e.g. copy change or removal of “wait” state)  
   **And** the **primary input for that action** is **re-enabled** (analytics: chat textarea + send; documents: drop zone / file input and confirm — whichever was blocked by the error).

4. **No `retry_after` → dismiss only**  
   **Given** the error has **no** `retry_after` (null/undefined/missing) or it is not a positive integer  
   **When** the toast is displayed  
   **Then** **no** countdown is shown  
   **And** the user can **dismiss** the toast (explicit dismiss control; clicking outside optional but not required).

5. **Coverage**  
   **Given** the main user flows (analytics query, document extract, confirm)  
   **When** any of these returns an `ErrorResponse`  
   **Then** behaviour above applies consistently (shared toast component or shared helper — avoid three different error UIs).

## Tasks / Subtasks

- [x] **Task 1 — Parse `ErrorResponse` from Axios failures (AC: 1, 5)**  
  - [x] Add a small helper (e.g. `getErrorResponseFromUnknown(err: unknown): ErrorResponse | null`) that reads `axios.isAxiosError` → `response?.data` and validates **`error === true`** and **`message`** (string) before treating as `ErrorResponse`.  
  - [x] Fallback: if not structured, show a safe generic message for network/unknown errors.  
  - [x] Reuse [Source: `frontend/src/types/api.ts`] `ErrorResponse` interface — do not duplicate shapes.

- [x] **Task 2 — `ErrorToast` UI component (AC: 1–4)**  
  - [x] New component under `frontend/src/components/` (e.g. `ErrorToast.tsx`): fixed/stacked position, high contrast, **`role="alert"`** or **`aria-live="assertive"`** for the message.  
  - [x] Props: `message`, `retryAfterSeconds: number | null`, `onDismiss`, optional `onCountdownComplete`.  
  - [x] If `retryAfterSeconds` is a positive number: show countdown + disable dismiss **until** countdown completes **or** allow dismiss but keep inputs disabled per AC3 — **prefer**: countdown visible, user can dismiss toast visually but AC3 requires inputs disabled until zero — implement so **primary controls stay disabled until countdown ends** (clearly document in code).  
  - [x] Styling: Tailwind, consistent with existing red alert blocks in [Source: `frontend/src/components/ChatPanel.tsx`] (inline error) — migrate inline errors to toast where appropriate so **one** pattern exists.

- [x] **Task 3 — Wire `useAnalytics` (AC: 1–3, 5)**  
  - [x] Replace `catch` branch that only uses `err instanceof Error ? err.message` with structured parsing + toast state: `{ message, retryAfter }`.  
  - [x] While `retryAfter > 0` (or countdown running): set **`isQuerying`** or a dedicated **`isRateLimited`** so textarea + Ask button stay disabled.  
  - [x] On countdown end: re-enable inputs; update toast copy per AC3.

- [x] **Task 4 — Wire `useExtraction` (AC: 1–3, 5)**  
  - [x] Extend `extractErrorMessage` / catch paths to prefer `ErrorResponse.message` from Axios body.  
  - [x] Surface errors via same `ErrorToast` pattern (state lifted to hook or panel).  
  - [x] Apply countdown disable to extract/upload and confirm flows as applicable.

- [x] **Task 5 — Optional: schema / global API failures**  
  - [x] [Source: `frontend/src/app/page.tsx`] currently swallows schema errors — consider showing toast on schema load failure **if** the response is `ErrorResponse` (optional stretch; AC says “any API call” — include if low effort).

- [x] **Task 6 — Tests**  
  - [x] Vitest + RTL: `ErrorToast` renders message; with `retryAfterSeconds={3}` shows “3” then decrements (use fake timers).  
  - [x] Helper unit test: mock Axios error object → `message` + `retry_after` extracted.  
  - [x] Follow [Source: `frontend/src/components/SqlDisclosure.test.tsx`] patterns and [Source: `frontend/vitest.config.ts`].

### Review Findings

- [x] [Review][Patch] Avoid overlapping fixed toasts — schema (`page.tsx`) and panel (`ChatPanel` / `UploadPanel`) each render `ErrorToast` with the same fixed position and `z-50`; concurrent errors can obscure each other. Prefer a single toast host, stacked offsets, or differentiated `z-index` / placement. [`frontend/src/app/page.tsx`, `frontend/src/components/ErrorToast.tsx`] — fixed 2026-03-31: `placement="top"` for schema toast; panels keep default bottom.

- [x] [Review][Defer] Schema fetch failure with `retry_after` shows countdown but does not auto-refetch `/api/schema` when the timer ends (one-shot `useEffect`); acceptable for optional Task 5 stretch — user can dismiss and refresh.

## Dev Notes

### Brownfield — current frontend

- [Source: `frontend/src/lib/api.ts`] — Axios instance with `baseURL`; **no** response interceptor yet — errors are thrown to callers; implementation belongs in hooks + shared parser.  
- [Source: `frontend/src/hooks/useAnalytics.ts`] — `catch` uses generic `Error.message`; **does not** read `response.data.message` from API envelope.  
- [Source: `frontend/src/hooks/useExtraction.ts`] — `extractErrorMessage` already prefers `response.data.message` but does not handle **`retry_after`** or toast UX.  
- [Source: `frontend/src/components/ChatPanel.tsx`] — inline `{error && <div className="bg-red-50"…`}; replace or augment with toast so errors are visible without scrolling the thread (toast fixed position).

### Backend contract (already implemented / expected)

- [Source: `backend/app/schemas/common.py`] — `ErrorResponse` with `message`, `retry_after: int | None`.  
- Stories **5.1**–**5.3**: rate limits return `error_type: "rate_limit"` with `retry_after` — frontend must **not** hard-code only `rate_limit`; any error with `retry_after` should show countdown.

### Architecture compliance

- [Source: `_bmad-output/planning-artifacts/architecture.md`] — **Structured Error Shape** — `{error, message, retry_after}` across endpoints; single toast pattern matches this.  
- **UX-DR4** — Error toast + countdown when `retry_after` present [Source: `_bmad-output/planning-artifacts/epics.md` § Epic 5 / UX requirements].

### Dependencies

| Story | Why |
|-------|-----|
| **5.1** | `ErrorResponse` JSON shape on all endpoints |
| **5.3** | `retry_after` on rate limit responses |

### Anti-patterns

- Do not show raw stack traces or full `detail` object in the toast by default — **`message`** only unless product asks otherwise.  
- Do not duplicate `ErrorResponse` TypeScript types — extend `frontend/src/types/api.ts` if a field is missing.  
- Avoid blocking the entire app for one panel’s rate limit — disable **only** the relevant panel’s primary controls.

### Files likely touched

| Path | Role |
|------|------|
| `frontend/src/components/ErrorToast.tsx` | New toast UI |
| `frontend/src/lib/errorResponse.ts` or `utils/` | Axios → `ErrorResponse` parser |
| `frontend/src/hooks/useAnalytics.ts` | Structured errors + countdown disable |
| `frontend/src/hooks/useExtraction.ts` | Same |
| `frontend/src/components/ChatPanel.tsx` | Render toast, remove/inline duplicate error UI |
| `frontend/src/components/UploadPanel.tsx` | Render toast |
| `frontend/src/**/*.test.tsx` | Tests |

### Previous story intelligence

- [Source: `_bmad-output/implementation-artifacts/5-5-automatic-fallback-model-on-primary-model-failure.md`] — backend may still return `model_unavailable` without `retry_after`; toast shows dismiss-only path (AC4).

### Project context reference

No `project-context.md` in repo; use this file + `epics.md` Story 5.6 + `architecture.md` structured errors section.

### References

- [Epics — Story 5.6](../planning-artifacts/epics.md)  
- [PRD — FR31](../planning-artifacts/prd.md) (if needed)  
- [Architecture — Structured error shape](../planning-artifacts/architecture.md)

## Dev Agent Record

### Agent Model Used

Composer (Cursor agent)

### Debug Log References

### Completion Notes List

- Added `frontend/src/lib/errorResponse.ts` (`getErrorResponseFromUnknown`, `normalizeRetryAfterSeconds`, `getUserFacingErrorMessage`).
- Added `ErrorToast` with `role="alert"`, `aria-live="assertive"`, countdown, dismiss disabled until countdown ends when `retry_after` applies; then “You may retry now.”
- `useAnalytics`: toast state + `rateLimited` → `inputDisabled`; chat thread inline error strip removed; SQL `detail` still shown in thread when present.
- `useExtraction`: `errorToast` + `rateLimited`; `extractDisabled` / `confirmDisabled`; inline error blocks removed from `UploadPanel`.
- `page.tsx`: schema fetch failures show the same toast pattern.
- Vitest: `errorResponse.test.ts`, `ErrorToast.test.tsx`.

### File List

- `frontend/src/lib/errorResponse.ts`
- `frontend/src/lib/errorResponse.test.ts`
- `frontend/src/components/ErrorToast.tsx`
- `frontend/src/components/ErrorToast.test.tsx`
- `frontend/src/hooks/useAnalytics.ts`
- `frontend/src/hooks/useExtraction.ts`
- `frontend/src/components/ChatPanel.tsx`
- `frontend/src/components/UploadPanel.tsx`
- `frontend/src/app/page.tsx`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Change Log

- 2026-03-31: Story 5.6 — shared ErrorResponse parsing, ErrorToast with countdown, wired analytics/extraction/schema; tests added.
- 2026-03-31: Code review patch — `ErrorToast` `placement` prop (`top` for schema, `bottom` default); ESLint scope for countdown effect; story marked done.

---

## Story completion status

- **Status:** done  
- **Note:** Code review patch applied; ACs satisfied.

---

### Latest technical notes (2026)

- Use **axios** `isAxiosError` from `axios` for type narrowing.  
- Prefer **`@testing-library/react`** `userEvent` + **`vi.useFakeTimers()`** for countdown tests.  
- Next.js **16** app router — keep components client-only where hooks run (`"use client"`).
