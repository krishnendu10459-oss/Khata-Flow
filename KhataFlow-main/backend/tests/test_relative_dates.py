"""
Tests for deterministic relative date parsing using an injectable reference date / clock.
Ensures ISO 8601 string formatting and null defaults when no date is mentioned.
"""

from datetime import date
import pytest
from backend.services.intent_engine import IntentEngine, EntityExtractor


@pytest.fixture
def fixed_date():
    return date(2026, 11, 13)  # Friday, 13 November 2026


@pytest.fixture
def engine(fixed_date):
    return IntentEngine(reference_date=fixed_date)


class TestRelativeDateHandling:
    def test_no_date_specified_returns_null(self, engine):
        """When no date is spoken, result must have date=null (not guessing)."""
        res = engine.parse("Ramesh ka 500 udhaar")
        assert res["date"] is None

    def test_kal_yields_yesterday(self, engine):
        """'kal' in past context indicates yesterday (2026-11-12)."""
        res = engine.parse("Mohan ko kal 300 diye")
        assert res["intent"] == "RECORD_PAYMENT"
        assert res["customer_name"] == "Mohan"
        assert res["amount"] == 300.0
        assert res["date"] == "2026-11-12"

    def test_parso_yields_day_before_yesterday(self, engine):
        """'parso' indicates 2 days ago (2026-11-11)."""
        res = engine.parse("Suresh ne parso 500 diye")
        assert res["intent"] == "RECORD_PAYMENT"
        assert res["customer_name"] == "Suresh"
        assert res["amount"] == 500.0
        assert res["date"] == "2026-11-11"

    def test_aaj_yields_reference_date(self, engine):
        """'aaj' indicates reference date (2026-11-13)."""
        res = engine.parse("Aaj ka total udhaar batao")
        assert res["intent"] == "DAILY_SUMMARY"
        assert res["date"] == "2026-11-13"

    def test_devanagari_relative_dates(self, engine):
        """Hindi Devanagari relative date keywords."""
        res_kal = engine.parse("मोहन ने कल 400 जमा किये")
        assert res_kal["date"] == "2026-11-12"

        res_parso = engine.parse("सुरेश ने परसों 200 दिए")
        assert res_parso["date"] == "2026-11-11"

        res_aaj = engine.parse("आज का हिसाब बताओ")
        assert res_aaj["date"] == "2026-11-13"

    def test_pichle_hafte(self, engine):
        """'pichle hafte' indicates 7 days before reference date."""
        res = engine.parse("Ramesh ne pichle hafte 1000 diye")
        assert res["date"] == "2026-11-06"

    def test_injectable_clock_changes_target_date(self):
        """Verifies changing reference date cleanly shifts computed ISO dates."""
        extractor = EntityExtractor(reference_date=date(2025, 1, 15))
        assert extractor.extract_date_iso("kal 200 diya tha") == "2025-01-14"
        assert extractor.extract_date_iso("parso 300 liya") == "2025-01-13"
        assert extractor.extract_date_iso("aaj ka khata") == "2025-01-15"
