# KhataFlow (खाताफ्लो) 🧾🎙️
### Production-Ready Low-Latency Indic Voice Ledger for Indian Kirana Stores

KhataFlow is a real-time, low-latency Voice Khata application tailored for Indian Kirana shopkeepers. It processes code-mixed Indic speech (Hindi, Hinglish, English) over WebSockets, extracts financial credit/payment intents offline or through AI pipelines, maintains an atomic ledger, and streams synthesized speech back with ultra-low latency.

---

## 👥 Module Ownership & Division of Responsibilities

To ensure independent development and zero merge conflicts, the codebase is partitioned across 4 team members:

| File / Folder | Owner | Scope & Responsibility |
|---|---|---|
| `frontend/` | Member 1 | Next.js AudioWorklet, UI Dashboard, Live Oscilloscope visualizer |
| `backend/database/` | Member 2 | SQLite schema, balance tracking, transaction ledger operations |
| `backend/services/gnani_stt.py` | Member 3 | Gnani Prisma v3.0 STT, streaming WebSockets, audio pipeline |
| `backend/services/gnani_tts.py` | Member 3 | Gnani Timbre v3.0 TTS, Hinglish voice playback, audio streaming |
| `backend/services/intent_engine.py` | **Member 4** | **NLU, Multilingual Intent Parser, Entity Extractor, Disambiguation** |
| `backend/tests/` | **Member 4** / Team | **Automated unit, entity extraction, correction, and integration tests** |
| `backend/main.py` | Joint (Integration) | FastAPI orchestration (integrated collaboratively after module testing) |
| `README.md` | **Member 4** | Technical setup, testing documentation, architecture specifications |
| Deployment (`Dockerfile`, `docker-compose.yml`) | **Member 4** | Containerization, deployment environments, reproducible runtime |

> **Note**: During development, each member develops independently using mock data and modular contracts. `backend/main.py` is reserved for final integration.

---

## 🧠 Intent Engine Documentation (Member 4)

The Intent Engine (`backend/services/intent_engine.py`) takes recognized text from the STT pipeline and converts it into a predictable, JSON-compatible structured result. It operates **100% offline**, requiring zero external network calls or paid API keys for core parsing.

### Common Interface Contract

#### 1. Input Specification
The parser accepts either a raw transcript string or an STT event dictionary:

```json
{
  "text": "Ramesh ka 500 udhaar",
  "is_final": true
}
```

#### 2. Output Specification (Single Action)
```json
{
  "intent": "ADD_CREDIT",
  "customer_name": "Ramesh",
  "amount": 500.0,
  "date": null,
  "confidence": 0.93,
  "raw_text": "Ramesh ka 500 udhaar"
}
```

#### 3. Output Specification (Multiple Actions in One Sentence)
```json
{
  "intent": "MULTIPLE_ACTIONS",
  "actions": [
    {
      "intent": "ADD_CREDIT",
      "customer_name": "Ramesh",
      "amount": 500.0,
      "date": null
    },
    {
      "intent": "RECORD_PAYMENT",
      "customer_name": "Mohan",
      "amount": 200.0,
      "date": "2026-11-12"
    }
  ],
  "confidence": 0.93,
  "raw_text": "Ramesh ka 500 udhaar aur Mohan ko kal 200 diye"
}
```

---

### Supported Intents

| Intent | Sample Commands (Hindi / Hinglish / English) | Output Intent |
|---|---|---|
| `ADD_CREDIT` | *"Ramesh ka 500 udhaar"*, *"सुरेश का 350 उधार"*, *"Pooja credit 1000"* | `ADD_CREDIT` |
| `RECORD_PAYMENT` | *"Ramesh ne 200 diye"*, *"सुरेश ने 500 जमा किये"*, *"Mohan paid 300"* | `RECORD_PAYMENT` |
| `CHECK_BALANCE` | *"Ramesh ka kitna baaki hai?"*, *"सुरेश का बैलेंस बताओ"*, *"Mohan balance?"* | `CHECK_BALANCE` |
| `DAILY_SUMMARY` | *"Aaj ka total udhaar batao"*, *"आज का हिसाब बताओ"*, *"Daily summary"* | `DAILY_SUMMARY` |
| `TRANSACTION_HISTORY` | *"Ramesh ka transaction dikhao"*, *"सुरेश का पुराना हिसाब दिखाओ"* | `TRANSACTION_HISTORY` |
| `CORRECTION` | *"Nahi, 450 tha"*, *"नहीं, 450 था"*, *"Galat ho gaya, 350 tha"* | `CORRECTION` |
| `CLARIFICATION_NEEDED` | *(Triggered when multiple candidates match a spoken customer name)* | `CLARIFICATION_NEEDED` |
| `UNKNOWN` | *"Namaste bhai sahab kaise ho"*, *"500 rupaye"* (incomplete/irrelevant) | `UNKNOWN` |

