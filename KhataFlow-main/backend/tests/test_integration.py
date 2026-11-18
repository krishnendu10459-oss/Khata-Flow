"""
Integration tests for KhataFlow Member 4 Deliverables:
Validates the exact test commands from the specification:
1. "Ramesh ka 500 udhaar."
2. "Ramesh ne 200 diye."
3. "Ramesh ka kitna baaki hai?"
4. "Nahi, 450 tha."
5. "Mohan ko kal 300 diye."
6. "Aaj ka total udhaar batao."
7. "Ramesh ka transaction dikhao."
"""

from datetime import date
import pytest
from backend.services.intent_engine import IntentEngine


@pytest.fixture
def engine():
    # Inject fixed reference date: 2026-11-13 (Friday)
    return IntentEngine(reference_date=date(2026, 11, 13))


class TestMember4SpecificationCommands:
    def test_command_1_add_credit(self, engine):
        """1. 'Ramesh ka 500 udhaar.' -> ADD_CREDIT"""
        res = engine.parse("Ramesh ka 500 udhaar.")
        assert res["intent"] == "ADD_CREDIT"
        assert res["customer_name"] == "Ramesh"
        assert res["amount"] == 500.0
        assert res["date"] is None

    def test_command_2_record_payment(self, engine):
        """2. 'Ramesh ne 200 diye.' -> RECORD_PAYMENT"""
        res = engine.parse("Ramesh ne 200 diye.")
        assert res["intent"] == "RECORD_PAYMENT"
        assert res["customer_name"] == "Ramesh"
        assert res["amount"] == 200.0
        assert res["date"] is None

    def test_command_3_check_balance(self, engine):
        """3. 'Ramesh ka kitna baaki hai?' -> CHECK_BALANCE"""
        res = engine.parse("Ramesh ka kitna baaki hai?")
        assert res["intent"] == "CHECK_BALANCE"
        assert res["customer_name"] == "Ramesh"
        assert res["amount"] is None
        assert res["date"] is None

    def test_command_4_spoken_correction(self, engine):
        """
        4. Sequence:
           First entry: 'Ramesh ka 500 udhaar.'
           Correction:  'Nahi, 450 tha.'
        Must be recognized as a CORRECTION to previous entry, not a new transaction.
        """
        entry = engine.parse("Ramesh ka 500 udhaar.")
        correction = engine.parse("Nahi, 450 tha.", prior_context=entry)

        assert correction["intent"] == "CORRECTION"
        assert correction["correction_type"] == "AMOUNT"
        assert correction["new_amount"] == 450.0
        assert correction["original_amount"] == 500.0
        assert correction["customer_name"] == "Ramesh"
        assert correction["prior_intent"] == "ADD_CREDIT"

    def test_command_5_relative_date_payment(self, engine):
        """5. 'Mohan ko kal 300 diye.' -> RECORD_PAYMENT with relative date (yesterday = 2026-11-12)"""
        res = engine.parse("Mohan ko kal 300 diye.")
        assert res["intent"] == "RECORD_PAYMENT"
        assert res["customer_name"] == "Mohan"
        assert res["amount"] == 300.0
        assert res["date"] == "2026-11-12"

    def test_command_6_daily_summary(self, engine):
        """6. 'Aaj ka total udhaar batao' -> DAILY_SUMMARY"""
        res = engine.parse("Aaj ka total udhaar batao")
        assert res["intent"] == "DAILY_SUMMARY"
        assert res["date"] == "2026-11-13"

    def test_command_7_transaction_history(self, engine):
        """7. 'Ramesh ka transaction dikhao' -> TRANSACTION_HISTORY"""
        res = engine.parse("Ramesh ka transaction dikhao")
        assert res["intent"] == "TRANSACTION_HISTORY"
        assert res["customer_name"] == "Ramesh"
