"""
Tests for Correction Handling:
Ensures correction phrases such as "Nahi, 450 tha" modify a prior entry
and do NOT create duplicate or new transactions.
Verifies prior-entry context requirements and prevents inventing history.
"""

import pytest
from backend.services.intent_engine import IntentEngine


@pytest.fixture
def engine():
    return IntentEngine()


class TestCorrectionHandling:
    def test_correction_with_prior_context(self, engine):
        """
        Scenario:
        1. Shopkeeper: 'Ramesh ka 500 udhaar'
        2. Shopkeeper: 'Nahi, 450 tha'
        Engine must recognize step 2 as a correction modifying step 1, not as a new transaction.
        """
        # Step 1
        first_entry = engine.parse("Ramesh ka 500 udhaar")
        assert first_entry["intent"] == "ADD_CREDIT"
        assert first_entry["customer_name"] == "Ramesh"
        assert first_entry["amount"] == 500.0

        # Step 2: Caller passes prior context (or relies on engine state)
        correction = engine.parse("Nahi, 450 tha", prior_context=first_entry)
        assert correction["intent"] == "CORRECTION"
        assert correction["correction_type"] == "AMOUNT"
        assert correction["new_amount"] == 450.0
        assert correction["original_amount"] == 500.0
        assert correction["customer_name"] == "Ramesh"
        assert correction["prior_intent"] == "ADD_CREDIT"

    def test_correction_without_prior_context_does_not_invent_history(self, engine):
        """
        When no prior context is available, engine returns a structured correction
        with new_amount but original_amount=null and customer_name=null.
        It must NEVER invent imaginary customers or transactions.
        """
        correction = engine.parse("Nahi, 450 tha", prior_context=None)
        assert correction["intent"] == "CORRECTION"
        assert correction["new_amount"] == 450.0
        assert correction["original_amount"] is None
        assert correction["customer_name"] is None

    def test_correction_devanagari(self, engine):
        """Hindi Devanagari correction: 'नहीं, 450 था'."""
        prior = {"intent": "ADD_CREDIT", "customer_name": "Suresh", "amount": 500.0}
        correction = engine.parse("नहीं, 450 था", prior_context=prior)
        assert correction["intent"] == "CORRECTION"
        assert correction["new_amount"] == 450.0
        assert correction["original_amount"] == 500.0
        assert correction["customer_name"] == "Suresh"

    def test_correction_phrase_variants(self, engine):
        """Tests variants like 'galat ho gaya, 350 tha' and 'correction 600'."""
        prior = {"intent": "RECORD_PAYMENT", "customer_name": "Mohan", "amount": 400.0}

        c1 = engine.parse("Galat ho gaya, 350 tha", prior_context=prior)
        assert c1["intent"] == "CORRECTION"
        assert c1["new_amount"] == 350.0

        c2 = engine.parse("Correction 600 tha", prior_context=prior)
        assert c2["intent"] == "CORRECTION"
        assert c2["new_amount"] == 600.0

        c3 = engine.parse("Sahi karo 250 tha", prior_context=prior)
        assert c3["intent"] == "CORRECTION"
        assert c3["new_amount"] == 250.0

    def test_name_correction(self, engine):
        """
        Scenario: Shopkeeper corrects the customer name:
        'Galat ho gaya, Mohan nahi Sohan tha'
        """
        prior = {"intent": "ADD_CREDIT", "customer_name": "Mohan", "amount": 300.0}
        c = engine.parse("Galat ho gaya, Mohan nahi Sohan tha", prior_context=prior)
        assert c["intent"] == "CORRECTION"
        assert c["customer_name"] == "Sohan"
