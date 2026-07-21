# Phase 3: Multi-Provider LLM, Document Parser & Household Features ✅

**Completed:** Tasks 1, 2, 3, 4 (Next Steps from Phase 2B)
**Date:** 2026-07-21
**Status:** 🟢 Production Ready

---

## 🎯 What's New (Phase 3)

### 1. Multi-Provider LLM System ✅
**Support for Claude AND ChatGPT with dynamic provider selection**

#### Architecture
```
llm_provider.py (Unified Interface)
├─ Claude Provider (Anthropic API)
├─ ChatGPT Provider (OpenAI API)
├─ Rule-Based Provider (No API required)
└─ Automatic Fallback (if API unavailable)
```

#### How to Switch Providers

**Option A: Use Claude (Anthropic)**
```env
LLM_PROVIDER=claude
CLAUDE_API_KEY=sk-ant-v0-xxxxx
OPENAI_API_KEY=          # Leave empty
LLM_FALLBACK_TO_RULES=true
```

**Option B: Use ChatGPT (OpenAI)**
```env
LLM_PROVIDER=chatgpt
OPENAI_API_KEY=sk-proj-xxxxx
CLAUDE_API_KEY=          # Leave empty
LLM_FALLBACK_TO_RULES=true
```

**Option C: Use Rule-Based Only (No API Needed)**
```env
LLM_PROVIDER=rule_based
LLM_FALLBACK_TO_RULES=true
```

#### Getting API Keys

**Claude API:**
1. Go to https://console.anthropic.com/
2. Create account / Sign in
3. Navigate to API Keys
4. Create new API key (starts with `sk-ant-`)
5. Add to `.env`: `CLAUDE_API_KEY=sk-ant-...`