---

### Natural Language Understanding & Entity Extraction

#### 1. Numerical & Amount Parsing
Supports all common Indian Kirana numbering conventions:
- **Standard Arabic Digits**: `500`, `1500`, `1,200`, `250.50`
- **Devanagari Numerals**: `५००` $\rightarrow$ `500`, `२५०` $\rightarrow$ `250`, `१०००` $\rightarrow$ `1000`
- **Spoken Hindi Words**:
  - Units & Tens: `paanch sau` $\rightarrow$ `500`, `do hazaar` $\rightarrow$ `2000`, `teen sau pachaas` $\rightarrow$ `350`, `chaar sau bees` $\rightarrow$ `420`
  - Large Scales: `das hazaar` $\rightarrow$ `10000`, `ek lakh` $\rightarrow$ `100000`
  - Fractional Multipliers: `dedh sau` $\rightarrow$ `150`, `dhai hazaar` $\rightarrow$ `2500`, `sawa sau` $\rightarrow$ `125`
- **Indian English Colloquialisms**: `one fifty` $\rightarrow$ `150`, `two twenty` $\rightarrow$ `220`

#### 2. Customer Name Extraction
- **Indic Devanagari Transliteration**: Maps `रमेश` $\rightarrow$ `Ramesh`, `सुरेश` $\rightarrow$ `Suresh`, `पूजा` $\rightarrow$ `Pooja`, `मोहन` $\rightarrow$ `Mohan`.
- **Postposition Extraction**: Extracts names preceding Hindi markers `ka`, `ki`, `ke`, `ne`, `ko`, `se` (e.g. *"Ramesh ka"* $\rightarrow$ `Ramesh`, *"Mohan ne"* $\rightarrow$ `Mohan`).
- **Honorific Handling**: Strips honorifics such as `ji`, `bhai`, `sahab`, `didi`, `bhaiya` from ledger names (e.g. *"Ramesh ji ka"* $\rightarrow$ `Ramesh`).
- **Surname Resolution**: Correctly binds known surnames (`Sharma`, `Verma`, `Gupta`, `Patel`, `Singh`).

#### 3. Relative Date Extraction
- **Injectable Reference Clock**: Uses an injectable `reference_date` parameter for deterministic, reproducible unit testing.
- **ISO 8601 Formatting**: Outputs dates in standard `YYYY-MM-DD` format (e.g. `2026-11-12`).
- **Null Safety**: When no date is spoken in the command, the engine explicitly outputs `date: null` (it does **not** guess or assume).
- **Supported Relative Offsets**:
  - `aaj` / `today` / `आज` $\rightarrow$ `reference_date` (offset 0)
  - `kal` / `yesterday` / `कल` $\rightarrow$ `reference_date - 1 day`
  - `parso` / `day before yesterday` / `परसों` $\rightarrow$ `reference_date - 2 days`
  - `tarso` / `तरसों` $\rightarrow$ `reference_date - 3 days`
  - `pichle hafte` / `last week` $\rightarrow$ `reference_date - 7 days`

#### 4. Spoken Correction Handling
When a shopkeeper notices a mistake and says:
> **Shopkeeper**: *"Ramesh ka 500 udhaar."*  
> **Shopkeeper**: *"Nahi, 450 tha."*

The engine parses the second phrase as a **`CORRECTION`** to the prior entry rather than creating a new transaction:
```json
{
  "intent": "CORRECTION",
  "correction_type": "AMOUNT",
  "new_amount": 450.0,
  "original_amount": 500.0,
  "customer_name": "Ramesh",
  "prior_intent": "ADD_CREDIT",
  "date": null,
  "confidence": 0.95,
  "message": "Previous entry corrected to 450.0",
  "raw_text": "Nahi, 450 tha."
}
```
- If prior context is supplied by the caller, original amount and customer are linked.
- If no prior context is available, it returns `new_amount: 450.0` with `original_amount: null` and `customer_name: null`. **It never invents fictitious history.**

