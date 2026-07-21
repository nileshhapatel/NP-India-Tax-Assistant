# Development Roadmap - NP India Tax Assistant

**Branch**: `dev`  
**Status**: Active Development  
**Last Updated**: 2026-07-21

---

## 🎯 Development Phases

### **Phase 1: Core Tax Engine & Calculation** (Critical Path)
- [x] FastAPI backend with Docker
- [x] PostgreSQL database
- [x] Multi-provider LLM (Claude/ChatGPT)
- [ ] **Tax Calculation Engine** - Old/New regime calculator with all deductions
- [ ] **Tax Report Generator** - Two professional reports (Calculations + Form Summary)
- [ ] **Household Assistant** - Family data management with prompts

### **Phase 2: AI Specialists & Data Processing** (High Priority)
- [ ] **Master AI Orchestrator** - Central conversation router and context manager
- [ ] **Document Parser AI** - OCR + extraction from AIS, 26AS, statements
- [ ] **Lifecycle Tracker AI** - Family events and residency re-evaluation
- [ ] **Deduction Optimizer AI** - Tax saving suggestions with compliance
- [ ] **Reconciliation Expert AI** - 3-way matching and discrepancy resolution

### **Phase 3: Advanced Features** (Medium Priority)
- [ ] **Tax Savings Optimizer AI** - Regime and strategy recommendations
- [ ] **Compliance Validator AI** - Government rules and cross-check validation
- [ ] **Final Review UI** - Two-tab professional report interface
- [ ] **Life-event Tracker UI** - Birth, death, OCI, moves, employment changes

### **Phase 4: Portal Integration** (Integration)
- [ ] Portal filing integration with signature capture
- [ ] Direct submission workflow
- [ ] Offline utility compatibility

---

## 📋 Immediate Next Steps (Priority Order)

### **1. Tax Calculation Engine** (Foundation)
**Files to create/modify**:
- `backend/app/tax_calculator.py` - Core calculation logic
- `backend/app/deduction_rules.py` - Deduction definitions and validation
- `backend/app/regime_calculator.py` - Old vs New regime comparison

**Features**:
- Gross income aggregation (salary, business, investment, rental)
- Deduction calculations (Section 80C, 80D, 80E, etc.)
- Regime comparison (Old vs New)
- Surcharge, cess, education-cess calculation
- Effective tax rate computation
- TDS credit adjustments

---

### **2. Tax Report Generator** (Output Layer)
**Files to create**:
- `backend/app/report_generator.py` - Report creation
- `backend/app/report_templates.py` - Template definitions

**Reports**:
1. **Report 1: Calculation Breakdown**
   - Income sources with references
   - Deductions with justification
   - Tax slabs and rates
   - Surcharge and cess calculation
   - Government regulation links

2. **Report 2: Form Summary**
   - ITR-2 form mapping
   - Section-wise summary
   - Three-way reconciliation results
   - Audit trail and validation status

---

### **3. Household Assistant API** (Family Management)
**Endpoints**:
- `POST /api/household/members` - Add family member
- `GET /api/household/members` - List all members
- `PUT /api/household/members/{id}` - Update member
- `POST /api/household/events` - Log life events
- `GET /api/household/dashboard` - Consolidated view

**Database Tables**:
- `family_members` - Names, PAN, relationship, residency status
- `household_events` - Life events with impact analysis
- `consent_records` - Audit trail of permissions

---

### **4. Master AI Orchestrator** (Conversation Hub)
**Architecture**:
- Main conversation endpoint that routes to specialists
- Session context manager
- Intent classifier
- Response synthesizer

**Sub-AI Specialists**:
1. `tax-specialist` - Taxation questions
2. `deduction-specialist` - Deduction optimization
3. `compliance-specialist` - Rules and validation
4. `reconciliation-specialist` - Matching and discrepancies
5. `documents-specialist` - File extraction and validation

---

### **5. Document Parser AI** (Data Extraction)
**Features**:
- PDF/image extraction using pytesseract
- LLM-based parsing for:
  - AIS (Annual Information Statement)
  - Form 26AS (TDS information)
  - Bank statements (interest, NRE/NRO)
  - Broker reports (dividends, capital gains)
  - Mutual fund CAS (holdings, gains)
  - Property documents

**Validation**:
- Data type checking
- Range validation
- Cross-field consistency
- Mapping to income/TDS registers

---

## 🛠️ Technology Stack Decision Matrix

| Component | Options | Recommendation | Rationale |
|-----------|---------|-----------------|-----------|
| Tax Calc | Python library vs Custom | **Custom Python module** | Full control over Indian tax rules, real-time updates |
| Report Gen | ReportLab vs PDF.js vs LaTeX | **ReportLab + Jinja2** | Server-side generation, templating, consistent output |
| Document Parse | PyPDF + pytesseract vs AWS Textract | **PyPDF + pytesseract locally** | Privacy (no cloud), open-source, cost-effective |
| LLM Routing | Custom vs LangChain vs CrewAI | **LangChain** | Chain orchestration, memory management, faster iteration |
| Frontend Charts | Chart.js vs D3 vs Plotly | **Recharts (React)** | Modern, responsive, integrates with Next.js |
| State Mgmt | Redux vs Zustand vs Jotai | **Zustand** | Lightweight, minimal boilerplate, good for complex forms |

---

## 📊 Development Workflow

```bash
# Create feature branch
git checkout -b feature/tax-calc-engine

# Make changes, test locally
npm run dev          # Frontend
python -m pytest     # Backend tests

# Commit and push
git add .
git commit -m "feat: tax-calc-engine - implement new regime calculator"
git push origin feature/tax-calc-engine

# Create PR on GitHub for review
# Merge to dev after review

# When phase complete: merge dev → main
git checkout main
git merge dev
git push origin main
```

---

## ✅ Definition of Done (for each feature)

- [ ] Code written with type hints and docstrings
- [ ] Unit tests written (80%+ coverage target)
- [ ] Integration tests pass
- [ ] API documented in Swagger/OpenAPI
- [ ] Error handling implemented
- [ ] Logging added for debugging
- [ ] Code reviewed (if in team)
- [ ] Merged to dev branch
- [ ] Tested end-to-end locally
- [ ] Commit message follows convention

---

## 🚀 Quick Commands

```bash
# Start development
cd itr_family_workspace
source .venv/bin/activate
docker-compose up -d

# Backend tests
python -m pytest backend/tests/ -v

# Frontend dev
cd frontend && npm run dev

# View logs
docker-compose logs -f api
docker-compose logs -f db

# Check code quality
flake8 backend/
mypy backend/

# Create backup before major changes
git stash
pg_dump -Fc India_ITR_Family > backup_$(date +%s).dump
```

---

## 📝 Notes

- All changes committed to `dev` branch only
- `main` branch is production-ready (only merge after full testing)
- Keep `.env` and `private_data/` in `.gitignore` always
- Update this roadmap as priorities change
- Reference GitHub issues for tracking individual tasks

---

**Next Session**: Continue with Tax Calculation Engine implementation
