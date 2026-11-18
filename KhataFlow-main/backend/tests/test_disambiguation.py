"""
Tests for Duplicate Customer Disambiguation:
When caller supplies multiple matching customer candidates (e.g. 'Ramesh Sharma' & 'Ramesh Verma'),
the engine must return a structured CLARIFICATION_NEEDED response containing the candidates
without guessing or arbitrarily picking one.
"""

import pytest
from backend.services.intent_engine import IntentEngine


@pytest.fixture
def engine():
    return IntentEngine()


class TestCustomerDisambiguation:
    def test_duplicate_customers_triggers_clarification(self, engine):
        """
        When two customers match 'Ramesh', return structured clarification
        containing candidate details and a natural clarification question.
        """
        candidates = [
            {"id": 101, "name": "Ramesh Sharma", "phone": "9876543210"},
            {"id": 102, "name": "Ramesh Verma", "phone": "9876543211"},
        ]

        res = engine.parse("Ramesh ka 500 udhaar", candidate_customers=candidates)

        assert res["intent"] == "CLARIFICATION_NEEDED"
        assert res["clarification_type"] == "CUSTOMER_DISAMBIGUATION"
        assert res["query_name"] == "Ramesh"
        assert len(res["candidates"]) == 2
        assert res["candidates"][0]["name"] == "Ramesh Sharma"
        assert res["candidates"][1]["name"] == "Ramesh Verma"
        # Engine must not arbitrarily pick one
        assert "customer_name" not in res or res.get("customer_name") is None

    def test_single_customer_candidate_does_not_trigger_clarification(self, engine):
        """When exactly one customer matches, no clarification is needed."""
        candidates = [
            {"id": 101, "name": "Ramesh Sharma", "phone": "9876543210"}
        ]

        res = engine.parse("Ramesh ka 500 udhaar", candidate_customers=candidates)

        assert res["intent"] == "ADD_CREDIT"
        assert res["customer_name"] == "Ramesh"
        assert res["amount"] == 500.0

    def test_no_candidates_proceeds_normally(self, engine):
        """When customer lookup returns empty list (new customer), proceed with parsed name."""
        res = engine.parse("Ramesh ka 500 udhaar", candidate_customers=[])

        assert res["intent"] == "ADD_CREDIT"
        assert res["customer_name"] == "Ramesh"
        assert res["amount"] == 500.0

    def test_check_disambiguation_method(self, engine):
        """Direct verification of check_disambiguation helper method."""
        candidates = [
            {"id": 1, "name": "Ramesh Sharma"},
            {"id": 2, "name": "Ramesh Verma"},
        ]
        clarification = engine.check_disambiguation("Ramesh", candidates)
        assert clarification is not None
        assert clarification["type"] == "customer_disambiguation"
        assert len(clarification["candidates"]) == 2
