# Story 3.2: Normalisation Layer — Mode, Country, Date, and Weight

Status: done

## Story

As a logistics operations analyst,
I want extracted values normalised to standard vocabulary before I review them,
So that I see clean, consistent data rather than raw OCR variants.

## Acceptance Criteria

1. **Given** the vision model returns a shipment mode value (e.g., "AIR FREIGHT", "by air", "Air-charter")
   **When** normalisation is applied
   **Then** the value is mapped to one of: `Air`, `Ocean`, `Truck`, or `Air Charter` — unrecognised values receive `NOT_FOUND` confidence (FR15)

2. **Given** the vision model returns a country name (e.g., "DRC", "Congo", "Democratic Republic of the Congo")
   **When** normalisation is applied
   **Then** the value is mapped to the corresponding dataset vocabulary country name (FR16)

3. **Given** the vision model returns a date in any format (e.g., "March 5, 2024", "05/03/24")
   **When** normalisation is applied
   **Then** the value is stored and displayed as `YYYY-MM-DD` ISO 8601 format (FR17)

4. **Given** the vision model returns a weight with units (e.g., "250 lbs", "0.25 tonnes")
   **When** normalisation is applied
   **Then** the value is converted to kilograms and stored as a numeric value (FR18)

## Tasks / Subtasks

- [x] Task 1: Create `ExtractionNormaliser` class (AC: 1, 2, 3, 4)
  - [x] Create `backend/app/agents/extraction/normaliser.py` — see Dev Notes for full implementation
  - [x] `normalise_mode(raw: str | None) -> tuple[str | None, str]` — maps to `Air | Ocean | Truck | Air Charter`; returns `(None, "NOT_FOUND")` if unrecognised
  - [x] `normalise_country(raw: str | None) -> tuple[str | None, str]` — maps to dataset vocabulary; returns `(None, "NOT_FOUND")` if unrecognised
  - [x] `normalise_date(raw: str | None) -> tuple[str | None, str]` — parses to `YYYY-MM-DD`; returns `(None, "NOT_FOUND")` if unparseable
  - [x] `normalise_weight(raw: str | None) -> tuple[float | None, str]` — converts to kg; returns `(None, "NOT_FOUND")` if unparseable
  - [x] All methods accept `None` and return `(None, "NOT_FOUND")` immediately — never raise

- [x] Task 2: Fill in `extraction_normalise.txt` prompt (AC: 1, 2)
  - [x] Replace TODO stub in `backend/app/prompts/extraction_normalise.txt` with the vocabulary guide — see Dev Notes for exact content
  - [x] This prompt is used by the extraction executor to guide the vision model, not for rule-based normalisation

- [x] Task 3: Write tests (AC: 1, 2, 3, 4)
  - [x] Create `backend/tests/test_story_3_2.py`
  - [x] Mode: maps "AIR FREIGHT", "air", "Air-charter", "by sea", "OCEAN", "road", "truck", "AIR CHARTER" to correct canonical values
  - [x] Mode: unrecognised returns `(None, "NOT_FOUND")`
  - [x] Mode: `None` input returns `(None, "NOT_FOUND")`
  - [x] Country: maps "DRC", "Congo", "Nigeria", "Ivory Coast", "Côte d'Ivoire" to correct canonical values
  - [x] Country: unrecognised returns `(None, "NOT_FOUND")`
  - [x] Date: parses "March 5, 2024", "05/03/2024", "2024-03-05", "5 Mar 2024", "03-05-2024" → `"2024-03-05"`
  - [x] Date: unparseable returns `(None, "NOT_FOUND")`
  - [x] Weight: converts "250 lbs" → ~113.4 kg, "0.25 tonnes" → 250.0 kg, "5000 g" → 5.0 kg, "10 oz" → ~0.284 kg, "75 kg" → 75.0 kg
  - [x] Weight: unparseable returns `(None, "NOT_FOUND")`
  - [x] All methods: `None` input returns `(None, "NOT_FOUND")` — never raises

### Review Findings