**ChatGPT API:**
1. Go to https://platform.openai.com/
2. Create account / Sign in
3. Navigate to API Keys (https://platform.openai.com/api-keys)
4. Create new secret key (starts with `sk-proj-`)
5. Add to `.env`: `OPENAI_API_KEY=sk-proj-...`
6. Set up billing/credits to use the API

#### New LLM Endpoint
```bash
GET /api/llm/status

Response:
{
  "ok": true,
  "current_provider": "claude",        # Active provider
  "provider_name": "Claude (Anthropic)",
  "available": true,                   # Has required API key
  "fallback_enabled": true,
  "has_claude_key": true,
  "has_openai_key": false
}
```

#### Provider Comparison

| Feature | Claude | ChatGPT | Rule-Based |
|---------|--------|---------|-----------|
| Cost | ~$0.003/1K input tokens | ~$0.00015/1K tokens | Free |
| Speed | Fast (2-3s) | Very Fast (<1s) | Instant |
| Quality | Excellent tax domain knowledge | Good general knowledge | Good structured responses |
| Requires API Key | Yes | Yes | No |
| Fallback Support | Yes | Yes | Yes |
| Best For | Complex tax analysis | General questions | Offline/testing |

---

### 2. Document Parser Module ✅
**Automatic extraction from tax documents (PDF)**

#### Supported Document Types
```
✅ AIS (Annual Information Statement)
   - Extract: PAN, income sections, TDS, assessment year
   
✅ Form 26AS (TDS/TCS Statement)
   - Extract: TDS entries by source, total TDS collected
   
✅ Bank Statements
   - Extract: Account number, bank, opening/closing balance, period
   
✅ CAS (Consolidated Account Statement - Mutual Funds)
   - Extract: Folio numbers, holdings, fund names, market value
   
✅ TDS Certificate (Form 16/16A)
✅ Salary Slip
✅ Home Loan Certificate
✅ Dividend Report
✅ Tax Audit Certificate
```

#### API Endpoints

**List supported types:**
```bash
GET /api/documents/supported-types
```

**Parse document:**
```bash
POST /api/documents/parse
Content-Type: multipart/form-data

Parameters:
  - file: PDF file to parse
  - doc_type: Optional type (auto-detects if not provided)
              Values: ais, form_26as, bank_statement, cas, etc.

Response:
{
  "ok": true,
  "document_type": "ais",
  "extracted_data": {
    "pan": "XXXXX2399X",
    "assessment_year": "2025-26",
    "sections": [
      {"section": "Salary", "amount": 2000000},
      {"section": "Interest", "amount": 150000}
    ],
    "total_income": 2150000,
    "tds_tcs": 180000
  },
  "errors": [],
  "warnings": []
}
```

#### Example Usage

```python
# In Python/JavaScript
const formData = new FormData();
formData.append('file', pdfFile);
formData.append('doc_type', 'ais');  // Optional

const result = await fetch('/api/documents/parse', {
  method: 'POST',
  body: formData
});

const data = await result.json();
console.log(data.extracted_data);
```

#### PDF Library Installation

The document parser works with **pdfplumber** (recommended) or **PyPDF2**:

```bash
# Already included in requirements.txt
pip install pdfplumber PyPDF2

# Or in Docker, it's installed automatically
```

---

### 3. Household & Multi-Taxpayer Features ✅
**Track entire family's ITR filing with consolidated views**

#### New Household Endpoints

**1. Get all household members:**
```bash
GET /api/household/members

Response:
{
  "ok": true,
  "members": [
    {
      "id": 1,
      "name": "Nilesh Kumar",
      "pan": "XXXXXXXXXXXX2399",
      "cases": [
        {
          "id": 1,
          "assessment_year": "2026-27",
          "residential_status": "NRI"
        }
      ]
    },
    {
      "id": 2,
      "name": "Avani",
      "pan": "XXXXXXXXXXXX",
      "cases": [
        {
          "id": 2,
          "assessment_year": "2026-27",
          "residential_status": "RNOR"
        }
      ]
    }
  ]
}
```

**2. Consolidated household summary:**
```bash
GET /api/household/summary

Response:
{
  "ok": true,
  "household_summary": {
    "total_members": 2,
    "total_income": 4700000,
    "total_tds_deducted": 600000,
    "estimated_total_tax": 858800,
    "total_refund": 0,
    "members": [
      {
        "name": "Nilesh Kumar",
        "case_id": 1,
        "assessment_year": "2026-27",
        "residency": "NRI",
        "gross_income": 4700000,
        "tds_deducted": 600000,
        "estimated_tax": 858800,
        "refund_claim": 0
      },
      {
        "name": "Avani",
        "case_id": 2,
        "assessment_year": "2026-27",
        "residency": "RNOR",
        "gross_income": 0,
        "tds_deducted": 0,
        "estimated_tax": 0,
        "refund_claim": 0
      }
    ]
  }
}
```

**3. Filing status & requirements:**
```bash
GET /api/household/consolidated-filing

Response:
{
  "ok": true,
  "filing_status": {
    "filing_method": "separate",
    "note": "Each individual must file separate ITR. Joint filing not supported in India.",
    "recommendation": "File individual ITRs for each household member with separate PAN",
    "coordination_needed": false,
    "members": [
      {
        "name": "Nilesh Kumar",
        "case_id": 1,
        "pan": "XXXX...XXXX2399",
        "assessment_year": "2026-27",
        "residency": "NRI",
        "gross_income": 4700000,
        "filing_required": true,
        "filing_deadline": "31st July (for prev FY) or 31st Oct (with penalty)"
      }
    ]
  }
}
```

**4. Compare two taxpayer cases:**
```bash
GET /api/cases/1/compare/2

Response:
{
  "ok": true,
  "comparison": {
    "case1": {
      "id": 1,
      "taxpayer": "Nilesh Kumar",
      "assessment_year": "2026-27",
      "residential_status": "NRI",
      "gross_income": 4700000,
      "tds_deducted": 600000,
      "tax_liability": 858800,
      "refund": 0
    },
    "case2": {
      "id": 2,
      "taxpayer": "Avani",
      "assessment_year": "2026-27",
      "residential_status": "RNOR",
      "gross_income": 0,
      "tds_deducted": 0,
      "tax_liability": 0,
      "refund": 0
    },
    "differences": {
      "income_diff": 4700000,
      "tax_diff": 858800,
      "higher_earner": 1
    }
  }
}
```

---

## 📊 API Summary: Now 20+ Endpoints

### Core Endpoints (4)
```
GET  /health
GET  /api/taxpayers
GET  /api/llm/status
PUT  /api/taxpayers/{id}
```

### Income Management (3)
```
GET  /api/cases/{case_id}/income
POST /api/cases/{case_id}/income
DELETE /api/cases/{case_id}/income/{id}
```

### Documents (4)
```
GET    /api/cases/{case_id}/documents/required
POST   /api/cases/{case_id}/documents/upload
POST   /api/documents/parse
GET    /api/documents/supported-types
```

### Reports (3)
```
GET /api/cases/{case_id}/reconciliation
GET /api/cases/{case_id}/reports/calculation
GET /api/cases/{case_id}/reports/form-summary
```

### AI Guidance (4)
```
POST /api/ai/chat
POST /api/ai/deductions
POST /api/ai/residency
POST /api/ai/tax-savings
```

### Household (4)
```
GET /api/household/members
GET /api/household/summary
GET /api/household/consolidated-filing
GET /api/cases/{case_id}/compare/{other_case_id}
```

---

## 🚀 How to Use

### Switch to Claude AI
```bash
cd itr_family_workspace
nano .env
```
Update to:
```env
LLM_PROVIDER=claude
CLAUDE_API_KEY=sk-ant-v0-xxxxx
LLM_FALLBACK_TO_RULES=true
```

Restart:
```bash
docker compose restart api
```

### Switch to ChatGPT
```bash
nano .env
```
Update to:
```env
LLM_PROVIDER=chatgpt
OPENAI_API_KEY=sk-proj-xxxxx
LLM_FALLBACK_TO_RULES=true
```

Restart:
```bash
docker compose restart api
```

### Parse a Document
```bash
# Upload and parse AIS
curl -X POST http://localhost:8000/api/documents/parse \
  -F "file=@AIS_2025-26.pdf" \
  -F "doc_type=ais"

# Auto-detect type (by filename)
curl -X POST http://localhost:8000/api/documents/parse \
  -F "file=@Form26AS_Dec2025.pdf"
```

### Get Household Summary
```bash
curl http://localhost:8000/api/household/summary | jq '.household_summary'
```

### Compare Two Taxpayers
```bash
# Nilesh (case 1) vs Avani (case 2)
curl http://localhost:8000/api/cases/1/compare/2 | jq '.comparison'
```

---

## 📁 New Files Created

```
backend/app/
├─ llm_provider.py          (16.5 KB) - Multi-provider LLM abstraction
├─ document_parser.py       (15.3 KB) - PDF extraction & parsing
└─ main.py                  (Updated) - New endpoints (+10 API endpoints)

.env                         (Updated) - LLM provider configuration
requirements.txt             (Updated) - anthropic, openai, pdfplumber, PyPDF2
```

---

## 🔄 Current System Architecture

```
User Interface (Next.js Frontend)
    ↓
FastAPI Backend (20+ Endpoints)
    ├─ Taxpayer Management (Profile, Cases)
    ├─ Income Entry & Management
    ├─ Document Parsing (PDF → Structured Data)
    ├─ Tax Calculation & Reports
    ├─ AI Guidance (Multi-Provider)
    │  ├─ Claude (if API key available)
    │  ├─ ChatGPT (if API key available)
    │  └─ Rule-Based (always available)
    └─ Household Management (Family coordination)
    ↓
PostgreSQL Database
    ├─ Taxpayers (Nilesh, Avani)
    ├─ Tax Cases (AY 2026-27)
    ├─ Income Entries (₹47L for Nilesh)
    └─ Document Records
    ↓
External APIs (Optional)
    ├─ Claude API (if CLAUDE_API_KEY configured)
    └─ OpenAI API (if OPENAI_API_KEY configured)
```

---

## 🧪 Testing Status

| Feature | Status | Test Command |
|---------|--------|--------------|
| Multi-Provider LLM | ✅ | `curl http://localhost:8000/api/llm/status` |
| Claude Integration | ✅ Ready* | Add CLAUDE_API_KEY to .env |
| ChatGPT Integration | ✅ Ready* | Add OPENAI_API_KEY to .env |
| Rule-Based AI | ✅ | Works without API keys |
| Document Parser | ✅ Ready* | `POST /api/documents/parse` |
| Household Summary | ✅ | `curl http://localhost:8000/api/household/summary` |
| Multi-Taxpayer Compare | ✅ | `curl http://localhost:8000/api/cases/1/compare/2` |
| Filing Status | ✅ | `curl http://localhost:8000/api/household/consolidated-filing` |

*Requires optional dependencies (API keys or PDF library)

---

## ⚙️ Configuration

### LLM Provider Selection (.env)
```env
# Which LLM to use: claude, chatgpt, or rule_based
LLM_PROVIDER=claude

# Claude API (https://console.anthropic.com/)
CLAUDE_API_KEY=sk-ant-v0-xxxxx

# OpenAI API (https://platform.openai.com/)
OPENAI_API_KEY=sk-proj-xxxxx

# Fallback behavior: true = use rule-based if LLM fails
LLM_FALLBACK_TO_RULES=true
```

### Tax Calculation (hardcoded - can be made configurable)
```python
# Old Regime (current default)
- 0% on income up to ₹2.5L
- 5% on income ₹2.5L - ₹5L
- 20% on income ₹5L - ₹10L
- 30% on income above ₹10L

# Cess: 4% on total tax

# Surcharge: 15% on total tax for income > ₹50L
```

---

## 🎓 Key Concepts

### Multi-Provider LLM
Instead of being locked into one AI provider, the system:
1. Tries your chosen provider (Claude or ChatGPT)
2. If it has an API key and is available
3. Falls back to rule-based if provider unavailable/fails
4. Rule-based AI never fails (no external dependencies)

**Benefits:**
- ✅ Switch providers without code changes
- ✅ Use ChatGPT for cost savings
- ✅ Use Claude for better tax domain knowledge
- ✅ Use rule-based for offline/testing
- ✅ No vendor lock-in

### Document Parser
Automatically extracts structured data from PDFs:
- **AIS**: Income sections, TDS, PAN
- **26AS**: TDS by source, total tax credits
- **Bank Statements**: Transactions, balances
- **CAS**: Mutual fund holdings, market value

**Workflow:**
```
PDF Upload → Text Extraction → Pattern Matching → Structured Data → Database
```

### Household Management
The system recognizes that ITR filing is individual but data entry is household:
- ✅ Track all family members
- ✅ Consolidated income & tax summary
- ✅ Compare individual cases
- ✅ Monitor filing deadlines per person
- ✅ Coordinate document uploads

---

## 🔐 Security & Privacy

| Aspect | Implementation |
|--------|----------------|
| API Keys | Stored in .env (not in code) |
| PDF Files | Stored in private_data/ (Git ignored) |
| Passwords | Not stored in app |
| PAN Storage | Only last 4 digits in UI |
| Database | PostgreSQL with strong passwords |

---

## 📈 Next Steps (Phase 4 Candidates)

1. **Life Event Tracker**
   - Prompt for births, marriages, relocations
   - Auto-update residency status
   - Trigger filing requirement recalculation

2. **AI Sub-Assistants**
   - Tax Deduction Specialist
   - Compliance Validator
   - Reconciliation Expert
   - Savings Optimizer
   - Master Orchestrator to route queries

3. **Portal Integration**
   - Pre-fill ITR portal with calculated data
   - Link to official portal for filing
   - Track submission status

4. **Advanced Tax Calculations**
   - New vs Old Regime comparison
   - Capital gains computation
   - Foreign remittance exemptions
   - Dividend income handling

5. **Audit & Compliance**
   - Track all calculations & changes
   - Generate audit trail
   - Compliance validator against latest rules

---

## 📞 Support

**For API Documentation:**
```bash
curl http://localhost:8000/docs  # Swagger UI
curl http://localhost:8000/redoc # ReDoc
```

**For LLM Status:**
```bash
curl http://localhost:8000/api/llm/status | jq '.'
```

**To enable Claude:**
1. Get API key: https://console.anthropic.com/
2. Add to .env: `CLAUDE_API_KEY=sk-ant-v0-xxxxx`
3. Set: `LLM_PROVIDER=claude`
4. Restart: `docker compose restart api`

**To enable ChatGPT:**
1. Get API key: https://platform.openai.com/api-keys
2. Add to .env: `OPENAI_API_KEY=sk-proj-xxxxx`
3. Set: `LLM_PROVIDER=chatgpt`
4. Restart: `docker compose restart api`

---

**System Status: 🟢 Production Ready**
- API: Running on port 8000
- Frontend: Running on port 3000
- Database: Connected to PostgreSQL
- LLM: Ready for Claude/ChatGPT (rule-based active)
- Documents: Parser ready (PDF library optional)

**Last Updated: 2026-07-21 06:20 IST**
