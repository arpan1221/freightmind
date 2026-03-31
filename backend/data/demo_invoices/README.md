# Synthetic demo freight invoices (Story 6.4)

Fictional companies and amounts for **FreightMind** demos. Do not use as real commercial documents.

## Files (suggested order)

| Order | File | Role |
|------:|------|------|
| 1 | `demo-01-air-nigeria-linkage.pdf` | **Linkage:** `Air` + **Nigeria** — normalises to SCMS vocabulary; use for confirm → cross-table analytics vs `shipments`. |
| 2 | `demo-02-ocean-vietnam.pdf` | General extraction; Ocean + Vietnam (dataset coverage). |
| 3 | `demo-03-truck-zambia.pdf` | General extraction; Truck + Zambia. |
| 4 | `demo-04-low-confidence-paymentterms.png` | **Confidence demo:** payment terms rendered small/low-contrast — expect **LOW** (or similar) on `payment_terms` / related fields. |
| 5 | `demo-05-air-charter-haiti.jpg` | Raster path + **Air Charter** + Haiti. |
| 6 | `demo-06-no-insurance-line.png` | **NOT_FOUND demo:** no visible total insurance line — expect **`NOT_FOUND`** or **LOW** on `total_insurance_usd`. |

## Format coverage

- **PDF:** `demo-01` … `demo-03` (3 files)  
- **PNG:** `demo-04`, `demo-06`  
- **JPG:** `demo-05`

## Regenerating assets

From repository root:

```bash
uv run python backend/scripts/generate_demo_invoices.py
```

Requires **PyMuPDF** (`pymupdf`) from the backend environment.

## Manual verification (OpenRouter)

With `OPENROUTER_API_KEY` set and the app running:

1. Upload each file via the Upload panel (`POST /extract`).
2. Confirm `demo-01-air-nigeria-linkage.pdf` extracts plausible header fields; normalise + confirm.
3. Ask a cross-table question (e.g. compare confirmed invoice freight to dataset average for **Air** / **Nigeria**).
4. For `demo-04` / `demo-06`, confirm the confidence badges show at least one **LOW** or **NOT_FOUND** on the intended field (vision output may vary slightly by model).

Vision models are non-deterministic; if a badge does not match intent, adjust prompts or re-run `generate_demo_invoices.py` and re-test.

## Automated build note

Assets and layout were generated and reviewed in-repo; **live** `POST /extract` calls were not executed in the automated test suite. Confirm behaviour with a valid `OPENROUTER_API_KEY` before a graded demo.
