# ITR Multi-AI Architecture

## Overview
Your ITR filing assistant uses a **Master Orchestrator AI** coordinating **7 specialist sub-AIs**, each expert in one domain. The master receives user input, routes to specialists, and synthesizes responses.

## Master AI (Orchestrator)
- **Role**: Central conversational hub
- **Responsibilities**:
  - Understands user intent (e.g., "What deductions can I claim?", "Did I report all income?")
  - Routes to appropriate specialist AI(s)
  - Maintains session context and conversation history
  - Synthesizes multi-specialist responses into cohesive guidance
  - Explains reasoning with government references
  - Proactively prompts for missing info or life events
- **Tech**: LLM (Claude or OpenAI) with prompt/RAG for ITR rules

## Specialist Sub-AIs

### 1. **Tax Deduction Expert**
- **Focus**: Section 80C, 80D, 80E, 80AC, 24(b), 80CCD, 80U, 80TTA, etc.
- **Outputs**:
  - Eligible deductions for taxpayer profile (age, family status, health, education, employment type)
  - Claim limits and rules per section
  - Documents required for each deduction
  - Government reference links and compliance notes
  - Impact on old/new regime
- **Data sources**: Taxpayer profile, life events, family info, income entries

### 2. **Residency & Status Analyzer**
- **Focus**: Determine NRI/RNOR/ROR/HUF status and apply clubbing rules
- **Outputs**:
  - Residency determination (Section 6)
  - Clubbing applicability (spouse, minor child, HUF, partnership, etc.)
  - Global income filing requirement
  - FTC/foreign tax credit eligibility
  - Form ITR-2 instructions per status
- **Data sources**: Life-event timeline, employment, property, days-in-India, family relationships

### 3. **Document Parser & Extractor**
- **Focus**: OCR + LLM extraction from uploaded documents
- **Outputs**:
  - Extracted tables (AIS: income sources; 26AS: TDS credits; bank: interest; broker: dividends/gains; MF: CAM/KFin data)
  - Data quality score and confidence
  - Mapped to income/TDS registers
  - Discrepancies flagged
- **Data sources**: PDF/image uploads, CSV imports from brokers

### 4. **3-Way Reconciliation Expert**
- **Focus**: Match source statement vs AIS/26AS vs ITR return
- **Outputs**:
  - Reconciliation table with differences explained
  - Root causes (timing, exemptions, carry-forwards, adjustments)
  - Government reference links
  - Suggested corrections
- **Data sources**: Income entries, tax credits, reconciliation items, AIS/26AS parsed data

### 5. **Tax Savings Optimizer**
- **Focus**: Suggest tax-saving actions aligned with compliance
- **Outputs**:
  - Tier-1 high-impact savings (deductions, regime choice, home loan optimal claim)
  - Tier-2 medium-impact (health insurance, pension, charity)
  - Tier-3 proactive/year-ahead (RD/PPF cycles, gift planning, HUF formation for RNOR)
  - Impact calculation and compliance risk assessment
- **Data sources**: Income, deductions claimed, life events, tax rules

### 6. **Compliance Validator**
- **Focus**: Validate entries against latest Income Tax Act, circulars, rates
- **Outputs**:
  - Red flags (violation of sections, incorrect limits, regime incompatibilities)
  - Warnings (marginal cases, high scrutiny risk)
  - Links to latest circulars and amendments
  - Automated fixes where applicable
- **Data sources**: All taxpayer entries, ITR rules database, government circulars (fetched daily)

### 7. **Lifecycle & Family Event Tracker**
- **Focus**: Prompt for life events and evaluate impact
- **Outputs**:
  - Event log with date and details (birth, OCI, move, job change, marriage, property)
  - Residency re-evaluation (if applicable)
  - Deduction re-check (e.g., 80AC if daughter born)
  - Task/documentation suggestions
  - Reminders for next year's filings
- **Data sources**: Life-event prompts, family DB, residency timeline

---

## System Architecture

