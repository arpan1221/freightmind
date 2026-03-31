import math
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
            result = round(float(number_str) * factor, 6)
            if math.isinf(result):
                return None, NOT_FOUND
            return result, HIGH
        except (KeyError, ValueError):
            return None, NOT_FOUND