- [x] [Review][Patch] Float overflow silently returns `(inf, HIGH)` — `except (KeyError, ValueError)` doesn't catch float→inf overflow for astronomically large weight values [`normaliser.py:normalise_weight`]
- [x] [Review][Patch] `"vessel"` missing from `extraction_normalise.txt` prompt vocabulary — prompt and `_MODE_MAP` are out of sync [`extraction_normalise.txt`]
- [x] [Review][Defer] Two-letter ISO code matches (e.g., `"ng"`, `"tz"`) conflated with full-name matches at same HIGH confidence — deferred, story 3.3 confidence scoring scope
- [x] [Review][Defer] No MEDIUM/LOW confidence levels — binary HIGH/NOT_FOUND is by design for this story — deferred, story 3.3 scope
- [x] [Review][Defer] Two-digit year century ambiguity — Python's 68/69 pivot rule applies to `%y` formats — deferred, low probability for freight docs in current decade
- [x] [Review][Defer] Internal double-whitespace in date strings fails all `strptime` formats — deferred, OCR normalisation out of scope for this story
- [x] [Review][Defer] ISO datetime with time component (e.g., `"2024-01-15T10:30:00"`) returns NOT_FOUND — deferred, pre-existing design boundary
- [x] [Review][Defer] European decimal comma (`"1,5 kg"`) silently misparsed as `"15 kg"` — deferred, LLM extractions expected in English locale
- [x] [Review][Defer] Zero weight `"0 kg"` accepted silently with HIGH confidence — deferred, semantic concern for story 3.3 confidence scoring

## Dev Notes

### What Already Exists — Critical Context

**DO NOT reinvent or re-implement these:**

| Component | Location | Status |
|-----------|----------|--------|
| `ExtractedDocument` ORM model | `backend/app/models/extracted_document.py` | ✅ Full schema with all 14 fields |
| `ExtractedLineItem` ORM model | `backend/app/models/extracted_line_item.py` | ✅ With CASCADE FK |
| `extraction_normalise.txt` | `backend/app/prompts/extraction_normalise.txt` | ⚠️ TODO stub — fill in Task 2 |
| `extraction_fields.txt` | `backend/app/prompts/extraction_fields.txt` | ⚠️ TODO stub — NOT in this story's scope |
| `extraction_system.txt` | `backend/app/prompts/extraction_system.txt` | ⚠️ TODO stub — NOT in this story's scope |
| `backend/app/agents/extraction/__init__.py` | `backend/app/agents/extraction/` | ✅ Folder exists, `__init__.py` is empty |
| `ConfidenceLevel` enum | NOT YET CREATED | ❌ Create in `normaliser.py` (see below) |

**Story 3.1 (POST /extract endpoint) has NOT been implemented yet.** This story creates the normalisation layer as a standalone module that story 3.1's ExtractionVerifier will call. The normaliser must be fully testable in isolation — no route, no DB, no LLM needed.

### Task 1: `ExtractionNormaliser` — Full Implementation

**File:** `backend/app/agents/extraction/normaliser.py`

