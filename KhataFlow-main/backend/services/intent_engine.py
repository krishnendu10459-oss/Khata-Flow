"""
KhataFlow Intent Engine — Member 4
====================================
Multilingual (Hindi / Hinglish / English) intent parser for KhataFlow,
the voice-first credit ledger for Indian Kirana store owners.

This module is 100% self-contained, offline, deterministic, and mock-friendly.
It requires NO external API keys or network access for core intent parsing.

Capabilities:
-------------
1. Core Intent Classification:
   - ADD_CREDIT          ("Ramesh ka 500 udhaar", "सुरेश का 500 उधार")
   - RECORD_PAYMENT      ("Ramesh ne 200 diye", "सुरेश ने 200 जमा किये")
   - CHECK_BALANCE       ("Ramesh ka kitna baaki hai?", "रमेश का कितना बाकी है?")
   - DAILY_SUMMARY       ("Aaj ka total udhaar batao", "आज का हिसाब बताओ")
   - TRANSACTION_HISTORY ("Ramesh ka transaction dikhao", "रमेश का लेन-देन दिखाओ")
   - CORRECTION          ("Nahi, 450 tha", "गलत, 450 था")
   - CLARIFICATION_NEEDED (multiple candidate customers provided by caller)
   - UNKNOWN             (unsupported, greeting, or incomplete speech)
   - MULTIPLE_ACTIONS    (compound sentences with multiple ledger operations)

2. Language Understanding & Entity Extraction:
   - Arabic digits (500, 1,500), Devanagari numerals (५००), English number words
     ("five hundred", "one fifty"), and Hindi spoken words ("paanch sau", "do hazaar", "dedh sau").
   - Customer name extraction with honorific handling ("ji", "bhai"), postposition patterns
     ("ka/ki/ke/ne/ko/se"), and Indic Devanagari transliteration.
   - Deterministic relative-date parsing with injectable reference date:
     "aaj" (today), "kal" (yesterday), "parso" (day before yesterday), or null when no date specified.
   - Spoken correction handling that updates prior amounts without creating duplicate transactions.
   - Customer disambiguation when candidate lists are provided.

3. Interface:
   - engine.parse(input_data, reference_date=..., prior_context=..., candidate_customers=...) -> dict
     Accepts string or {"text": "...", "is_final": True} and returns structured JSON dictionary.
   - engine.extract_intent(transcript, context=...) -> IntentResponse
     Preserves async interface consumed by backend/main.py.
   - engine.process_sync(transcript) -> IntentResponse
     Synchronous convenience wrapper for backend/main.py and test suites.

Author: Member 4 (Intent Engine + Intelligence + Testing)
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional, Union

from backend.database.models import ActionItem, IntentResponse

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════════════
# Constants & Reference Tables
# ════════════════════════════════════════════════════════════════════════

# Devanagari digits -> ASCII digits
DEVANAGARI_DIGITS: Dict[str, str] = {
    "०": "0", "१": "1", "२": "2", "३": "3", "४": "4",
    "५": "5", "६": "6", "७": "7", "८": "8", "९": "9",
}

# Indic Devanagari Names -> Canonical English Names
NAME_MAP_INDIC: Dict[str, str] = {
    "रमेश": "Ramesh",
    "सुरेश": "Suresh",
    "मोहन": "Mohan",
    "सोहन": "Sohan",
    "पूजा": "Pooja",
    "मुकेश": "Mukesh",
    "गुप्ता": "Gupta",
    "वर्मा": "Verma",
    "शर्मा": "Sharma",
    "पटेल": "Patel",
    "अनीता": "Anita",
    "विजय": "Vijay",
    "राहुल": "Rahul",
    "अमित": "Amit",
    "दिनेश": "Dinesh",
    "राजेश": "Rajesh",
    "सुनील": "Sunil",
    "अनिल": "Anil",
}

# Phonetic / ASR variants -> Canonical Name
ROMAN_NAME_ALIASES: Dict[str, str] = {
    "ramesh": "Ramesh", "ramash": "Ramesh", "rameshbhai": "Ramesh",
    "suresh": "Suresh", "sureshh": "Suresh", "sureshbhai": "Suresh",
    "mohan": "Mohan", "mohanbhai": "Mohan", "mohanlal": "Mohan",
    "sohan": "Sohan", "sohanlal": "Sohan",
    "pooja": "Pooja", "puja": "Pooja", "poojaa": "Pooja",
    "mukesh": "Mukesh", "mukeshbhai": "Mukesh", "mukes": "Mukesh",
    "anita": "Anita", "aneeta": "Anita",
    "vijay": "Vijay", "vijaybhai": "Vijay",
    "rahul": "Rahul",
    "amit": "Amit",
    "dinesh": "Dinesh",
    "rajesh": "Rajesh",
    "sunil": "Sunil",
    "anil": "Anil",
}

KNOWN_SURNAMES: Dict[str, str] = {
    "gupta": "Gupta",
    "verma": "Verma",
    "sharma": "Sharma",
    "patel": "Patel",
    "patil": "Patel",
    "singh": "Singh",
    "kumar": "Kumar",
    "yadav": "Yadav",
}

HONORIFICS = {"ji", "bhai", "sahab", "sahib", "didi", "behen", "madam", "sir", "bhiya", "bhaiya"}

# Unit numbers (1-19) in English and Romanized Hindi
NUMBER_UNITS: Dict[str, int] = {
    # English
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19,
    # Hindi Romanized
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4,
    "panch": 5, "paanch": 5, "chhe": 6, "chhah": 6, "che": 6,
    "saat": 7, "aath": 8, "nau": 9, "das": 10,
    "gyarah": 11, "barah": 12, "terah": 13, "chaudah": 14,
    "pandrah": 15, "solah": 16, "satrah": 17, "atharah": 18,
    "unnis": 19,
}

# Tens numbers (20-90)
NUMBER_TENS: Dict[str, int] = {
    # English
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    # Hindi Romanized
    "bees": 20, "ikkees": 21, "pachees": 25, "pachhees": 25,
    "tees": 30, "paintees": 35,
    "chaalees": 40, "chalees": 40, "chalis": 40,
    "pachaas": 50, "pachas": 50,
    "sattar": 70, "assi": 80, "nabbe": 90, "nabbhe": 90,
}

# Scale multipliers
NUMBER_SCALES: Dict[str, int] = {
    "hundred": 100, "sau": 100, "so": 100,
    "thousand": 1000, "hazaar": 1000, "hazar": 1000, "hajar": 1000, "k": 1000,
    "lakh": 100000, "lac": 100000,
}

# Fractional multipliers (common in Kirana speech)
FRACTIONAL_PREFIXES: Dict[str, float] = {
    "dedh": 1.5, "dhai": 2.5, "adhai": 2.5, "sawa": 1.25,
}

# Postpositions indicating preceding word is a person's name
NAME_POSTPOSITIONS = {"ka", "ki", "ke", "ne", "ko", "se", "का", "की", "के", "ने", "को", "से"}

# Words that cannot be customer names even if capitalized or preceding postpositions
STOP_WORDS = {
    "aaj", "kal", "parso", "tarso", "today", "yesterday", "total", "kitna", "baaki", "baki",
    "udhaar", "udhar", "jama", "credit", "payment", "diye", "diya", "rupaye", "rupees", "rs",
    "batao", "dikhao", "dekhna", "tha", "thi", "hai", "karo", "kar", "do", "de", "le", "liya",
    "gaya", "khata", "mein", "hisaab", "hisab", "sabka", "sab", "din", "daily", "summary",
    "transaction", "transactions", "history", "nahi", "nai", "na", "haan", "ha", "yes", "no",
    "galat", "sahi", "aur", "phir", "then", "and", "or", "mera", "meri", "uska", "uski",
    "unka", "unki", "is", "us", "pichle", "pichhle", "agle", "hafte", "mahine",
    "namaste", "hello", "hi", "hey", "kaise", "kya", "kyun", "shukriya", "dhanyawad",
    "आज", "कल", "परसों", "टोटल", "कितना", "बाकी", "उधार", "जमा", "क्रेडिट", "पेमेंट",
    "दिया", "दिए", "रुपये", "रुपए", "हिसाब", "लेनदेन", "नहीं", "गलत", "सही", "और",
    "नमस्ते", "धन्यवाद",
}

# Keyword triggers by intent
CORRECTION_TRIGGERS = [
    "nahi", "nai", "galat", "correction", "sahi karo", "sudhar", "change karo",
    "nhi", "nahi tha", "galat ho gaya", "गलत", "नहीं", "सुधार",
]

DAILY_SUMMARY_TRIGGERS = [
    "aaj ka total", "aaj ka hisaab", "aaj ka hisab", "din ka total", "din ka hisaab",
    "daily summary", "aaj kitna udhaar", "aaj kitna udhar", "aaj kitna jama",
    "aaj ka udhaar", "aaj ka udhar", "आज का टोटल", "आज का हिसाब", "आज का उधार",
]

TRANSACTION_HISTORY_TRIGGERS = [
    "transaction dikhao", "transaction history", "transactions dikhao",
    "history dikhao", "hisaab dikhao", "hisab dikhao", "sab dikhao",
    "purana hisaab", "transaction dekhna", "लेनदेन दिखाओ", "ट्रांजेक्शन दिखाओ",
]

CHECK_BALANCE_TRIGGERS = [
    "kitna baaki", "kitna baki", "kitna baaki hai", "kitna baki hai",
    "kitna udhaar", "kitna udhar", "balance batao", "balance kitna",
    "total kitna", "kitna dena", "kitna lena", "hisaab batao", "hisab batao",
    "kitne bache", "kitna bacha", "कितना बाकी", "कितना उधार", "बैलेंस",
]

RECORD_PAYMENT_TRIGGERS = [
    "diye", "diya", "dia", "jama", "jamaa", "paid", "bhara", "chukaya",
    "payment", "payment mila", "mila", "payment kiya", "wapas diye", "de diye", "de diya", "pay kiya",
    "दिया", "दिए", "जमा", "पेमेंट", "भरा", "चुकाया", "मिला",
]

ADD_CREDIT_TRIGGERS = [
    "udhaar", "udhar", "udaar", "udar", "udhaari", "udhari", "credit",
    "likh", "likho", "likh lo", "le gaya", "le liya", "dena hai",
    "khata mein", "khate mein", "उधार", "क्रेडिट", "लिख", "ले गया",
]

# Multi-action clause separators
CLAUSE_SPLIT_PATTERN = re.compile(
    r"""[,،|।]+            # Punctuation breaks
    | \b(?:aur|phir|and|then)\b   # Explicit coordinating conjunctions
    | \b(?:और|फिर)\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


