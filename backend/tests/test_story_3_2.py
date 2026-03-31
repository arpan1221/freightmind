"""
Tests for Story 3.2 — Normalisation Layer (mode, country, date, weight)

Verifies:
- AC1: Shipment mode mapped to canonical vocabulary; unrecognised → NOT_FOUND (FR15)
- AC2: Country name mapped to dataset vocabulary; unrecognised → NOT_FOUND (FR16)
- AC3: Date parsed to YYYY-MM-DD ISO 8601; unparseable → NOT_FOUND (FR17)
- AC4: Weight converted to kilograms; unparseable → NOT_FOUND (FR18)
"""
import os

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_tests")

import pytest
from app.agents.extraction.normaliser import ExtractionNormaliser, HIGH, NOT_FOUND


@pytest.fixture
def norm():
    return ExtractionNormaliser()


# ─────────────────────────────────────────────────────────────────────────────
# AC1: Shipment mode normalisation (FR15)
# ─────────────────────────────────────────────────────────────────────────────

class TestNormaliseMode:
    def test_air_freight_uppercase(self, norm):
        assert norm.normalise_mode("AIR FREIGHT") == ("Air", HIGH)

    def test_air_lowercase(self, norm):
        assert norm.normalise_mode("air") == ("Air", HIGH)

    def test_air_charter_hyphenated(self, norm):
        assert norm.normalise_mode("Air-charter") == ("Air Charter", HIGH)

    def test_air_charter_spaced(self, norm):
        assert norm.normalise_mode("air charter") == ("Air Charter", HIGH)

    def test_by_sea(self, norm):
        assert norm.normalise_mode("by sea") == ("Ocean", HIGH)

    def test_ocean_uppercase(self, norm):
        assert norm.normalise_mode("OCEAN") == ("Ocean", HIGH)

    def test_truck_lowercase(self, norm):
        assert norm.normalise_mode("truck") == ("Truck", HIGH)

    def test_road(self, norm):
        assert norm.normalise_mode("road") == ("Truck", HIGH)

    def test_unrecognised_returns_not_found(self, norm):
        assert norm.normalise_mode("cargo ship XL") == (None, NOT_FOUND)

    def test_none_returns_not_found(self, norm):
        assert norm.normalise_mode(None) == (None, NOT_FOUND)

    def test_empty_string_returns_not_found(self, norm):
        assert norm.normalise_mode("") == (None, NOT_FOUND)


# ─────────────────────────────────────────────────────────────────────────────
# AC2: Country normalisation (FR16)
# ─────────────────────────────────────────────────────────────────────────────

class TestNormaliseCountry:
    def test_drc_alias(self, norm):
        assert norm.normalise_country("DRC") == ("Congo (DRC)", HIGH)

    def test_full_drc_name(self, norm):
        assert norm.normalise_country("Democratic Republic of the Congo") == ("Congo (DRC)", HIGH)

    def test_nigeria(self, norm):
        assert norm.normalise_country("Nigeria") == ("Nigeria", HIGH)

    def test_ivory_coast(self, norm):
        assert norm.normalise_country("Ivory Coast") == ("Côte d'Ivoire", HIGH)

    def test_cote_divoire_with_accent(self, norm):
        assert norm.normalise_country("Côte d'Ivoire") == ("Côte d'Ivoire", HIGH)

    def test_cote_divoire_without_accent(self, norm):
        assert norm.normalise_country("Cote d'Ivoire") == ("Côte d'Ivoire", HIGH)

    def test_unknown_country_returns_not_found(self, norm):
        assert norm.normalise_country("Australia") == (None, NOT_FOUND)

    def test_none_returns_not_found(self, norm):
        assert norm.normalise_country(None) == (None, NOT_FOUND)

    def test_empty_string_returns_not_found(self, norm):
        assert norm.normalise_country("") == (None, NOT_FOUND)


# ─────────────────────────────────────────────────────────────────────────────
# AC3: Date normalisation (FR17)
# ─────────────────────────────────────────────────────────────────────────────

class TestNormaliseDate:
    def test_already_iso(self, norm):
        assert norm.normalise_date("2024-03-05") == ("2024-03-05", HIGH)

    def test_long_month_name(self, norm):
        assert norm.normalise_date("March 5, 2024") == ("2024-03-05", HIGH)

    def test_dmy_slash(self, norm):
        assert norm.normalise_date("05/03/2024") == ("2024-03-05", HIGH)

    def test_short_month_name(self, norm):
        assert norm.normalise_date("5 Mar 2024") == ("2024-03-05", HIGH)

    def test_dmy_dash(self, norm):
        assert norm.normalise_date("05-03-2024") == ("2024-03-05", HIGH)

    def test_unparseable_returns_not_found(self, norm):
        assert norm.normalise_date("not a date") == (None, NOT_FOUND)

    def test_none_returns_not_found(self, norm):
        assert norm.normalise_date(None) == (None, NOT_FOUND)

    def test_empty_string_returns_not_found(self, norm):
        assert norm.normalise_date("") == (None, NOT_FOUND)


# ─────────────────────────────────────────────────────────────────────────────
# AC4: Weight normalisation (FR18)
# ─────────────────────────────────────────────────────────────────────────────

class TestNormaliseWeight:
    def test_kg_passthrough(self, norm):
        value, conf = norm.normalise_weight("75 kg")
        assert value == pytest.approx(75.0)
        assert conf == HIGH

    def test_lbs_to_kg(self, norm):
        value, conf = norm.normalise_weight("250 lbs")
        assert value == pytest.approx(113.398, rel=1e-3)
        assert conf == HIGH

    def test_tonnes_to_kg(self, norm):
        value, conf = norm.normalise_weight("0.25 tonnes")
        assert value == pytest.approx(250.0)
        assert conf == HIGH

    def test_grams_to_kg(self, norm):
        value, conf = norm.normalise_weight("5000 g")
        assert value == pytest.approx(5.0)
        assert conf == HIGH

    def test_ounces_to_kg(self, norm):
        value, conf = norm.normalise_weight("10 oz")
        assert value == pytest.approx(0.283495, rel=1e-3)
        assert conf == HIGH

    def test_comma_thousands_separator(self, norm):
        value, conf = norm.normalise_weight("1,500 kg")
        assert value == pytest.approx(1500.0)
        assert conf == HIGH

    def test_unparseable_returns_not_found(self, norm):
        assert norm.normalise_weight("heavy") == (None, NOT_FOUND)

    def test_none_returns_not_found(self, norm):
        assert norm.normalise_weight(None) == (None, NOT_FOUND)

    def test_empty_string_returns_not_found(self, norm):
        assert norm.normalise_weight("") == (None, NOT_FOUND)


# ─────────────────────────────────────────────────────────────────────────────
# Robustness: no exceptions on arbitrary input (all ACs)
# ─────────────────────────────────────────────────────────────────────────────

class TestNormaliserRobustness:
    def test_no_exception_on_arbitrary_strings(self, norm):
        for method in [norm.normalise_mode, norm.normalise_country, norm.normalise_date]:
            assert method("!@#$%") == (None, NOT_FOUND)
            assert method("") == (None, NOT_FOUND)
            assert method(None) == (None, NOT_FOUND)

    def test_no_exception_on_weight_arbitrary(self, norm):
        assert norm.normalise_weight("!@#$%") == (None, NOT_FOUND)
        assert norm.normalise_weight("") == (None, NOT_FOUND)
        assert norm.normalise_weight(None) == (None, NOT_FOUND)