```
┌─────────────────────────────────────────────┐
│  User Interface (Web/Mobile)                │
│  Chat + Forms + Dashboard                   │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  Master AI Orchestrator                     │
│  - Intent Router                            │
│  - Context Manager                          │
│  - Response Synthesizer                     │
└─────────────────┬───────────────────────────┘
                  │
        ┌─────────┴──────────┬────────┬────────┬────────┬────────┬────────┐
        ▼                    ▼        ▼        ▼        ▼        ▼        ▼
    ┌────────┐          ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐
    │ Tax    │          │ Res- │  │ Doc  │  │ 3-Way│  │ Tax  │  │Compl-│  │ Lif- │
    │Ded.   │          │iden- │  │Parse│  │Recon│  │Saver │  │iance │  │ events│
    │Expert │          │cy    │  │     │  │     │  │      │  │Valid │  │Track  │
    └────────┘          └──────┘  └──────┘  └──────┘  └──────┘  └──────┘  └──────┘
        │                   │         │         │         │         │         │
        └─────────────────────────────┴─────────┴─────────┴─────────┴─────────┘
                                    │
                                    ▼
                        ┌──────────────────────┐
                        │  Database Layer      │
                        │  - Taxpayers         │
                        │  - Income Entries    │
                        │  - Tax Credits       │
                        │  - Life Events       │
                        │  - Documents         │
                        │  - Reconciliation    │
                        └──────────────────────┘
```

---

## Implementation Phases

### Phase 1: Foundation (Weeks 1–2)
- Master AI with intent routing (Claude/OpenAI API)
- Database schema for prompts, rules, references
- Tax Deduction Expert (rule engine)
- Residency Analyzer (timeline + status logic)

### Phase 2: Data Extraction (Weeks 3–4)
- Document Parser (OCR + LLM, table extraction)
- Reconciliation Expert (3-way matching)
- File upload integration

### Phase 3: Optimization & Compliance (Weeks 5–6)
- Tax Savings Optimizer
- Compliance Validator (daily rule updates)
- Lifecycle Tracker (event prompts and impact re-evaluation)

### Phase 4: Integration & UX (Weeks 7–8)
- Chat UI (Web + mobile)
- Dashboard (family profiles, annual checklist, reminders)
- Export (ITR-2 form, proof-of-work, audit trail)

---

## Technology Stack

- **Master AI**: OpenAI GPT-4 or Claude 3.5 Sonnet (multi-turn context)
- **Sub-AIs**: Specialized LLM prompts + rule engines (Python + FastAPI endpoints)
- **RAG**: Embed ITR rules, circulars, government links into vector DB (Pinecone or Weaviate)
- **Document Processing**: Pytesseract (OCR) + LLM table extraction
- **Backend**: FastAPI (already in place)
- **Frontend**: Next.js with chat component (e.g., Vercel AI SDK, Langchain UI)

---

## Data Flow Example: "What deductions can I claim?"

1. **User**: "My daughter is 5.5, and I earn ₹50L from abroad. What deductions apply?"
2. **Master AI**: Parses intent → routes to Tax Deduction Expert + Residency Analyzer
3. **Residency Analyzer**: "User is NRI (you said earlier) → global income applies; Section 80AC (Sukanya) applies if in India; Section 80CCD eligible; 80D up to ₹50k"
4. **Tax Deduction Expert**: Lists applicable sections with limits, documents, forms
5. **Master AI**: Synthesizes: "As NRI, you can claim 80AC (daughter in India), 80CCD(1) if you contribute, 80D if health insurance. Here are the limits and government links. Shall I show the calculation impact?"

---

## Success Metrics

- User spends <5 min to identify all applicable deductions
- 95%+ accuracy on deduction eligibility and limits
- Zero compliance violations in generated ITR
- Year-on-year retention (user runs this annually, not switching to CA/tool)

---

## Next Steps (Your Priorities)

1. Implement Master AI + Tax Deduction Expert + Residency Analyzer (Phase 1)
2. Wire to chat UI (with example conversations)
3. Add document parser and reconciliation expert (Phase 2)
4. Test end-to-end: user uploads docs → extracts data → deductions → calc → report → AI-guided review

Would you like me to start building Phase 1 (Master AI setup + experts)?