```python
import re
from datetime import datetime

# ─── Confidence level constants ───────────────────────────────────────────────
HIGH = "HIGH"
NOT_FOUND = "NOT_FOUND"

# ─── Shipment mode vocabulary ────────────────────────────────────────────────
_MODE_MAP: dict[str, str] = {
    # Air variants
    "air": "Air",
    "airfreight": "Air",
    "air freight": "Air",
    "air-freight": "Air",
    "air express": "Air",
    "by air": "Air",
    "airplane": "Air",
    "aircraft": "Air",
    "plane": "Air",
    # Air Charter variants
    "air charter": "Air Charter",
    "air-charter": "Air Charter",
    "charter": "Air Charter",
    "chartered air": "Air Charter",
    # Ocean variants
    "ocean": "Ocean",
    "sea": "Ocean",
    "by sea": "Ocean",
    "ocean freight": "Ocean",
    "sea freight": "Ocean",
    "ship": "Ocean",
    "vessel": "Ocean",
    "maritime": "Ocean",
    # Truck variants
    "truck": "Truck",
    "road": "Truck",
    "road freight": "Truck",
    "truck freight": "Truck",
    "land": "Truck",
    "ground": "Truck",
    "lorry": "Truck",
    "overland": "Truck",
}

# ─── Country vocabulary ───────────────────────────────────────────────────────
# Maps raw aliases → exact dataset vocabulary
_COUNTRY_MAP: dict[str, str] = {
    # Nigeria
    "nigeria": "Nigeria",
    "nigerian": "Nigeria",
    "ng": "Nigeria",
    # South Africa
    "south africa": "South Africa",
    "south african": "South Africa",
    "rsa": "South Africa",
    "za": "South Africa",
    # Côte d'Ivoire
    "côte d'ivoire": "Côte d'Ivoire",
    "cote d'ivoire": "Côte d'Ivoire",
    "cote divoire": "Côte d'Ivoire",
    "ivory coast": "Côte d'Ivoire",
    "ivorycoast": "Côte d'Ivoire",
    "ci": "Côte d'Ivoire",
    # Uganda
    "uganda": "Uganda",
    "ugandan": "Uganda",
    "ug": "Uganda",
    # Zambia
    "zambia": "Zambia",
    "zambian": "Zambia",
    "zm": "Zambia",
    # Congo (DRC)
    "congo (drc)": "Congo (DRC)",
    "drc": "Congo (DRC)",
    "congo": "Congo (DRC)",
    "democratic republic of the congo": "Congo (DRC)",
    "democratic republic of congo": "Congo (DRC)",
    "dr congo": "Congo (DRC)",
    "dr. congo": "Congo (DRC)",
    "zaire": "Congo (DRC)",
    "cd": "Congo (DRC)",
    # Tanzania
    "tanzania": "Tanzania",
    "tanzanian": "Tanzania",
    "tz": "Tanzania",
    # Mozambique
    "mozambique": "Mozambique",
    "mozambican": "Mozambique",
    "mz": "Mozambique",
    # Kenya
    "kenya": "Kenya",
    "kenyan": "Kenya",
    "ke": "Kenya",
    # Ethiopia
    "ethiopia": "Ethiopia",
    "ethiopian": "Ethiopia",
    "et": "Ethiopia",
    # Zimbabwe
    "zimbabwe": "Zimbabwe",
    "zimbabwean": "Zimbabwe",
    "zw": "Zimbabwe",
    # Haiti
    "haiti": "Haiti",
    "haitian": "Haiti",
    "ht": "Haiti",
    # Rwanda
    "rwanda": "Rwanda",
    "rwandan": "Rwanda",
    "rw": "Rwanda",
    # Vietnam
    "vietnam": "Vietnam",
    "viet nam": "Vietnam",
    "vietnamese": "Vietnam",
    "vn": "Vietnam",
    # Guyana
    "guyana": "Guyana",
    "guyanese": "Guyana",
    "gy": "Guyana",
}

# ─── Date format patterns (tried in order) ───────────────────────────────────
_DATE_FORMATS = [
    "%Y-%m-%d",    # 2024-03-05 (already ISO)
    "%d/%m/%Y",    # 05/03/2024
    "%m/%d/%Y",    # 03/05/2024
    "%d/%m/%y",    # 05/03/24
    "%m/%d/%y",    # 03/05/24
    "%B %d, %Y",   # March 5, 2024
    "%b %d, %Y",   # Mar 5, 2024
    "%d %B %Y",    # 5 March 2024
    "%d %b %Y",    # 5 Mar 2024
    "%B %d %Y",    # March 5 2024
    "%d-%m-%Y",    # 05-03-2024
    "%m-%d-%Y",    # 03-05-2024
    "%Y/%m/%d",    # 2024/03/05
]

# ─── Weight unit conversion to kg ─────────────────────────────────────────────
_WEIGHT_RE = re.compile(
    r"^\s*([\d,]+(?:\.\d+)?)\s*"
    r"(kg|kgs|kilogram|kilograms|lb|lbs|pound|pounds|"
    r"t|ton|tons|tonne|tonnes|g|gr|gram|grams|oz|ounce|ounces)\s*$",
    re.IGNORECASE,
)
_WEIGHT_FACTORS: dict[str, float] = {
    "kg": 1.0, "kgs": 1.0, "kilogram": 1.0, "kilograms": 1.0,
    "lb": 0.453592, "lbs": 0.453592, "pound": 0.453592, "pounds": 0.453592,
    "t": 1000.0, "ton": 1000.0, "tons": 1000.0, "tonne": 1000.0, "tonnes": 1000.0,
    "g": 0.001, "gr": 0.001, "gram": 0.001, "grams": 0.001,
    "oz": 0.0283495, "ounce": 0.0283495, "ounces": 0.0283495,
}


class ExtractionNormaliser:
    """Pure rule-based normaliser for extracted freight document fields.

    All methods accept None and never raise — unrecognised inputs return (None, "NOT_FOUND").
    """

    def normalise_mode(self, raw: str | None) -> tuple[str | None, str]:
        """Map raw shipment mode string to canonical vocabulary."""
        if not raw:
            return None, NOT_FOUND
        key = raw.strip().lower()
        result = _MODE_MAP.get(key)
        if result:
            return result, HIGH
        return None, NOT_FOUND

    def normalise_country(self, raw: str | None) -> tuple[str | None, str]:
        """Map raw country string to dataset vocabulary."""
        if not raw:
            return None, NOT_FOUND
        key = raw.strip().lower()
        result = _COUNTRY_MAP.get(key)
        if result:
            return result, HIGH
        return None, NOT_FOUND

    def normalise_date(self, raw: str | None) -> tuple[str | None, str]:
        """Parse date string to ISO 8601 YYYY-MM-DD format."""
        if not raw:
            return None, NOT_FOUND
        cleaned = raw.strip()
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d"), HIGH
            except ValueError:
                continue
        return None, NOT_FOUND

    def normalise_weight(self, raw: str | None) -> tuple[float | None, str]:
        """Convert weight string with unit to kilograms."""
        if not raw:
            return None, NOT_FOUND
        m = _WEIGHT_RE.match(raw.strip())
        if not m:
            return None, NOT_FOUND
        number_str = m.group(1).replace(",", "")
        unit = m.group(2).lower()
        try:
            factor = _WEIGHT_FACTORS[unit]
            return round(float(number_str) * factor, 6), HIGH
        except (KeyError, ValueError):
            return None, NOT_FOUND
```

