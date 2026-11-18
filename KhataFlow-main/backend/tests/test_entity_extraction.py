"""
Tests for Entity Extraction:
- Customer name extraction (Indic Devanagari, aliases, honorifics, surnames, postpositions)
- Monetary amounts (Arabic digits, Devanagari digits, spoken Hindi words, Indian English forms)
"""

import pytest
from backend.services.intent_engine import EntityExtractor, TextPreprocessor, IntentEngine


@pytest.fixture
def extractor():
    return EntityExtractor()


@pytest.fixture
def engine():
    return IntentEngine()


class TestAmountExtraction:
    @pytest.mark.parametrize(
        "text,expected_amount",
        [
            # Arabic digits
            ("Ramesh ka 500 udhaar", 500.0),
            ("Suresh ne 1500 diye", 1500.0),
            ("Pooja ka 1,200 likho", 1200.0),
            ("Mohan ne 250.50 diya", 250.50),

            # Devanagari digits
            ("सुरेश का ५०० उधार", 500.0),
            ("रमेश ने २५० जमा किये", 250.0),
            ("पूजा का १००० का सामान", 1000.0),
            ("मोहन ने १५० दिए", 150.0),

            # Hindi spoken number words
            ("Ramesh ka paanch sau udhaar", 500.0),
            ("Suresh ne do hazaar jama kiye", 2000.0),
            ("Pooja ka ek hazaar paanch sau udhaar", 1500.0),
            ("Mohan ne teen sau pachaas diye", 350.0),
            ("Mukesh ka chaar sau bees udhaar", 420.0),
            ("Vijay ne saat sau rupaye diye", 700.0),
            ("Anita ka aath sau udhaar", 800.0),
            ("Rahul ne nau sau jama kiye", 900.0),
            ("Dinesh ka ek lakh udhaar", 100000.0),

            # Fractional multipliers common in Kirana stores
            ("Ramesh ka dedh sau udhaar", 150.0),
            ("Suresh ne dhai hazaar diye", 2500.0),
            ("Pooja ka sawa sau udhaar", 125.0),

            # Colloquial Indian English spoken numbers
            ("Ramesh paid one fifty", 150.0),
            ("Suresh gave two twenty", 220.0),
            ("five hundred rupees credit", 500.0),
            ("two thousand payment", 2000.0),
        ],
    )
    def test_amount_extraction_cases(self, extractor, text, expected_amount):
        amt = extractor.extract_amount(text)
        assert amt == expected_amount, f"Failed extracting from: {text}"


class TestCustomerNameExtraction:
    @pytest.mark.parametrize(
        "text,expected_name",
        [
            # Devanagari names
            ("सुरेश का 500 उधार", "Suresh"),
            ("रमेश ने 200 दिए", "Ramesh"),
            ("पूजा का कितना बाकी है", "Pooja"),
            ("मोहन को 300 दिए", "Mohan"),

            # Names with honorifics
            ("Ramesh ji ka 500 udhaar", "Ramesh"),
            ("Suresh bhai ne 200 diye", "Suresh"),
            ("Mohan sahab ka balance batao", "Mohan"),
            ("Pooja didi ka 300 udhaar", "Pooja"),

            # Names with surnames
            ("Ramesh Sharma ka 500 udhaar", "Ramesh Sharma"),
            ("Pooja Patel ne 200 diye", "Pooja Patel"),
            ("Mukesh Gupta ka hisaab", "Mukesh Gupta"),
            ("Suresh Verma ka kitna baaki", "Suresh Verma"),

            # Postposition patterns ("ka", "ne", "ko", "se")
            ("Dinesh ne 400 jama kiye", "Dinesh"),
            ("Rajesh ko 300 udhaar diya", "Rajesh"),
            ("Sunil se 500 payment mila", "Sunil"),
            ("Anil ka 700 udhaar", "Anil"),
        ],
    )
    def test_customer_name_cases(self, extractor, text, expected_name):
        name = extractor.extract_customer_name(text)
        assert name == expected_name, f"Failed extracting name from: {text}"


class TestTextPreprocessor:
    def test_devanagari_digit_conversion(self):
        text = "सुरेश का ५०० उधार और २०१०"
        converted = TextPreprocessor.normalize_devanagari_digits(text)
        assert converted == "सुरेश का 500 उधार और 2010"

    def test_whitespace_and_punctuation_clean(self):
        text = "  Ramesh   ka  500   udhaar???  "
        cleaned = TextPreprocessor.clean_text(text)
        assert cleaned == "Ramesh ka 500 udhaar"