# ════════════════════════════════════════════════════════════════════════
# Preprocessor
# ════════════════════════════════════════════════════════════════════════

class TextPreprocessor:
    """Cleans, normalizes, and prepares speech transcripts for entity extraction."""

    @staticmethod
    def normalize_devanagari_digits(text: str) -> str:
        """Converts Devanagari numerals (०-९) to ASCII digits (0-9)."""
        return "".join(DEVANAGARI_DIGITS.get(ch, ch) for ch in text)

    @staticmethod
    def clean_text(text: str) -> str:
        """Standardizes punctuation, whitespace, and numeral representations."""
        if not text:
            return ""
        text = TextPreprocessor.normalize_devanagari_digits(text)
        # Strip trailing speech punctuation (e.g., ?, !, ., ।)
        text = re.sub(r"[?!।.]+$", "", text.strip())
        # Collapse multiple spaces
        text = re.sub(r"\s+", " ", text).strip()
        return text


# ════════════════════════════════════════════════════════════════════════
# Entity Extractor
# ════════════════════════════════════════════════════════════════════════

class EntityExtractor:
    """Extracts customer name, monetary amount, and date from speech text."""

    def __init__(self, reference_date: Optional[date] = None):
        self.reference_date = reference_date or date.today()

    def set_reference_date(self, ref_date: date) -> None:
        self.reference_date = ref_date

    # ── Amount Extraction ─────────────────────────────────────────────

    def extract_amount(self, text: str) -> Optional[float]:
        """
        Extracts monetary amount from Arabic digits, mixed numbers, or spoken Hindi/English words.
        Returns float or None if no valid amount found.
        """
        cleaned = TextPreprocessor.normalize_devanagari_digits(text)

        # 1. Standard Arabic digits (e.g. 500, 1500, 1,200, 250.50)
        digit_matches = re.findall(r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b|\b\d+(?:\.\d+)?\b", cleaned)
        for m in digit_matches:
            val_str = m.replace(",", "")
            try:
                val = float(val_str)
                # Filter out obvious year numbers (2020-2030) if standalone
                if 2020 <= val <= 2030 and not any(w in cleaned.lower() for w in ("rupaye", "rs", "₹", "rupees")):
                    continue
                return val
            except ValueError:
                pass

        # 2. Spoken word combinations: "paanch sau", "do hazaar", "dedh sau", "one fifty"
        word_amount = self._parse_spoken_number_words(cleaned)
        if word_amount is not None:
            return float(word_amount)

        return None

    def _parse_spoken_number_words(self, text: str) -> Optional[float]:
        """Parses compound spoken words in Hindi/English into numerical values."""
        lower = text.lower()

        # Handle Indian English colloquialisms: "one fifty" -> 150, "two twenty" -> 220
        unit_words = "one|two|three|four|five|six|seven|eight|nine"
        tens_words = "twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety"
        colloquial_pattern = rf"\b({unit_words})\s+({tens_words})\b"
        m_col = re.search(colloquial_pattern, lower)
        if m_col:
            val = NUMBER_UNITS[m_col.group(1)] * 100 + NUMBER_TENS[m_col.group(2)]
            return float(val)

        tokens = re.findall(r"[\w\u0900-\u097F]+", lower)
        total = 0.0
        current = 0.0
        found_num = False

        i = 0
        while i < len(tokens):
            tok = tokens[i]

            if tok.isdigit():
                current += float(tok)
                found_num = True
            elif tok in FRACTIONAL_PREFIXES:
                current = FRACTIONAL_PREFIXES[tok]
                found_num = True
            elif tok in NUMBER_UNITS:
                current += NUMBER_UNITS[tok]
                found_num = True
            elif tok in NUMBER_TENS:
                current += NUMBER_TENS[tok]
                found_num = True
            elif tok == "saath" and i + 1 < len(tokens) and tokens[i + 1] in NUMBER_SCALES:
                # 'saath' as 60 only when followed by sau/hazaar
                current += 60
                found_num = True
            elif tok in NUMBER_SCALES:
                scale = NUMBER_SCALES[tok]
                if current == 0:
                    current = 1.0
                current *= scale
                if scale >= 1000:
                    total += current
                    current = 0.0
                found_num = True
            elif tok in ("rupaye", "rupees", "rs", "rupay", "rupaiye", "रुपये", "रुपए"):
                # Currency marker - continue accumulating
                pass
            else:
                if found_num and current > 0:
                    # Check next token before stopping
                    if i + 1 < len(tokens) and (
                        tokens[i + 1].isdigit()
                        or tokens[i + 1] in NUMBER_UNITS
                        or tokens[i + 1] in NUMBER_TENS
                        or tokens[i + 1] in NUMBER_SCALES
                    ):
                        i += 1
                        continue
                    total += current
                    current = 0.0
                    break

            i += 1

        total += current
        return float(total) if found_num and total > 0 else None

    # ── Customer Name Extraction ──────────────────────────────────────

    def extract_customer_name(self, text: str) -> Optional[str]:
        """
        Extracts customer name using Indic Devanagari lookup, Hindi postpositions,
        and known alias/surname matching.
        """
        # 1. Direct Devanagari name match
        for dev_name, eng_name in NAME_MAP_INDIC.items():
            if dev_name in text:
                surname = self._find_following_surname(text, dev_name)
                return f"{eng_name} {surname}" if surname else eng_name

        # 2. Extract preceding postpositions (e.g. "Ramesh ka", "Mohan ne", "Suresh ko")
        postpos_name = self._extract_name_via_postposition(text)
        if postpos_name:
            return postpos_name

        # 3. Match known Roman aliases
        lower = text.lower()
        first_name: Optional[str] = None
        first_pos = len(text)
        for alias, canonical in ROMAN_NAME_ALIASES.items():
            match = re.search(rf"\b{re.escape(alias)}\b", lower)
            if match and match.start() < first_pos:
                first_name = canonical
                first_pos = match.start()

        if first_name:
            surname = self._find_surname_after_pos(text, first_pos)
            return f"{first_name} {surname}" if surname else first_name

        # 4. Fallback: Capitalized Indian name heuristic
        capitalized = re.findall(r"\b([A-Z][a-z]{2,})\b", text)
        for cand in capitalized:
            if cand.lower() not in STOP_WORDS and cand.lower() not in HONORIFICS:
                return cand

        return None

    def _extract_name_via_postposition(self, text: str) -> Optional[str]:
        """Finds tokens immediately preceding a Hindi postposition ('ka', 'ki', 'ke', 'ne', 'ko', 'se')."""
        tokens = text.split()
        for i, tok in enumerate(tokens):
            clean_tok = tok.lower().strip(",.?!")
            if clean_tok in NAME_POSTPOSITIONS and i > 0:
                name_parts: List[str] = []
                j = i - 1
                while j >= 0:
                    word = tokens[j].strip(",.?!")
                    word_lower = word.lower()
                    if word_lower in HONORIFICS:
                        j -= 1
                        continue
                    if word_lower in STOP_WORDS:
                        break
                    if word_lower.isdigit() or word_lower in NUMBER_UNITS or word_lower in NUMBER_TENS:
                        break

                    # Canonicalize alias or keep capitalized
                    if word_lower in ROMAN_NAME_ALIASES:
                        name_parts.insert(0, ROMAN_NAME_ALIASES[word_lower])
                    elif word_lower in KNOWN_SURNAMES:
                        name_parts.insert(0, KNOWN_SURNAMES[word_lower])
                    elif word and word[0].isupper():
                        name_parts.insert(0, word.title())
                    elif len(name_parts) > 0:
                        # Part of multi-word name
                        name_parts.insert(0, word.title())
                    else:
                        break
                    j -= 1

                if name_parts:
                    return " ".join(name_parts)
        return None

    def _find_following_surname(self, text: str, anchor: str) -> Optional[str]:
        idx = text.find(anchor)
        if idx >= 0:
            rest = text[idx + len(anchor):].strip().split()
            if rest and rest[0].lower() in KNOWN_SURNAMES:
                return KNOWN_SURNAMES[rest[0].lower()]
        return None

    def _find_surname_after_pos(self, text: str, pos: int) -> Optional[str]:
        tokens = text[pos:].split()
        if len(tokens) >= 2:
            candidate = tokens[1].lower().strip(",.?!")
            if candidate in KNOWN_SURNAMES:
                return KNOWN_SURNAMES[candidate]
        return None

    # ── Date Extraction ───────────────────────────────────────────────

    def extract_date_iso(self, text: str) -> Optional[str]:
        """
        Extracts date and returns ISO 8601 string (e.g. '2026-11-12') using reference_date.
        Returns None when no date is explicitly mentioned.
        """
        lower = text.lower()

        # Relative keywords
        if any(w in lower for w in ("parso", "परसों", "day before yesterday")):
            return (self.reference_date - timedelta(days=2)).isoformat()
        if any(w in lower for w in ("tarso", "तरसों")):
            return (self.reference_date - timedelta(days=3)).isoformat()
        if any(w in lower for w in ("kal", "कल", "yesterday")):
            return (self.reference_date - timedelta(days=1)).isoformat()
        if any(w in lower for w in ("aaj", "आज", "today")):
            return self.reference_date.isoformat()

        # "pichle hafte" / "last week"
        if "pichle hafte" in lower or "last week" in lower:
            return (self.reference_date - timedelta(days=7)).isoformat()

        return None

    def extract_date_relative_label(self, text: str) -> Optional[str]:
        """Legacy label ('today', 'yesterday', 'day_before_yesterday') for ActionItem.date."""
        lower = text.lower()
        if any(w in lower for w in ("parso", "परसों", "day before yesterday")):
            return "day_before_yesterday"
        if any(w in lower for w in ("kal", "कल", "yesterday")):
            return "yesterday"
        if any(w in lower for w in ("aaj", "आज", "today")):
            return "today"
        return None


# ════════════════════════════════════════════════════════════════════════
# Intent Classifier
# ════════════════════════════════════════════════════════════════════════

class IntentClassifier:
    """Classifies user intent from normalized speech transcript."""

    @staticmethod
    def _matches_any(triggers: List[str], text: str) -> bool:
        """Helper to match keywords across English, Hinglish, and Indic Devanagari."""
        lower = text.lower()
        for w in triggers:
            # For Devanagari strings, regex \b boundary is unreliable
            if any('\u0900' <= ch <= '\u097f' for ch in w):
                if w in lower:
                    return True
            else:
                if re.search(rf"\b{re.escape(w)}\b", lower):
                    return True
        return False

    @classmethod
    def classify(cls, text: str) -> tuple[str, float]:
        """
        Classifies transcript into (intent_name, confidence).
        Supported intents:
        - CORRECTION
        - DAILY_SUMMARY
        - TRANSACTION_HISTORY
        - CHECK_BALANCE
        - RECORD_PAYMENT
        - ADD_CREDIT
        - UNKNOWN
        """
        lower = text.lower()

        # 1. Spoken correction: "Nahi, 450 tha", "Galat, 200 tha", "नहीं, 450 था"
        has_corr_word = cls._matches_any(CORRECTION_TRIGGERS, lower)
        has_digits = bool(re.search(r"\d+", text)) or any(w in lower for w in NUMBER_UNITS) or any(w in lower for w in NUMBER_TENS)
        has_past_tense = any(w in lower for w in ("tha", "thi", "the", "था", "थी"))
        if has_corr_word and (has_digits or has_past_tense):
            return "CORRECTION", 0.95

        # 2. Daily summary: "Aaj ka total udhaar batao"
        if cls._matches_any(DAILY_SUMMARY_TRIGGERS, lower):
            return "DAILY_SUMMARY", 0.95

        # 3. Transaction history: "Ramesh ka transaction dikhao"
        if cls._matches_any(TRANSACTION_HISTORY_TRIGGERS, lower):
            return "TRANSACTION_HISTORY", 0.93

        # 4. Check balance: "Ramesh ka kitna baaki hai?"
        if cls._matches_any(CHECK_BALANCE_TRIGGERS, lower):
            return "CHECK_BALANCE", 0.95

        # 5. Payment vs Credit distinction
        has_payment = cls._matches_any(RECORD_PAYMENT_TRIGGERS, lower)
        has_credit = cls._matches_any(ADD_CREDIT_TRIGGERS, lower)

        if has_payment and not has_credit:
            return "RECORD_PAYMENT", 0.93
        if has_credit and not has_payment:
            return "ADD_CREDIT", 0.93
        if has_payment and has_credit:
            return "MULTIPLE_ACTIONS", 0.90

        # If has amount and customer name but no specific keyword, kirana default is credit
        if has_digits and any(p in lower for p in NAME_POSTPOSITIONS):
            return "ADD_CREDIT", 0.70

        return "UNKNOWN", 0.0


# ════════════════════════════════════════════════════════════════════════
# Main Intent Engine
# ════════════════════════════════════════════════════════════════════════

class IntentEngine:
    """
    Main orchestrator for Indic Speech Intent & Entity extraction.
    Exposes both structured dictionary API (parse) and Pydantic IntentResponse API (extract_intent).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        reference_date: Optional[date] = None,
        customer_lookup: Optional[Callable] = None,
    ):
        self.reference_date = reference_date or date.today()
        self.preprocessor = TextPreprocessor()
        self.extractor = EntityExtractor(self.reference_date)
        self.classifier = IntentClassifier()
        self.customer_lookup = customer_lookup
        self.last_parsed_result: Optional[Dict[str, Any]] = None

    def set_reference_date(self, ref_date: date) -> None:
        """Sets reference date for deterministic relative date tests."""
        self.reference_date = ref_date
        self.extractor.set_reference_date(ref_date)

    # ════════════════════════════════════════════════════════════════════
    # Structured JSON API (Member 4 Primary Interface)
    # ════════════════════════════════════════════════════════════════════

    def parse(
        self,
        input_data: Union[str, Dict[str, Any]],
        reference_date: Optional[date] = None,
        prior_context: Optional[Dict[str, Any]] = None,
        candidate_customers: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Parses text or STT dict and returns a predictable, JSON-compatible structured dictionary.

        Example Input:
            {"text": "Ramesh ka 500 udhaar", "is_final": True}
            OR "Ramesh ka 500 udhaar"

        Example Output (Single Action):
            {
              "intent": "ADD_CREDIT",
              "customer_name": "Ramesh",
              "amount": 500.0,
              "date": null,
              "confidence": 0.93,
              "raw_text": "Ramesh ka 500 udhaar"
            }

        Example Output (Multiple Actions):
            {
              "intent": "MULTIPLE_ACTIONS",
              "actions": [
                {"intent": "ADD_CREDIT", "customer_name": "Ramesh", "amount": 500.0, "date": null},
                {"intent": "RECORD_PAYMENT", "customer_name": "Mohan", "amount": 200.0, "date": "2026-11-12"}
              ],
              "confidence": 0.93,
              "raw_text": "..."
            }
        """
        if reference_date:
            self.set_reference_date(reference_date)

        # 1. Unpack input text
        if isinstance(input_data, dict):
            raw_text = input_data.get("text", "")
        else:
            raw_text = str(input_data or "")

        cleaned = self.preprocessor.clean_text(raw_text)
        if not cleaned:
            return {
                "intent": "UNKNOWN",
                "customer_name": None,
                "amount": None,
                "date": None,
                "confidence": 0.0,
                "raw_text": raw_text,
                "message": "Empty or unsupported input.",
            }

        # 2. Check for multi-action compound sentences
        clauses = self._split_compound_sentence(cleaned)
        if len(clauses) > 1:
            multi_res = self._parse_multi_action(clauses, cleaned, prior_context)
            self.last_parsed_result = multi_res
            return multi_res

        # 3. Single-clause parsing
        result = self._parse_single_clause(cleaned, prior_context, candidate_customers)
        self.last_parsed_result = result
        return result

    def _parse_single_clause(
        self,
        text: str,
        prior_context: Optional[Dict[str, Any]] = None,
        candidate_customers: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Parses a single intent clause."""
        intent, confidence = self.classifier.classify(text)

        # Disambiguation Check: If caller supplied multiple matching customers
        if candidate_customers and len(candidate_customers) > 1:
            name = self.extractor.extract_customer_name(text) or "Grahak"
            cand_names = [c.get("name", "") for c in candidate_customers]
            return {
                "intent": "CLARIFICATION_NEEDED",
                "clarification_type": "CUSTOMER_DISAMBIGUATION",
                "query_name": name,
                "candidates": candidate_customers,
                "message": f"Kaun se {name} ki baat kar rahe hain? " + " ya ".join(cand_names) + "?",
                "confidence": 0.95,
                "raw_text": text,
            }

        # Correction Handling
        if intent == "CORRECTION":
            return self._build_correction_result(text, prior_context, confidence)

        # Entity Extraction
        customer_name = self.extractor.extract_customer_name(text)
        amount = self.extractor.extract_amount(text)
        date_iso = self.extractor.extract_date_iso(text)

        # Guard: Incomplete commands (e.g. amount given but no customer and no intent verb)
        if intent == "UNKNOWN":
            return {
                "intent": "UNKNOWN",
                "customer_name": customer_name,
                "amount": amount,
                "date": date_iso,
                "confidence": 0.0,
                "raw_text": text,
                "message": "Could not understand command.",
            }

        return {
            "intent": intent,
            "customer_name": customer_name,
            "amount": amount,
            "date": date_iso,
            "confidence": confidence,
            "raw_text": text,
        }

    def _parse_multi_action(
        self,
        clauses: List[str],
        full_text: str,
        prior_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Parses compound sentences into structured list of individual actions."""
        actions: List[Dict[str, Any]] = []
        overall_confidence = 1.0
        shared_customer: Optional[str] = None

        for clause in clauses:
            res = self._parse_single_clause(clause, prior_context=prior_context)
            if res.get("intent") == "UNKNOWN" and res.get("amount") is None:
                continue

            # Inherit customer from preceding clause if missing (e.g. "Ramesh ka 500 udhaar aur 200 payment")
            if res.get("customer_name"):
                shared_customer = res["customer_name"]
            elif shared_customer and res.get("intent") in ("ADD_CREDIT", "RECORD_PAYMENT", "CHECK_BALANCE"):
                res["customer_name"] = shared_customer

            overall_confidence = min(overall_confidence, res.get("confidence", 0.9))
            actions.append({
                "intent": res.get("intent"),
                "customer_name": res.get("customer_name"),
                "amount": res.get("amount"),
                "date": res.get("date"),
            })

        if not actions:
            return {
                "intent": "UNKNOWN",
                "customer_name": None,
                "amount": None,
                "date": None,
                "confidence": 0.0,
                "raw_text": full_text,
            }

        return {
            "intent": "MULTIPLE_ACTIONS",
            "actions": actions,
            "confidence": overall_confidence,
            "raw_text": full_text,
        }

    def _build_correction_result(
        self,
        text: str,
        prior_context: Optional[Dict[str, Any]],
        confidence: float,
    ) -> Dict[str, Any]:
        """
        Builds a structured correction result.
        Does NOT invent transaction history — uses caller-provided prior_context or last_parsed_result.
        """
        # Find new amount in correction phrase: "Nahi, 450 tha" -> 450
        amount = self.extractor.extract_amount(text)
        if amount is None:
            # Check numbers directly
            nums = [float(n) for n in re.findall(r"\b\d+(?:\.\d+)?\b", text)]
            amount = nums[-1] if nums else None

        # Determine prior context (either explicitly passed or from session history)
        context = prior_context or self.last_parsed_result

        original_amount = context.get("amount") if context else None
        customer_name = context.get("customer_name") if context else None
        prior_intent = context.get("intent") if context else None

        # Check if the user also corrected the name: "Nahi, Mohan nahi Sohan"
        lower = text.lower()
        extracted_name = None
        for marker in ("nahi", "nai", "galat", "नहीं", "गलत"):
            idx = lower.find(marker)
            if idx >= 0:
                after_text = text[idx + len(marker):]
                cand = self.extractor.extract_customer_name(after_text)
                if cand:
                    extracted_name = cand
                    break

        if not extracted_name:
            extracted_name = self.extractor.extract_customer_name(text)

        if extracted_name:
            customer_name = extracted_name

        return {
            "intent": "CORRECTION",
            "correction_type": "AMOUNT" if amount is not None else "GENERAL",
            "new_amount": amount,
            "original_amount": original_amount,
            "customer_name": customer_name,
            "prior_intent": prior_intent,
            "date": None,
            "confidence": confidence,
            "message": f"Previous entry corrected to {amount}" if amount is not None else "Spoken correction noted",
            "raw_text": text,
        }

    def _split_compound_sentence(self, text: str) -> List[str]:
        """
        Splits sentence on conjunctions ('aur', 'and') or commas, ONLY when
        different actions or separate subjects are present.
        Prevents splitting corrections like 'Nahi, 450 tha'.
        """
        lower = text.lower()
        # Do NOT split correction phrases
        if any(w in lower for w in ("nahi,", "nahi ", "galat,", "galat ")):
            return [text]

        # Check if explicit coordinating conjunctions exist
        has_conjunction = any(re.search(rf"\b{w}\b", lower) for w in ("aur", "and", "or", "phir", "और", "फिर"))
        if not has_conjunction and "," not in text:
            return [text]

        parts = CLAUSE_SPLIT_PATTERN.split(text)
        cleaned_parts = [p.strip() for p in parts if p and len(p.strip()) > 3]

        # Only treat as multi-action if at least one part contains an action or amount
        valid_actions = 0
        for p in cleaned_parts:
            p_intent, _ = self.classifier.classify(p)
            if p_intent != "UNKNOWN" or self.extractor.extract_amount(p) is not None:
                valid_actions += 1

        return cleaned_parts if valid_actions > 1 else [text]

    # ════════════════════════════════════════════════════════════════════
    # Pydantic & Async Interface (backend/main.py Compatibility)
    # ════════════════════════════════════════════════════════════════════

    async def extract_intent(
        self,
        transcript: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> IntentResponse:
        """
        Async entry point matching backend/main.py call signature:
        `intent_resp = await intent_engine.extract_intent(transcript)`
        """
        return self.process_sync(transcript, context)

    def process_sync(
        self,
        transcript: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> IntentResponse:
        """
        Synchronous processing generating standard ActionItem / IntentResponse.
        Maps CHECK_BALANCE to QUERY_BALANCE for backend/main.py compatibility.
        """
        parsed = self.parse(transcript, prior_context=context)

        # Multi-action handling
        if parsed.get("intent") == "MULTIPLE_ACTIONS":
            items = []
            for act in parsed.get("actions", []):
                act_name = act.get("intent", "UNKNOWN")
                # Map CHECK_BALANCE to QUERY_BALANCE for main.py execution
                backend_act = "QUERY_BALANCE" if act_name == "CHECK_BALANCE" else act_name
                items.append(ActionItem(
                    action=backend_act,
                    customer=act.get("customer_name"),
                    amount=act.get("amount"),
                    date=act.get("date") or "today",
                    notes="",
                    target="total",
                ))
            return IntentResponse(
                actions=items,
                confidence=parsed.get("confidence", 0.9),
                spoken_summary="Multiple transactions recorded.",
            )

        intent_name = parsed.get("intent", "UNKNOWN")
        backend_intent = "QUERY_BALANCE" if intent_name == "CHECK_BALANCE" else intent_name

        amount_val = parsed.get("amount")
        if intent_name == "CORRECTION":
            amount_val = parsed.get("new_amount")

        action_item = ActionItem(
            action=backend_intent,
            customer=parsed.get("customer_name"),
            amount=amount_val,
            date=parsed.get("date") or "today",
            notes=parsed.get("message", ""),
            target="today" if "aaj" in str(transcript).lower() else "total",
        )

        spoken_summary = self._generate_spoken_summary(parsed)

        return IntentResponse(
            actions=[action_item],
            confidence=parsed.get("confidence", 0.9),
            spoken_summary=spoken_summary,
        )

    def check_disambiguation(
        self,
        customer_name: str,
        candidates: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Return a clarification payload when multiple customers match."""
        if not candidates or len(candidates) <= 1:
            return None
        cand_names = [c.get("name", "") for c in candidates]
        return {
            "type": "customer_disambiguation",
            "message": f"Kaun se {customer_name} ki baat kar rahe hain? " + " ya ".join(cand_names) + "?",
            "candidates": candidates,
        }

    def _generate_spoken_summary(self, parsed: Dict[str, Any]) -> Optional[str]:
        """Generates natural Hinglish spoken confirmation for TTS."""
        intent = parsed.get("intent")
        cust = parsed.get("customer_name")
        amt = parsed.get("amount")

        if intent == "ADD_CREDIT" and cust and amt:
            return f"{cust} ka {int(amt)} rupaye udhaar darj ho gaya."
        if intent == "RECORD_PAYMENT" and cust and amt:
            return f"{cust} se {int(amt)} rupaye jama ho gaye."
        if intent in ("CHECK_BALANCE", "QUERY_BALANCE") and cust:
            return f"{cust} ka balance dekh rahe hain."
        if intent == "DAILY_SUMMARY":
            return "Aaj ka total hisaab dekh rahe hain."
        if intent == "CORRECTION" and parsed.get("new_amount"):
            return f"Amount sudhar kar {int(parsed['new_amount'])} rupaye kar diya gaya hai."
        return None