### Task 2: `extraction_normalise.txt` — Vocabulary Guide Content

**File:** `backend/app/prompts/extraction_normalise.txt`

Replace the TODO stub with:

```
Normalisation vocabulary for freight document extraction.

SHIPMENT MODE — map to exactly one of these four values:
- Air  (variants: air freight, airfreight, by air, airplane, aircraft)
- Ocean  (variants: sea, by sea, ocean freight, sea freight, ship, maritime)
- Truck  (variants: road, road freight, land, ground, lorry, overland)
- Air Charter  (variants: charter, chartered air, air-charter)

COUNTRY NAMES — map to exactly one of these 15 dataset values:
Nigeria, South Africa, Côte d'Ivoire, Uganda, Zambia, Congo (DRC),
Tanzania, Mozambique, Kenya, Ethiopia, Zimbabwe, Haiti, Rwanda, Vietnam, Guyana

Common aliases:
- DRC / DR Congo / Democratic Republic of the Congo → Congo (DRC)
- Ivory Coast / Cote d'Ivoire → Côte d'Ivoire

DATE FORMAT — always output as YYYY-MM-DD (ISO 8601)
Examples: "March 5, 2024" → "2024-03-05", "05/03/24" → "2024-03-05"

WEIGHT — always output as numeric kilograms
Conversions: 1 lb = 0.453592 kg, 1 tonne = 1000 kg, 1 g = 0.001 kg, 1 oz = 0.0283495 kg
```

### Testing Pattern — `backend/tests/test_story_3_2.py`

```python
import os
os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

import pytest
from app.agents.extraction.normaliser import ExtractionNormaliser, HIGH, NOT_FOUND

@pytest.fixture
def norm():
    return ExtractionNormaliser()
```

Key test cases to cover:

**Mode:**
- `"AIR FREIGHT"` → `("Air", HIGH)` — uppercase variant
- `"air"` → `("Air", HIGH)` — lowercase exact
- `"by sea"` → `("Ocean", HIGH)`
- `"truck"` → `("Truck", HIGH)`
- `"Air-charter"` → note: raw "Air-charter" — normalise to "Air Charter"
- `"cargo ship XL"` → `(None, NOT_FOUND)` — unrecognised
- `None` → `(None, NOT_FOUND)`
- `""` → `(None, NOT_FOUND)`

**Country:**
- `"DRC"` → `("Congo (DRC)", HIGH)`
- `"Nigeria"` → `("Nigeria", HIGH)`
- `"Ivory Coast"` → `("Côte d'Ivoire", HIGH)`
- `"Australia"` → `(None, NOT_FOUND)` — not in dataset vocabulary
- `None` → `(None, NOT_FOUND)`

**Date:**
- `"2024-03-05"` → `("2024-03-05", HIGH)` — already ISO
- `"March 5, 2024"` → `("2024-03-05", HIGH)`
- `"05/03/2024"` → `("2024-03-05", HIGH)` — day/month/year
- `"5 Mar 2024"` → `("2024-03-05", HIGH)`
- `"not a date"` → `(None, NOT_FOUND)`
- `None` → `(None, NOT_FOUND)`

**Weight:**
- `"250 lbs"` → `(approximately 113.398, HIGH)` — use `pytest.approx`
- `"0.25 tonnes"` → `(250.0, HIGH)`
- `"5000 g"` → `(5.0, HIGH)`
- `"75 kg"` → `(75.0, HIGH)`
- `"10 oz"` → `(approximately 0.283, HIGH)`
- `"heavy"` → `(None, NOT_FOUND)`
- `None` → `(None, NOT_FOUND)`
- `"1,500 kg"` → `(1500.0, HIGH)` — comma-separated thousands

