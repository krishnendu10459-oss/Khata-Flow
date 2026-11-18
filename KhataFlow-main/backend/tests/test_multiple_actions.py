"""
Tests for Multiple Actions in One Sentence:
Ensures compound sentences like "Ramesh ka 500 udhaar aur Mohan ko 200 diye"
are cleanly split into individual actions with consistent documented structure.
"""

from datetime import date
import pytest
from backend.services.intent_engine import IntentEngine


@pytest.fixture
def engine():
    return IntentEngine(reference_date=date(2026, 11, 13))


class TestMultipleActions:
    def test_two_different_customers_different_actions(self, engine):
        """Sentence with two customers and two actions (credit + payment)."""
        cmd = "Ramesh ka 500 udhaar aur Mohan ko 200 diye"
        res = engine.parse(cmd)

        assert res["intent"] == "MULTIPLE_ACTIONS"
        assert len(res["actions"]) == 2

        act1, act2 = res["actions"][0], res["actions"][1]
        assert act1["intent"] == "ADD_CREDIT"
        assert act1["customer_name"] == "Ramesh"
        assert act1["amount"] == 500.0

        assert act2["intent"] == "RECORD_PAYMENT"
        assert act2["customer_name"] == "Mohan"
        assert act2["amount"] == 200.0

    def test_same_customer_shared_subject(self, engine):
        """
        When customer is mentioned once at the beginning:
        'Ramesh ka 500 udhaar likho aur 200 jama karo'
        """
        cmd = "Ramesh ka 500 udhaar likho aur 200 jama karo"
        res = engine.parse(cmd)

        assert res["intent"] == "MULTIPLE_ACTIONS"
        assert len(res["actions"]) == 2

        act1, act2 = res["actions"][0], res["actions"][1]
        assert act1["intent"] == "ADD_CREDIT"
        assert act1["customer_name"] == "Ramesh"
        assert act1["amount"] == 500.0

        assert act2["intent"] == "RECORD_PAYMENT"
        assert act2["customer_name"] == "Ramesh"
        assert act2["amount"] == 200.0

    def test_devanagari_multiple_actions(self, engine):
        """Hindi compound command: 'सुरेश का 300 उधार और पूजा ने 150 दिए'."""
        cmd = "सुरेश का 300 उधार और पूजा ने 150 दिए"
        res = engine.parse(cmd)

        assert res["intent"] == "MULTIPLE_ACTIONS"
        assert len(res["actions"]) == 2
        assert res["actions"][0]["intent"] == "ADD_CREDIT"
        assert res["actions"][0]["customer_name"] == "Suresh"
        assert res["actions"][0]["amount"] == 300.0
        assert res["actions"][1]["intent"] == "RECORD_PAYMENT"
        assert res["actions"][1]["customer_name"] == "Pooja"
        assert res["actions"][1]["amount"] == 150.0

    def test_multiple_actions_pydantic_output(self, engine):
        """Pydantic extract_intent / process_sync produces a list of ActionItem."""
        cmd = "Ramesh ka 500 udhaar aur Mohan ko 200 diye"
        resp = engine.process_sync(cmd)

        assert len(resp.actions) == 2
        assert resp.actions[0].action == "ADD_CREDIT"
        assert resp.actions[0].customer == "Ramesh"
        assert resp.actions[0].amount == 500.0

        assert resp.actions[1].action == "RECORD_PAYMENT"
        assert resp.actions[1].customer == "Mohan"
        assert resp.actions[1].amount == 200.0