#### 5. Duplicate Customer Disambiguation
When the caller provides matching customer records (e.g. both *"Ramesh Sharma"* and *"Ramesh Verma"* exist in the database):
```python
candidates = [
    {"id": 101, "name": "Ramesh Sharma", "phone": "9876543210"},
    {"id": 102, "name": "Ramesh Verma", "phone": "9876543211"},
]
res = engine.parse("Ramesh ka 500 udhaar", candidate_customers=candidates)
```
The engine returns:
```json
{
  "intent": "CLARIFICATION_NEEDED",
  "clarification_type": "CUSTOMER_DISAMBIGUATION",
  "query_name": "Ramesh",
  "candidates": [
    {"id": 101, "name": "Ramesh Sharma", "phone": "9876543210"},
    {"id": 102, "name": "Ramesh Verma", "phone": "9876543211"}
  ],
  "message": "Kaun se Ramesh ki baat kar rahe hain? Ramesh Sharma ya Ramesh Verma?",
  "confidence": 0.95,
  "raw_text": "Ramesh ka 500 udhaar"
}
```
The parser does not choose one arbitrarily; it provides candidate data so the UI/voice loop can ask for clarification.

#### 6. Dual API Interfaces
1. **Structured Dict API (`engine.parse`)**: Recommended for modular testing, frontend inspection, and direct JSON contracts.
2. **Pydantic API (`engine.extract_intent` / `engine.process_sync`)**: Returns `IntentResponse` with `List[ActionItem]` matching existing `backend/main.py` conventions for seamless integration.

---

## 🧪 Automated Testing

Member 4 provides a comprehensive automated test suite (102 tests) covering all requirements. Tests are completely isolated from external databases, live voice sockets, and network APIs.

### Running Tests

```bash
# Set PYTHONPATH to project root
cd KhataFlow-main

# Run all 102 automated tests
python -m pytest backend/tests/ -v
```

### Test Suite Structure

```
backend/tests/
├── __init__.py
├── test_intent_recognition.py   # Hindi, Hinglish, & English intent classification (30+ tests)
├── test_entity_extraction.py     # Arabic, Devanagari digits, spoken Hindi words, names (35+ tests)
├── test_relative_dates.py        # Aaj, kal, parso, tarso, pichle hafte with injectable clock
├── test_correction_handling.py   # Spoken corrections modifying prior entry without duplicate creation
├── test_disambiguation.py        # Candidate customer clarification without arbitrary guessing
├── test_multiple_actions.py      # Compound sentences with multiple actions in one utterance
├── test_invalid_inputs.py        # Incomplete commands, greetings, noise (predictable UNKNOWN results)
└── test_integration.py           # The exact 5 specification commands and end-to-end flows
```

### Test Suite Results Summary
- **Total Tests**: `102 passed`
- **Execution Time**: `< 0.6 seconds`
- **Offline / Mock Friendly**: Yes (no database or API keys required)

---

## 🐳 Deployment Configuration

Member 4 provides containerization configurations for consistent deployments across development and production:

### Files
- **`Dockerfile`**: Multi-stage lightweight Python 3.11 container with audio system libraries (`libasound2`, `portaudio19`, `ffmpeg`) and FastAPI setup.
- **`docker-compose.yml`**: Service definition mapping port 8000, environment variable pass-through (`.env`), healthcheck monitoring, and persistent data volumes for SQLite (`khataflow_data`).
- **`.dockerignore`**: Excludes virtual environments, caches, and `.env` files from container build context.

### Running with Docker Compose

```bash
# Build and start container in detached mode
docker-compose up --build -d

# Check service logs
docker-compose logs -f backend

# Verify health status
curl http://localhost:8000/docs
```

---

## 🛠️ Local Development Quickstart

### Prerequisites
- **Python** (3.10+)
- **Node.js** (v18+)

### 1. Configure Environment
```bash
cp .env.example .env
```
*(Keep your secrets in `.env`. Never commit `.env` or API keys to version control).*

### 2. Backend Setup
```bash
cd KhataFlow-main
python -m venv backend/venv

# Activate venv
# Windows:
backend\venv\Scripts\activate
# Linux/macOS:
source backend/venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Run FastAPI server
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 📄 License
MIT License.