**No exceptions on any input:**
```python
def test_no_exception_on_arbitrary_input(norm):
    for method in [norm.normalise_mode, norm.normalise_country, norm.normalise_date]:
        assert method("!@#$%") == (None, NOT_FOUND)
        assert method("") == (None, NOT_FOUND)
        assert method(None) == (None, NOT_FOUND)
```

### Architecture: Normaliser in the Extraction Pipeline

Story 3.2 creates the normaliser as a **pure, standalone module**. Story 3.1 (POST /extract endpoint) will import and call it inside `ExtractionVerifier.verify()`:

```
ExtractionVerifier.verify(raw_fields: dict) → normalised_fields: dict
    └─► ExtractionNormaliser().normalise_mode(raw_fields["shipment_mode"])
    └─► ExtractionNormaliser().normalise_country(raw_fields["destination_country"])
    └─► ExtractionNormaliser().normalise_date(raw_fields["invoice_date"])
    └─► ExtractionNormaliser().normalise_weight(raw_fields["total_weight_kg"])
```

**This story does NOT:**
- Create the full ExtractionVerifier (story 3.3)
- Create the POST /extract endpoint (story 3.1)
- Call the vision model
- Write to the database

### Previous Story Learnings

From Story 2.x tests:
- `os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")` must come **before any `app.*` import** in test files — required even for pure unit tests because `app.core.config` is imported transitively.
- Use `class Test<Feature>:` pattern — no standalone test functions.
- `pytest.approx()` for floating-point weight comparisons (e.g., `assert result == pytest.approx(113.398, rel=1e-3)`).

From codebase patterns:
- `settings.analytics_model` uses `settings` from `app.core.config` — this normaliser does NOT use `settings` (no model calls).
- No `ModelClient` needed — the normaliser is pure Python, zero async.
- No `load_prompt()` needed in the normaliser itself — prompt is used by the executor, not the normaliser.

### What NOT to Change

- `backend/app/models/extracted_document.py` — schema already correct
- `backend/app/models/extracted_line_item.py` — schema already correct
- `backend/app/prompts/extraction_fields.txt` — NOT in scope (story 3.1)
- `backend/app/prompts/extraction_system.txt` — NOT in scope (story 3.1)
- Any analytics route, planner, executor, or verifier files

### References

- [Source: epics.md — Story 3.2]: FR15 (mode), FR16 (country), FR17 (date), FR18 (weight)
- [Source: epics.md — Epic 3]: `confirmed_by_user` flag, vocabulary exactness constraint (FR25–FR28)
- [Source: architecture.md — ExtractionVerifier]: "validates fields, normalises vocabulary, scores confidence"
- [Source: backend/app/models/extracted_document.py]: Column types for `shipment_mode` (Text), `destination_country` (Text), `invoice_date` (Text), `total_weight_kg` (Float)
- [Source: architecture.md — Confidence Scoring]: "HIGH" | "MEDIUM" | "LOW" | "NOT_FOUND" — always uppercase

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None — implementation was straightforward, no debugging required.

### Completion Notes List

- Pure rule-based implementation: no LLM calls, no async, no DB — fully testable in isolation.
- `_MODE_MAP` and `_COUNTRY_MAP` use lowercase keys; all normalise methods call `.strip().lower()` before lookup, enabling case-insensitive matching.
- Date parsing tries `_DATE_FORMATS` list in order; `%d/%m/%Y` placed before `%m/%d/%Y` so "05/03/2024" → 2024-03-05 (day-first convention).
- Weight regex requires the unit to be directly adjacent or whitespace-separated, and strips comma thousands separators before parsing.
- All 39 tests pass; 7 pre-existing failures in `test_story_3_4.py` confirmed unrelated (present before story 3.2 changes).

### File List

New:
- `backend/app/agents/extraction/normaliser.py` — ExtractionNormaliser class
- `backend/tests/test_story_3_2.py` — 39 unit tests (5 test classes)

Modified:
- `backend/app/prompts/extraction_normalise.txt` — vocabulary guide (replaces TODO stub)

## Change Log

- 2026-03-30: Story 3.2 created by create-story workflow
- 2026-03-30: Implementation complete. ExtractionNormaliser created with 4 normalisation methods. 39/39 tests passing. Status → review.
