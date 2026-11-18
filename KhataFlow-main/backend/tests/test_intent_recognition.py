"""
Tests for Intent Recognition across Hindi, Hinglish, and English.
Covers all required intents:
- ADD_CREDIT
- RECORD_PAYMENT
- CHECK_BALANCE
- DAILY_SUMMARY
- TRANSACTION_HISTORY
"""

import pytest
from backend.services.intent_engine import IntentEngine


@pytest.fixture
def engine():
    return IntentEngine()


class TestIntentRecognition:
    @pytest.mark.parametrize(
        "command,expected_intent,expected_customer,expected_amount",
        [
            # ADD_CREDIT (Hindi, Hinglish, English)
            ("Ramesh ka 500 udhaar", "ADD_CREDIT", "Ramesh", 500.0),
            ("सुरेश का 350 उधार", "ADD_CREDIT", "Suresh", 350.0),
            ("Pooja ka 1000 credit likho", "ADD_CREDIT", "Pooja", 1000.0),
            ("Mukesh ko 250 ka udhaar dena hai", "ADD_CREDIT", "Mukesh", 250.0),
            ("Rahul ka khata mein 400 likh lo", "ADD_CREDIT", "Rahul", 400.0),
            ("Anita ka 150 udhari", "ADD_CREDIT", "Anita", 150.0),

            # RECORD_PAYMENT (Hindi, Hinglish, English)
            ("Ramesh ne 200 diye", "RECORD_PAYMENT", "Ramesh", 200.0),
            ("सुरेश ने 500 जमा किये", "RECORD_PAYMENT", "Suresh", 500.0),
            ("Mohan ne 300 rupees pay kiya", "RECORD_PAYMENT", "Mohan", 300.0),
            ("Pooja se 150 payment mila", "RECORD_PAYMENT", "Pooja", 150.0),
            ("Vijay ne 600 wapas diye", "RECORD_PAYMENT", "Vijay", 600.0),
            ("Amit ne 800 bhara", "RECORD_PAYMENT", "Amit", 800.0),

            # CHECK_BALANCE
            ("Ramesh ka kitna baaki hai?", "CHECK_BALANCE", "Ramesh", None),
            ("रमेश का कितना बाकी है?", "CHECK_BALANCE", "Ramesh", None),
            ("Suresh ka balance batao", "CHECK_BALANCE", "Suresh", None),
            ("Pooja ka kitna dena baaki hai", "CHECK_BALANCE", "Pooja", None),
            ("Mohan ka hisaab batao", "CHECK_BALANCE", "Mohan", None),
            ("Mukesh ka total kitna baaki hai", "CHECK_BALANCE", "Mukesh", None),

            # DAILY_SUMMARY
            ("Aaj ka total udhaar batao", "DAILY_SUMMARY", None, None),
            ("आज का टोटल उधार बताओ", "DAILY_SUMMARY", None, None),
            ("Aaj ka hisaab batao", "DAILY_SUMMARY", None, None),
            ("Din ka total udhaar kitna hai", "DAILY_SUMMARY", None, None),
            ("Daily summary dikhao", "DAILY_SUMMARY", None, None),

            # TRANSACTION_HISTORY
            ("Ramesh ka transaction dikhao", "TRANSACTION_HISTORY", "Ramesh", None),
            ("सुरेश का लेनदेन दिखाओ", "TRANSACTION_HISTORY", "Suresh", None),
            ("Mohan ki transaction history dikhao", "TRANSACTION_HISTORY", "Mohan", None),
            ("Pooja ka purana hisaab dikhao", "TRANSACTION_HISTORY", "Pooja", None),
        ],
    )
    def test_intent_classification(self, engine, command, expected_intent, expected_customer, expected_amount):
        res = engine.parse(command)
        assert res["intent"] == expected_intent
        assert res["customer_name"] == expected_customer
        if expected_amount is not None:
            assert res["amount"] == expected_amount

    def test_dict_input_support(self, engine):
        """Input can be a dict as emitted by STT streaming pipeline."""
        stt_payload = {"text": "Ramesh ka 500 udhaar", "is_final": True}
        res = engine.parse(stt_payload)
        assert res["intent"] == "ADD_CREDIT"
        assert res["customer_name"] == "Ramesh"
        assert res["amount"] == 500.0
        assert res["date"] is None
