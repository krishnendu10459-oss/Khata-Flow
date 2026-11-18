"""
Tests for Invalid, Incomplete, or Ambiguous Commands:
Ensures unpredictable speech returns predictable results with intent=UNKNOWN
and does NOT guess missing information.
"""

import pytest
from backend.services.intent_engine import IntentEngine


@pytest.fixture
def engine():
    return IntentEngine()


class TestInvalidAndIncompleteInputs:
    def test_empty_input(self, engine):
        """Empty string or whitespace returns UNKNOWN."""
        res = engine.parse("")
        assert res["intent"] == "UNKNOWN"
        assert res["confidence"] == 0.0

        res_spaces = engine.parse("     ")
        assert res_spaces["intent"] == "UNKNOWN"

    def test_greeting_or_irrelevant_speech(self, engine):
        """Casual conversation must not trigger ledger transactions."""
        res1 = engine.parse("Namaste bhai sahab kaise ho")
        assert res1["intent"] == "UNKNOWN"
        assert res1["customer_name"] is None
        assert res1["amount"] is None

        res2 = engine.parse("Hello good morning dukaan kab khuli")
        assert res2["intent"] == "UNKNOWN"

    def test_unsupported_or_random_words(self, engine):
        """Random unparseable phrases."""
        res = engine.parse("Chai peete hain biscuit lao")
        assert res["intent"] == "UNKNOWN"
        assert res["amount"] is None

    def test_incomplete_command_does_not_guess_missing_info(self, engine):
        """
        When shopkeeper says just '500 rupaye' without customer or action,
        the system must return UNKNOWN and NOT guess who or what to do.
        """
        res = engine.parse("500 rupaye")
        assert res["intent"] == "UNKNOWN"
        assert res["customer_name"] is None
        assert res["amount"] == 500.0

    def test_dict_with_empty_text(self, engine):
        """Dict payload with empty text field."""
        res = engine.parse({"text": "", "is_final": True})
        assert res["intent"] == "UNKNOWN"
