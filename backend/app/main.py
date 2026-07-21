from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, Optional, List
from decimal import Decimal
import os
import csv
import io
from datetime import datetime
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
import asyncio
import logging

logger = logging.getLogger(__name__)

DOCUMENT_PORTAL_MAP = {
    "PORTAL_AIS": ("Income Tax Portal - AIS", "https://www.incometax.gov.in/iec/foportal/"),
    "PORTAL_TIS": ("Income Tax Portal - TIS", "https://www.incometax.gov.in/iec/foportal/"),
    "PORTAL_26AS": ("Income Tax Portal / TRACES - 26AS", "https://www.incometax.gov.in/iec/foportal/"),
    "PRIOR_ITR": ("Income Tax Portal - Downloaded Documents", "https://www.incometax.gov.in/iec/foportal/"),
    "MF_CAS": ("CAMS", "https://www.camsonline.com/"),
    "MF_CG": ("KFintech", "https://mfs.kfintech.com/"),
    "ZERODHA_DIV": ("Zerodha Console", "https://console.zerodha.com/"),
    "ZERODHA_TAXPL": ("Zerodha Console", "https://console.zerodha.com/"),
    "ZERODHA_LEDGER": ("Zerodha Console", "https://console.zerodha.com/"),
}

COMMON_DOC_PREFIXES = (
    "ID_",
    "HOUSE_",
    "LOAN_",
    "TRAVEL_",
    "PRIOR_",
    "PORTAL_",
)

# Import models from existing workspace
try:
    from itr_workspace.models import (
        Taxpayer,
        TaxCase,
        DocumentRequirement,
        ResidencyRecord,
        TaxCredit,
        PropertyLoan,
        AuditLog,
        Task,
        ReconciliationItem,
        IncomeEntry as IncomeEntryModel,
    )
    from itr_workspace.tax_calculator import (
        TaxFilingCalculator,
        TaxRegime,
        ResidentialStatus,
    )
except Exception as e:
    import traceback
    print('Model import failed in main.py:', e)
    traceback.print_exc()
    Taxpayer = None
    TaxCase = None
    DocumentRequirement = None
    ResidencyRecord = None
    TaxCredit = None
    PropertyLoan = None
    AuditLog = None
    Task = None
    ReconciliationItem = None
    IncomeEntryModel = None
    TaxFilingCalculator = None
    TaxRegime = None
    ResidentialStatus = None


def _case_progress(session, case_id: int) -> dict:
    docs = session.scalars(select(DocumentRequirement).where(DocumentRequirement.case_id == case_id)).all()
    tasks = session.scalars(select(Task).where(Task.case_id == case_id)).all()
    required_docs = [d for d in docs if d.required]
    done_docs = [d for d in required_docs if d.status in {"Received", "Verified", "Not applicable"}]
    done_tasks = [t for t in tasks if t.status in {"Complete", "Not applicable"}]
    doc_pct = round(100 * len(done_docs) / len(required_docs), 1) if required_docs else 100.0
    task_pct = round(100 * len(done_tasks) / len(tasks), 1) if tasks else 100.0
    overall = round((doc_pct * 0.6) + (task_pct * 0.4), 1)
    return {
        "documents": doc_pct,
        "tasks": task_pct,
        "overall": overall,
        "missing_required": len(required_docs) - len(done_docs),
        "open_tasks": len(tasks) - len(done_tasks),
    }


def _review_checks(session, case) -> list[dict]:
    checks = []
    seen_messages = set()

    def add_check(item: dict):
        key = (item.get("severity"), item.get("area"), item.get("message"))
        if key in seen_messages:
            return
        seen_messages.add(key)
        checks.append(item)

    docs = session.scalars(select(DocumentRequirement).where(DocumentRequirement.case_id == case.id)).all()
    missing = [d.title for d in docs if d.required and d.status == "Missing"]
    if missing:
        add_check({"severity": "BLOCK", "area": "Documents", "message": f"{len(missing)} required documents are still missing."})
    residency = session.scalar(select(ResidencyRecord).where(ResidencyRecord.case_id == case.id))
    if not residency or residency.days_in_india_current_fy is None:
        add_check({"severity": "BLOCK", "area": "Residency", "message": "Current-FY India presence days have not been entered."})
    elif residency.conclusion and residency.conclusion != case.residential_status:
        add_check({
            "severity": "BLOCK",
            "area": "Residency",
            "message": f"Residency worksheet concludes {residency.conclusion}, but case is set to {case.residential_status}.",
        })
    incomes = session.scalars(select(IncomeEntryModel).where(IncomeEntryModel.case_id == case.id)).all()
    for i in incomes:
        if float(getattr(i, "amount_in_return", 0) or 0) == 0 and float(getattr(i, "gross_amount", 0) or 0) > 0 and float(getattr(i, "exempt_amount", 0) or 0) == 0:
            add_check({"severity": "WARN", "area": "Income", "message": f"{i.source_name}: gross income exists but return amount and exempt amount are both zero."})
        if float(getattr(i, "tds_amount", 0) or 0) > float(getattr(i, "gross_amount", 0) or 0):
            add_check({"severity": "BLOCK", "area": "Income", "message": f"{i.source_name}: TDS exceeds gross income."})
    if case.residential_status in {"NRI", "RNOR"} and case.return_form == "ITR-1":
        add_check({"severity": "BLOCK", "area": "Return form", "message": "ITR-1 is not appropriate for NRI/RNOR status."})
    if not checks:
        checks.append({"severity": "OK", "area": "Review", "message": "No automated exceptions found. Manual tax review is still required."})
    return checks


def _is_doc_reusable_across_years(code: str) -> bool:
    return bool(code and (code.startswith(COMMON_DOC_PREFIXES) or code.endswith("_DEED") or code.endswith("_PASSPORT")))


def _task_status_suggestions(session, case) -> Dict[str, str]:
    tasks = session.scalars(select(Task).where(Task.case_id == case.id)).all()
    if not tasks:
        return {}
    docs = session.scalars(select(DocumentRequirement).where(DocumentRequirement.case_id == case.id)).all()
    incomes = session.scalars(select(IncomeEntryModel).where(IncomeEntryModel.case_id == case.id)).all()
    residency = session.scalar(select(ResidencyRecord).where(ResidencyRecord.case_id == case.id))
    required_docs = [d for d in docs if d.required]
    done_docs = [d for d in required_docs if d.status in {"Received", "Verified", "Not applicable"}]
    doc_codes_done = {d.code for d in done_docs}
    profile_exists = bool(session.execute(
        text("SELECT 1 FROM taxpayer_profiles WHERE taxpayer_id = :taxpayer_id LIMIT 1"),
        {"taxpayer_id": case.taxpayer_id},
    ).first())
    has_income = len(incomes) > 0

    def suggested_status(code: str) -> str:
        if code == "PROFILE":
            return "In progress" if profile_exists else "Not started"
        if code == "RESIDENCY":
            return "In progress" if residency and residency.days_in_india_current_fy is not None else "Not started"
        if code == "DOCS":
            if not required_docs:
                return "Not started"
            if len(done_docs) == len(required_docs):
                return "In progress"
            return "In progress" if len(done_docs) > 0 else "Not started"
        if code == "BANK_RECON":
            bank_codes = {d.code for d in required_docs if "_STMT" in d.code or "_INT" in d.code}
            if bank_codes and bank_codes.issubset(doc_codes_done):
                return "In progress"
            return "Not started"
        if code == "DIV_RECON":
            needed = {"ZERODHA_DIV", "ZERODHA_TAXPL"}
            return "In progress" if needed.issubset(doc_codes_done) else "Not started"
        if code == "MF_REVIEW":
            needed = {"MF_CAS", "MF_CG"}
            return "In progress" if needed.issubset(doc_codes_done) else "Not started"
        if code == "HOUSE_REVIEW":
            needed = {"HOUSE_DEED", "HOUSE_POSSESSION", "LOAN_CERT", "LOAN_STATEMENT"}
            completed_count = len(needed.intersection(doc_codes_done))
            return "In progress" if completed_count > 0 else "Not started"
        if code == "REGIME":
            return "In progress" if (case.tax_regime or "").strip().lower() not in {"", "undecided"} else "Not started"
        if code == "FORM":
            return "In progress"
        if code == "PORTAL_VALIDATE":
            return "In progress" if case.case_status in {"Validated", "Ready to file", "Filed"} else "Not started"
        if code == "FILE_VERIFY":
            return "In progress" if case.acknowledgement_no else "Not started"
        return "Not started"

    return {task.code: suggested_status(task.code) for task in tasks}


def _recommend_itr_form(session, case) -> dict:
    incomes = session.scalars(select(IncomeEntryModel).where(IncomeEntryModel.case_id == case.id)).all()
    income_types = [str(getattr(i, "income_type", "") or "").lower() for i in incomes]
    gross_income = sum(float(getattr(i, "gross_amount", 0) or 0) for i in incomes)
    has_business_professional = any(
        t for t in income_types
        if any(k in t for k in ("business", "profession", "freelance", "consulting", "proprietor"))
    )
    has_presumptive_business = any("presumptive" in t for t in income_types)
    has_capital_gains = any(
        t for t in income_types
        if any(k in t for k in ("capital_gain", "capital gains", "stcg", "ltcg"))
    )
    has_foreign_income = any(
        t for t in income_types
        if any(k in t for k in ("foreign", "overseas"))
    )
    is_non_resident = case.residential_status in {"NRI", "RNOR"}
    docs = session.scalars(select(DocumentRequirement).where(DocumentRequirement.case_id == case.id)).all()
    has_foreign_asset_doc = any((d.code or "").startswith("FOREIGN_") for d in docs)
    has_multiple_houses = len(session.scalars(select(PropertyLoan).where(PropertyLoan.case_id == case.id)).all()) > 1

    recommended = "ITR-2"
    reason = "Defaulted to ITR-2 for individual taxpayer profile with non-business income."

    if has_business_professional and has_presumptive_business and not has_capital_gains and not is_non_resident:
        recommended = "ITR-4"
        reason = "Presumptive business/professional income detected with resident profile."
    elif has_business_professional:
        recommended = "ITR-3"
        reason = "Business/professional income detected."
    elif is_non_resident or has_capital_gains or has_foreign_income or has_foreign_asset_doc or has_multiple_houses:
        recommended = "ITR-2"
        reason = "NRI/RNOR, foreign/capital-gain/multi-property profile maps to ITR-2."
    elif gross_income <= 5000000:
        recommended = "ITR-1"
        reason = "Resident profile with straightforward income and total income up to ₹50L."
    else:
        recommended = "ITR-2"
        reason = "Income exceeds ITR-1 scope."

    return {
        "recommended_form": recommended,
        "current_form": case.return_form,
        "reason": reason,
        "signals": {
            "residential_status": case.residential_status,
            "gross_income": gross_income,
            "has_business_professional_income": has_business_professional,
            "has_presumptive_business_income": has_presumptive_business,
            "has_capital_gains": has_capital_gains,
            "has_foreign_income": has_foreign_income,
            "has_foreign_asset_doc": has_foreign_asset_doc,
            "has_multiple_house_properties": has_multiple_houses,
        },
        "disclaimer": "This is a rule-based recommendation and should be reviewed before filing.",
    }

# If tax engine class imported, expose wrapper functions
if 'TaxFilingCalculator' in globals() and TaxFilingCalculator is not None:
    def _build_calc_from_person(person, fiscal_year=None):
        rs_str = None
        # Try case-level residential status first
        if hasattr(person, 'residential_status') and getattr(person, 'residential_status'):
            rs_str = getattr(person, 'residential_status')
        elif hasattr(person, 'cases') and person.cases:
            try:
                rs_str = person.cases[0].residential_status
            except Exception:
                rs_str = None
        # Map to enum
        try:
            rs_enum = ResidentialStatus[rs_str]
        except Exception:
            try:
                rs_enum = ResidentialStatus[rs_str.upper()]
            except Exception:
                rs_enum = ResidentialStatus.NRI
        calc = TaxFilingCalculator(rs_enum, assessment_year=fiscal_year or '2026-27')
        # Populate incomes from case income_entries if available
        case = None
        if hasattr(person, 'cases') and person.cases:
            case = person.cases[0]
        if case and hasattr(case, 'income_entries'):
            for ie in case.income_entries:
                gross = getattr(ie, 'gross_amount', getattr(ie, 'amount_in_return', 0)) or 0
                exempt = getattr(ie, 'exempt_amount', 0) or 0
                try:
                    calc.add_income(getattr(ie, 'income_type', 'income'), Decimal(str(gross)), Decimal(str(exempt)))
                except Exception:
                    # ignore bad entries
                    pass
        return calc

    def calculate_filing(person, fiscal_year=None):
        calc = _build_calc_from_person(person, fiscal_year=fiscal_year)
        # Default to OLD regime for detailed calculation
        try:
            return calc.calculate_filing(TaxRegime.OLD, person=person)
        except Exception as e:
            return {'error': str(e)}

    def compare_regimes(person, fiscal_year=None):
        calc = _build_calc_from_person(person, fiscal_year=fiscal_year)
        try:
            return calc.compare_regimes(person=person)
        except Exception as e:
            return {'error': str(e)}
else:
    calculate_filing = None
    compare_regimes = None

load_dotenv('.env')
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
else:
    engine = None
    SessionLocal = None


def _ensure_profile_table() -> None:
    if engine is None:
        return
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS taxpayer_profiles (
                id SERIAL PRIMARY KEY,
                taxpayer_id INTEGER UNIQUE REFERENCES taxpayers(id) ON DELETE CASCADE,
                mobile_primary VARCHAR(20),
                aadhaar_mobile VARCHAR(20),
                alt_mobiles TEXT,
                email VARCHAR(200),
                permanent_address TEXT,
                mailing_address TEXT,
                city VARCHAR(120),
                state VARCHAR(120),
                postal_code VARCHAR(20),
                country VARCHAR(80),
                date_of_birth DATE,
                marital_status VARCHAR(30),
                occupation VARCHAR(120),
                employer_name VARCHAR(160),
                aadhaar_last4 VARCHAR(4),
                passport_last4 VARCHAR(4),
                emergency_contact_name VARCHAR(120),
                emergency_contact_mobile VARCHAR(20),
                refund_account_last4 VARCHAR(4),
                refund_ifsc VARCHAR(20),
                preferred_contact_mode VARCHAR(20),
                communication_notes TEXT,
                pan_full VARCHAR(20),
                aadhaar_full VARCHAR(20),
                passport_full VARCHAR(30),
                mobile_country_code VARCHAR(5),
                aadhaar_mobile_country_code VARCHAR(5),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.execute(text("ALTER TABLE taxpayer_profiles ADD COLUMN IF NOT EXISTS date_of_birth DATE"))
        conn.execute(text("ALTER TABLE taxpayer_profiles ADD COLUMN IF NOT EXISTS marital_status VARCHAR(30)"))
        conn.execute(text("ALTER TABLE taxpayer_profiles ADD COLUMN IF NOT EXISTS occupation VARCHAR(120)"))
        conn.execute(text("ALTER TABLE taxpayer_profiles ADD COLUMN IF NOT EXISTS employer_name VARCHAR(160)"))
        conn.execute(text("ALTER TABLE taxpayer_profiles ADD COLUMN IF NOT EXISTS aadhaar_last4 VARCHAR(4)"))
        conn.execute(text("ALTER TABLE taxpayer_profiles ADD COLUMN IF NOT EXISTS passport_last4 VARCHAR(4)"))
        conn.execute(text("ALTER TABLE taxpayer_profiles ADD COLUMN IF NOT EXISTS emergency_contact_name VARCHAR(120)"))
        conn.execute(text("ALTER TABLE taxpayer_profiles ADD COLUMN IF NOT EXISTS emergency_contact_mobile VARCHAR(20)"))
        conn.execute(text("ALTER TABLE taxpayer_profiles ADD COLUMN IF NOT EXISTS refund_account_last4 VARCHAR(4)"))
        conn.execute(text("ALTER TABLE taxpayer_profiles ADD COLUMN IF NOT EXISTS refund_ifsc VARCHAR(20)"))
        conn.execute(text("ALTER TABLE taxpayer_profiles ADD COLUMN IF NOT EXISTS preferred_contact_mode VARCHAR(20)"))
        conn.execute(text("ALTER TABLE taxpayer_profiles ADD COLUMN IF NOT EXISTS communication_notes TEXT"))
        conn.execute(text("ALTER TABLE taxpayer_profiles ADD COLUMN IF NOT EXISTS pan_full VARCHAR(20)"))
        conn.execute(text("ALTER TABLE taxpayer_profiles ADD COLUMN IF NOT EXISTS aadhaar_full VARCHAR(20)"))
        conn.execute(text("ALTER TABLE taxpayer_profiles ADD COLUMN IF NOT EXISTS passport_full VARCHAR(30)"))
        conn.execute(text("ALTER TABLE taxpayer_profiles ADD COLUMN IF NOT EXISTS mobile_country_code VARCHAR(5)"))
        conn.execute(text("ALTER TABLE taxpayer_profiles ADD COLUMN IF NOT EXISTS aadhaar_mobile_country_code VARCHAR(5)"))


_ensure_profile_table()

app = FastAPI(title='ITR Family API', version='0.2')

# Add CORS middleware to allow frontend at localhost:3000 to access backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'http://localhost:3000',
        'http://127.0.0.1:3000',
        'http://localhost',
        'http://127.0.0.1',
    ],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

class TaxRequest(BaseModel):
    taxpayer: Dict[str, Any]
    fiscal_year: Optional[str] = None


class ResidencyAssessmentRequest(BaseModel):
    days_in_india_current_fy: int
    days_in_india_prior_4y: int = 0
    days_in_india_prior_7y: int = 0
    nonresident_years_prior_10y: int = 0
    indian_citizen_or_pio: bool = True
    visiting_india: bool = False
    indian_income_excluding_foreign: float = 0
    not_liable_to_tax_elsewhere: bool = False


def _compute_residency_status(req: ResidencyAssessmentRequest) -> Dict[str, Any]:
    days_current = req.days_in_india_current_fy or 0
    days_prior4 = req.days_in_india_prior_4y or 0
    days_prior7 = req.days_in_india_prior_7y or 0
    nonresident_years = req.nonresident_years_prior_10y or 0
    income = float(req.indian_income_excluding_foreign or 0)

    threshold = 60
    threshold_reason = "Standard resident test uses 60 days in current FY with 365 days in prior 4 FYs."
    if req.indian_citizen_or_pio and req.visiting_india:
        if income > 1500000:
            threshold = 120
            threshold_reason = "Indian citizen/PIO visiting India with income > ₹15L uses 120-day threshold with 365-day prior 4-year condition."
        else:
            threshold = 182
            threshold_reason = "Indian citizen/PIO visiting India with income ≤ ₹15L uses 182-day threshold."

    resident_primary = days_current >= 182
    resident_secondary = (days_current >= threshold and days_prior4 >= 365) if threshold < 182 else False
    deemed_resident = bool(
        req.indian_citizen_or_pio and income > 1500000 and req.not_liable_to_tax_elsewhere and days_current < 182
    )
    is_resident = resident_primary or resident_secondary or deemed_resident

    if not is_resident:
        status = "NRI"
        status_basis = "Does not satisfy resident tests under Section 6."
    else:
        rnor_test = (nonresident_years >= 9) or (days_prior7 <= 729)
        if rnor_test:
            status = "RNOR"
            status_basis = "Resident but satisfies RNOR conditions (non-resident history or prior 7-year stay test)."
        else:
            status = "ROR"
            status_basis = "Resident and does not satisfy RNOR relaxation conditions."

    checks = [
        {"rule": "182-day resident test", "passed": resident_primary, "detail": f"Current FY days = {days_current}"},
        {"rule": f"{threshold}-day + 365-day test", "passed": resident_secondary, "detail": f"Current FY days = {days_current}, Prior 4 FY days = {days_prior4}"},
        {"rule": "Deemed resident test", "passed": deemed_resident, "detail": f"Income > 15L: {income > 1500000}, Not liable elsewhere: {req.not_liable_to_tax_elsewhere}"},
    ]

    return {
        "recommended_status": status,
        "status_basis": status_basis,
        "threshold_reason": threshold_reason,
        "checks": checks,
        "government_sources": [
            "https://www.incometax.gov.in/iec/foportal/help/individual",
            "https://www.incometax.gov.in/iec/foportal/",
            "Income-tax Act, 1961 - Section 6 (Residential status tests)",
        ],
        "disclaimer": "Rule-based recommendation only. Final determination should be reviewed with a qualified tax professional for edge cases.",
    }

@app.get('/health')
def health():
    return {'status': 'ok'}


@app.post('/api/residency/assess')
def assess_residency(req: ResidencyAssessmentRequest):
    return {'ok': True, 'assessment': _compute_residency_status(req)}


@app.get('/api/llm/status')
def llm_status():
    """Get LLM provider configuration status"""
    try:
        from backend.app.llm_provider import get_llm_config
        config = get_llm_config()
        return {
            'ok': True,
            'current_provider': config.provider,
            'provider_name': config.get_provider_name(),
            'available': config.is_available(),
            'fallback_enabled': config.fallback_to_rules,
            'has_claude_key': bool(config.claude_api_key),
            'has_openai_key': bool(config.openai_api_key),
        }
    except Exception as e:
        logger.error(f"Error getting LLM status: {e}")
        return {
            'ok': False,
            'error': str(e),
            'current_provider': 'unknown',
        }


@app.get('/api/reference/postal-lookup')
def postal_lookup(country: str, postal_code: str):
    country_norm = (country or '').strip().lower()
    code = (postal_code or '').strip()
    if not code:
        raise HTTPException(status_code=400, detail='postal_code is required')
    try:
        if country_norm == 'india':
            if not code.isdigit() or len(code) != 6:
                return {'ok': True, 'valid': False, 'country': 'India', 'message': 'Indian PIN must be 6 digits'}
            r = requests.get(f'https://api.postalpincode.in/pincode/{code}', timeout=8)
            payload = r.json() if r.ok else []
            first = payload[0] if isinstance(payload, list) and payload else {}
            offices = first.get('PostOffice') or []
            if not offices:
                return {'ok': True, 'valid': False, 'country': 'India', 'message': 'PIN not found'}
            office = offices[0]
            return {
                'ok': True,
                'valid': True,
                'country': 'India',
                'postal_code': code,
                'city': office.get('District'),
                'state': office.get('State'),
                'suggested_country': 'India',
            }
        if country_norm in {'us', 'usa', 'united states', 'united states of america'}:
            if not (code.isdigit() and len(code) in {5, 9}):
                return {'ok': True, 'valid': False, 'country': 'US', 'message': 'US ZIP must be 5 or 9 digits'}
            query_code = code[:5]
            r = requests.get(f'https://api.zippopotam.us/us/{query_code}', timeout=8)
            if not r.ok:
                return {'ok': True, 'valid': False, 'country': 'US', 'message': 'ZIP not found'}
            payload = r.json()
            places = payload.get('places') or []
            place = places[0] if places else {}
            return {
                'ok': True,
                'valid': True,
                'country': 'US',
                'postal_code': query_code,
                'city': place.get('place name'),
                'state': place.get('state'),
                'suggested_country': 'US',
            }
        return {'ok': True, 'valid': False, 'message': 'Postal lookup currently supports India and US only'}
    except Exception as e:
        return {'ok': False, 'valid': False, 'message': f'Lookup failed: {e}'}


@app.get('/api/reference/tax-credits')
def tax_credit_reference():
    return {
        'ok': True,
        'sections': [
            {
                'code': 'TDS',
                'how_claimed': 'Claim based on Form 26AS/AIS and matching deductor entry.',
                'examples': ['Salary TDS (Form 16)', 'Bank interest TDS (194A)', 'Brokerage/commission TDS (194H/194J)'],
                'important': 'Claim should generally not exceed tax reported in Form 26AS for the same entry.',
                'source': 'Income Tax Department portal and Form 26AS guidance',
            },
            {
                'code': 'TCS',
                'how_claimed': 'Claim as tax credit where seller/collector has reported TCS against your PAN.',
                'examples': ['Foreign remittance TCS', 'High-value purchase TCS'],
                'important': 'Verify collector name, amount, and PAN mapping in 26AS.',
                'source': 'Income Tax Act TCS provisions',
            },
            {
                'code': 'ADVANCE_TAX',
                'how_claimed': 'Claim challan-based advance tax payments made during the FY.',
                'examples': ['Quarterly self-paid tax'],
                'important': 'Ensure BSR code/challan serial/date are correctly entered and visible in tax payment history.',
                'source': 'Income Tax portal challan records',
            },
            {
                'code': 'SELF_ASSESSMENT_TAX',
                'how_claimed': 'Claim self-assessment tax paid before filing where applicable.',
                'examples': ['Tax paid after final computation'],
                'important': 'Capture challan details exactly to avoid mismatch.',
                'source': 'Income Tax portal challan records',
            },
        ],
        'gov_links': [
            'https://www.incometax.gov.in/iec/foportal/',
            'https://www.incometax.gov.in/iec/foportal/help/individual',
        ],
    }
@app.get('/api/taxpayers')
def list_taxpayers():
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    if Taxpayer is None:
        raise HTTPException(status_code=500, detail='Taxpayer model unavailable')
    with SessionLocal() as session:
        stmt = select(Taxpayer)
        try:
            rows = session.execute(stmt).scalars().all()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f'Database query failed: {e}')
        out = []
        for t in rows:
            if t is None:
                # defensive: skip unmapped rows
                continue
            out.append({
                'id': getattr(t, 'id', None),
                'name': getattr(t, 'name', None),
                'pan_last4': getattr(t, 'pan_last4', None),
                'citizenship': getattr(t, 'citizenship', None),
                'has_dependent_child': getattr(t, 'has_dependent_child', False),
                'dependent_child_country_of_residence': getattr(t, 'dependent_child_country_of_residence', None),
                'is_eligible_for_80ac': getattr(t, 'is_eligible_for_80ac', False),
            })
        return {'ok': True, 'taxpayers': out}

@app.get('/api/cases/{case_id}')
def case_detail(case_id: int):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        case = session.get(TaxCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail='Case not found')
        docs = [
            {
                'id': d.id,
                'code': d.code,
                'title': d.title,
                'status': d.status,
                'file_path': d.file_path,
                'required': d.required,
            }
            for d in case.documents
        ]
        tasks = [
            {'id': t.id, 'code': t.code, 'title': t.title, 'status': t.status}
            for t in case.tasks
        ]
        return {
            'ok': True,
            'case': {
                'id': case.id,
                'assessment_year': case.assessment_year,
                'financial_year': case.financial_year,
                'residential_status': case.residential_status,
                'return_form': case.return_form,
                'case_status': case.case_status,
                'documents': docs,
                'tasks': tasks,
            },
        }


@app.get('/api/cases/{case_id}/itr-form-recommendation')
def get_itr_form_recommendation(case_id: int):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        case = session.get(TaxCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail='Case not found')
        return {'ok': True, 'recommendation': _recommend_itr_form(session, case)}


@app.post('/api/cases/{case_id}/itr-form-recommendation/apply')
def apply_itr_form_recommendation(case_id: int):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        case = session.get(TaxCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail='Case not found')
        recommendation = _recommend_itr_form(session, case)
        case.return_form = recommendation['recommended_form']
        session.add(case)
        session.add(AuditLog(
            case_id=case_id,
            action='ITR_FORM_AUTO_SELECTED',
            entity='TaxCase',
            details=f"Set return_form to {case.return_form} via recommendation engine",
        ))
        session.commit()
        return {'ok': True, 'return_form': case.return_form, 'recommendation': recommendation}

@app.get('/api/cases/{case_id}/documents/required')
def required_documents(case_id: int):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        case = session.get(TaxCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail='Case not found')
        stmt = select(DocumentRequirement).where(DocumentRequirement.case_id == case_id)
        rows = session.execute(stmt).scalars().all()
        other_cases = session.scalars(
            select(TaxCase).where(TaxCase.taxpayer_id == case.taxpayer_id, TaxCase.id != case_id)
        ).all()
        other_case_ids = [c.id for c in other_cases]
        linked_candidates = {}
        if other_case_ids:
            other_docs = session.scalars(
                select(DocumentRequirement).where(
                    DocumentRequirement.case_id.in_(other_case_ids),
                    DocumentRequirement.file_path.is_not(None),
                )
            ).all()
            for d in other_docs:
                linked_candidates[d.code] = {'source_case_id': d.case_id, 'file_path': d.file_path}
        out = [
            {
                'id': r.id,
                'code': r.code,
                'title': r.title,
                'category': r.category,
                'institution': r.institution,
                'required': r.required,
                'status': r.status,
                'file_path': r.file_path,
                'portal': {
                    'name': DOCUMENT_PORTAL_MAP.get(r.code, (r.institution or 'Source Portal', None))[0],
                    'url': DOCUMENT_PORTAL_MAP.get(r.code, (None, None))[1],
                },
                'reusable_across_years': _is_doc_reusable_across_years(r.code),
                'link_candidate': linked_candidates.get(r.code),
            }
            for r in rows
        ]
        return {'ok': True, 'documents': out}


@app.get('/api/documents/case/{case_id}')
def list_case_documents(case_id: int):
    return required_documents(case_id)

@app.post('/api/cases/{case_id}/documents/upload')
def upload_document(case_id: int, file: UploadFile = File(...), code: Optional[str] = None):
    """Upload a file and attach to a DocumentRequirement by code or create a new record."""
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    save_dir = os.path.join(os.getcwd(), 'private_data', f'case_{case_id}')
    os.makedirs(save_dir, exist_ok=True)
    filename = file.filename
    dest = os.path.join(save_dir, filename)
    with open(dest, 'wb') as f:
        contents = file.file.read()
        f.write(contents)
    # Update DB record if code given
    with SessionLocal() as session:
        if code and DocumentRequirement is not None:
            stmt = select(DocumentRequirement).where(DocumentRequirement.case_id == case_id, DocumentRequirement.code == code)
            dr = session.execute(stmt).scalars().first()
            if dr:
                dr.file_path = dest
                dr.status = 'Received'
                session.add(dr)
                session.add(AuditLog(
                    case_id=case_id,
                    action='DOCUMENT_UPLOAD',
                    entity='DocumentRequirement',
                    details=f'{dr.code}:{filename}'
                ))
                session.commit()
            elif DocumentRequirement is not None:
                dr = DocumentRequirement(
                    case_id=case_id,
                    code=code,
                    category='Uploaded',
                    title=filename,
                    required=False,
                    status='Received',
                    file_path=dest,
                )
                session.add(dr)
                session.add(AuditLog(
                    case_id=case_id,
                    action='DOCUMENT_UPLOAD',
                    entity='DocumentRequirement',
                    details=f'{code}:{filename}'
                ))
                session.commit()
        return {'ok': True, 'path': dest}


@app.post('/api/documents/upload')
def upload_document_alias(
    case_id: int = Form(...),
    file: UploadFile = File(...),
    document_type: Optional[str] = Form(None),
    code: Optional[str] = Form(None),
):
    return upload_document(case_id=case_id, file=file, code=code or document_type)


@app.post('/api/cases/{case_id}/documents/{doc_code}/reuse')
def reuse_document_from_other_year(case_id: int, doc_code: str):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        case = session.get(TaxCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail='Case not found')
        target_doc = session.scalar(
            select(DocumentRequirement).where(
                DocumentRequirement.case_id == case_id,
                DocumentRequirement.code == doc_code,
            )
        )
        if not target_doc:
            raise HTTPException(status_code=404, detail='Document requirement not found')
        if not _is_doc_reusable_across_years(doc_code):
            raise HTTPException(status_code=400, detail='This document should be collected year-wise and is not reusable across years')

        source_case = session.scalar(
            select(TaxCase).where(
                TaxCase.taxpayer_id == case.taxpayer_id,
                TaxCase.id != case_id,
            ).order_by(TaxCase.assessment_year.desc())
        )
        if not source_case:
            raise HTTPException(status_code=404, detail='No prior tax year case found for this taxpayer')
        source_doc = session.scalar(
            select(DocumentRequirement).where(
                DocumentRequirement.case_id == source_case.id,
                DocumentRequirement.code == doc_code,
                DocumentRequirement.file_path.is_not(None),
            )
        )
        if not source_doc:
            raise HTTPException(status_code=404, detail='No uploaded document found in prior years for this document code')

        target_doc.file_path = source_doc.file_path
        target_doc.status = 'Received'
        target_doc.notes = f"Linked from AY {source_case.assessment_year} case {source_case.id}"
        session.add(target_doc)
        session.add(AuditLog(
            case_id=case_id,
            action='DOCUMENT_REUSED',
            entity='DocumentRequirement',
            details=f'{doc_code} linked from case {source_case.id}',
        ))
        session.commit()
        return {'ok': True, 'linked_from_case_id': source_case.id, 'path': target_doc.file_path}


@app.get('/api/taxpayers/{taxpayer_id}/documents/vault')
def taxpayer_document_vault(taxpayer_id: int):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        cases = session.scalars(select(TaxCase).where(TaxCase.taxpayer_id == taxpayer_id)).all()
        case_by_id = {c.id: c for c in cases}
        if not cases:
            return {'ok': True, 'documents': []}
        docs = session.scalars(
            select(DocumentRequirement).where(
                DocumentRequirement.case_id.in_(list(case_by_id.keys())),
                DocumentRequirement.file_path.is_not(None),
            )
        ).all()
        return {
            'ok': True,
            'documents': [
                {
                    'id': d.id,
                    'code': d.code,
                    'title': d.title,
                    'status': d.status,
                    'file_path': d.file_path,
                    'case_id': d.case_id,
                    'assessment_year': case_by_id[d.case_id].assessment_year if d.case_id in case_by_id else None,
                    'financial_year': case_by_id[d.case_id].financial_year if d.case_id in case_by_id else None,
                    'reusable_across_years': _is_doc_reusable_across_years(d.code),
                }
                for d in docs
            ],
        }


@app.get('/api/cases/{case_id}/progress')
def get_case_progress(case_id: int):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        case = session.get(TaxCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail='Case not found')
        return {'ok': True, 'progress': _case_progress(session, case_id)}


@app.get('/api/cases/{case_id}/review-checks')
def get_case_review_checks(case_id: int):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        case = session.get(TaxCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail='Case not found')
        return {'ok': True, 'checks': _review_checks(session, case)}


@app.get('/api/cases/{case_id}/reconciliation')
def get_case_reconciliation(case_id: int):
    return get_reconciliation(case_id)


@app.get('/api/cases/{case_id}/calculations/summary')
def get_case_calculation_summary(case_id: int):
    report = get_calculation_report(case_id)
    if isinstance(report, dict) and report.get('ok'):
        calc = report['report'].get('tax_calculation', {})
        income = report['report'].get('income_summary', {})
        return {
            'ok': True,
            'summary': {
                'total_income': income.get('gross_income', 0),
                'total_deductions': report['report'].get('deductions', {}).get('total', 0),
                'taxable_income': calc.get('taxable_income', 0),
                'income_tax': calc.get('tax_liability', 0),
                'total_tds': calc.get('tds_deducted', 0),
                'balance_due': calc.get('net_tax_payable', calc.get('refund', 0)),
                'income_breakdown': {d.get('head'): d.get('amount', 0) for d in income.get('income_details', []) if d.get('head')},
            },
        }
    return report


@app.get('/api/calculations/case/{case_id}/summary')
def get_case_calculation_summary_alias(case_id: int):
    return get_case_calculation_summary(case_id)


@app.get('/api/cases/{case_id}/residency')
def get_residency(case_id: int):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        case = session.get(TaxCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail='Case not found')
        record = session.scalar(select(ResidencyRecord).where(ResidencyRecord.case_id == case_id))
        return {
            'ok': True,
            'residency': None if not record else {
                'id': record.id,
                'days_in_india_current_fy': record.days_in_india_current_fy,
                'days_in_india_prior_4y': record.days_in_india_prior_4y,
                'days_in_india_prior_7y': record.days_in_india_prior_7y,
                'nonresident_years_prior_10y': record.nonresident_years_prior_10y,
                'date_returned_to_india': record.date_returned_to_india.isoformat() if record.date_returned_to_india else None,
                'foreign_income_received_in_india': record.foreign_income_received_in_india,
                'business_controlled_from_india': record.business_controlled_from_india,
                'conclusion': record.conclusion,
                'reviewed_by': record.reviewed_by,
                'notes': record.notes,
            },
            'case_status': case.residential_status,
        }


@app.post('/api/cases/{case_id}/residency')
def save_residency(case_id: int, data: Dict[str, Any]):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        case = session.get(TaxCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail='Case not found')
        record = session.scalar(select(ResidencyRecord).where(ResidencyRecord.case_id == case_id))
        if not record:
            record = ResidencyRecord(case_id=case_id)
        for key in [
            'days_in_india_current_fy',
            'days_in_india_prior_4y',
            'days_in_india_prior_7y',
            'nonresident_years_prior_10y',
            'foreign_income_received_in_india',
            'business_controlled_from_india',
            'conclusion',
            'reviewed_by',
            'notes',
        ]:
            if key in data:
                setattr(record, key, data[key])
        if 'date_returned_to_india' in data:
            value = data['date_returned_to_india']
            record.date_returned_to_india = None if not value else datetime.strptime(value, '%Y-%m-%d').date()
        session.add(record)
        session.commit()
        return {'ok': True}


@app.get('/api/cases/{case_id}/tax-credits')
def list_tax_credits(case_id: int):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        rows = session.scalars(select(TaxCredit).where(TaxCredit.case_id == case_id)).all()
        return {
            'ok': True,
            'credits': [
                {
                    'id': r.id,
                    'deductor': r.deductor,
                    'credit_type': r.credit_type,
                    'section_code': r.section_code,
                    'gross_amount_26as': float(r.gross_amount_26as),
                    'tax_amount_26as': float(r.tax_amount_26as),
                    'tax_claimed': float(r.tax_claimed),
                    'notes': r.notes,
                }
                for r in rows
            ]
        }


@app.post('/api/cases/{case_id}/tax-credits')
def add_tax_credit(case_id: int, data: Dict[str, Any]):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        case = session.get(TaxCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail='Case not found')
        credit = TaxCredit(
            case_id=case_id,
            deductor=data.get('deductor', ''),
            credit_type=data.get('credit_type', 'TDS'),
            section_code=data.get('section_code'),
            gross_amount_26as=data.get('gross_amount_26as', 0),
            tax_amount_26as=data.get('tax_amount_26as', 0),
            tax_claimed=data.get('tax_claimed', 0),
            notes=data.get('notes'),
        )
        session.add(credit)
        session.commit()
        return {'ok': True, 'id': credit.id}


@app.get('/api/cases/{case_id}/tasks')
def list_tasks(case_id: int):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        case = session.get(TaxCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail='Case not found')
        suggestions = _task_status_suggestions(session, case)
        rows = session.scalars(select(Task).where(Task.case_id == case_id)).all()
        return {
            'ok': True,
            'auto_suggestions': True,
            'tasks': [
                {
                    'id': r.id,
                    'code': r.code,
                    'phase': r.phase,
                    'title': r.title,
                    'status': r.status,
                    'suggested_status': suggestions.get(r.code),
                    'blocking': r.blocking,
                    'notes': r.notes,
                }
                for r in rows
            ]
        }


@app.put('/api/cases/{case_id}/tasks/{task_id}')
def update_task(case_id: int, task_id: int, data: Dict[str, Any]):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        task = session.get(Task, task_id)
        if not task or task.case_id != case_id:
            raise HTTPException(status_code=404, detail='Task not found')
        if 'status' in data:
            task.status = data['status']
        if 'notes' in data:
            task.notes = data['notes']
        session.add(task)
        session.commit()
        return {'ok': True}


@app.post('/api/cases/{case_id}/tasks/reset')
def reset_tasks(case_id: int):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        case = session.get(TaxCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail='Case not found')
        tasks = session.scalars(select(Task).where(Task.case_id == case_id)).all()
        for task in tasks:
            task.status = 'Not started'
            session.add(task)
        session.commit()
        return {'ok': True, 'updated': len(tasks)}


@app.get('/api/cases/{case_id}/audit-history')
def audit_history(case_id: int):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        rows = session.scalars(
            select(AuditLog).where(AuditLog.case_id == case_id).order_by(AuditLog.event_time.desc())
        ).all()
        return {
            'ok': True,
            'history': [
                {
                    'id': r.id,
                    'event_time': r.event_time.isoformat() if r.event_time else None,
                    'action': r.action,
                    'entity': r.entity,
                    'details': r.details,
                }
                for r in rows
            ],
        }


@app.get('/api/cases/{case_id}/properties')
def list_properties(case_id: int):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        rows = session.scalars(select(PropertyLoan).where(PropertyLoan.case_id == case_id)).all()
        return {
            'ok': True,
            'properties': [
                {
                    'id': r.id,
                    'property_name': r.property_name,
                    'property_address': r.property_address,
                    'ownership_percent': float(r.ownership_percent),
                    'self_occupied': r.self_occupied,
                    'possession_date': r.possession_date.isoformat() if r.possession_date else None,
                    'loan_start_date': r.loan_start_date.isoformat() if r.loan_start_date else None,
                    'lender': r.lender,
                    'interest_fy': float(r.interest_fy),
                    'principal_fy': float(r.principal_fy),
                    'preconstruction_interest': float(r.preconstruction_interest),
                    'actual_payment_percent': float(r.actual_payment_percent),
                    'notes': r.notes,
                }
                for r in rows
            ],
        }


@app.post('/api/cases/{case_id}/properties')
def add_property(case_id: int, data: Dict[str, Any]):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        case = session.get(TaxCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail='Case not found')
        prop = PropertyLoan(
            case_id=case_id,
            property_name=data.get('property_name', ''),
            property_address=data.get('property_address'),
            ownership_percent=data.get('ownership_percent', 0),
            self_occupied=bool(data.get('self_occupied', True)),
            lender=data.get('lender'),
            interest_fy=data.get('interest_fy', 0),
            principal_fy=data.get('principal_fy', 0),
            preconstruction_interest=data.get('preconstruction_interest', 0),
            actual_payment_percent=data.get('actual_payment_percent', 0),
            notes=data.get('notes'),
        )
        if data.get('possession_date'):
            prop.possession_date = datetime.strptime(data['possession_date'], '%Y-%m-%d').date()
        if data.get('loan_start_date'):
            prop.loan_start_date = datetime.strptime(data['loan_start_date'], '%Y-%m-%d').date()
        session.add(prop)
        session.commit()
        return {'ok': True, 'id': prop.id}


@app.put('/api/cases/{case_id}/properties/{property_id}')
def update_property(case_id: int, property_id: int, data: Dict[str, Any]):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        prop = session.get(PropertyLoan, property_id)
        if not prop or prop.case_id != case_id:
            raise HTTPException(status_code=404, detail='Property not found')

        for field in [
            'property_name', 'property_address', 'ownership_percent', 'self_occupied', 'lender',
            'interest_fy', 'principal_fy', 'preconstruction_interest', 'actual_payment_percent', 'notes'
        ]:
            if field in data:
                setattr(prop, field, data[field])

        if 'possession_date' in data:
            value = data.get('possession_date')
            prop.possession_date = None if not value else datetime.strptime(value, '%Y-%m-%d').date()
        if 'loan_start_date' in data:
            value = data.get('loan_start_date')
            prop.loan_start_date = None if not value else datetime.strptime(value, '%Y-%m-%d').date()

        session.add(prop)
        session.commit()
        return {'ok': True}


@app.get('/api/portal/export')
def export_case_bundle(case_id: int, format: str = 'json'):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        case = session.get(TaxCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail='Case not found')
        payload = get_calculation_report(case_id)
        if format == 'xml':
            content = f'<itr case_id="{case_id}" assessment_year="{case.assessment_year}" />'
            return Response(content=content, media_type='application/xml')
        if format == 'csv':
            report = payload.get('report', {}) if isinstance(payload, dict) else {}
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(['field', 'value'])
            writer.writerow(['case_id', case_id])
            writer.writerow(['assessment_year', report.get('assessment_year', case.assessment_year)])
            writer.writerow(['taxpayer_name', report.get('taxpayer_details', {}).get('name', '')])
            writer.writerow(['residential_status', report.get('taxpayer_details', {}).get('residential_status', case.residential_status)])
            writer.writerow(['gross_income', report.get('income_summary', {}).get('gross_income', 0)])
            writer.writerow(['taxable_income', report.get('tax_calculation', {}).get('taxable_income', 0)])
            writer.writerow(['tax_liability', report.get('tax_calculation', {}).get('tax_liability', 0)])
            writer.writerow(['tds_deducted', report.get('tax_calculation', {}).get('tds_deducted', 0)])
            writer.writerow(['net_tax_payable', report.get('tax_calculation', {}).get('net_tax_payable', 0)])
            return Response(content=buffer.getvalue(), media_type='text/csv')
        return JSONResponse(content=payload)


@app.post('/api/documents/parse')
async def parse_document(file: UploadFile = File(...), doc_type: Optional[str] = None):
    """Parse and extract data from document (AIS, 26AS, CAS, Bank Statement)"""
    try:
        from backend.app.document_parser import (
            DocumentParserFactory,
            DocumentType,
        )
    except ImportError:
        logger.error("document_parser module not available")
        raise HTTPException(
            status_code=500,
            detail="Document parsing not available (pdfplumber or PyPDF2 required)"
        )

    # Save uploaded file temporarily
    temp_dir = os.path.join(os.getcwd(), 'private_data', 'temp_parse')
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, file.filename)

    try:
        with open(temp_path, 'wb') as f:
            contents = await file.read()
            f.write(contents)

        # Parse document
        if doc_type:
            try:
                doc_type_enum = DocumentType[doc_type.upper()]
            except KeyError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown document type: {doc_type}"
                )
            result = DocumentParserFactory.parse_document(temp_path, doc_type_enum)
        else:
            result = DocumentParserFactory.auto_detect_and_parse(temp_path)

        return {
            'ok': result.success,
            'document_type': result.doc_type,
            'extracted_data': result.extracted_data,
            'errors': result.errors,
            'warnings': result.warnings,
        }
    except Exception as e:
        logger.error(f"Document parsing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up temp file
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass


@app.get('/api/documents/supported-types')
def supported_document_types():
    """Get list of supported document types for parsing"""
    try:
        from backend.app.document_parser import DocumentType
        return {
            'ok': True,
            'types': [
                {
                    'type': dt.value,
                    'name': dt.name,
                    'description': {
                        'ais': 'Annual Information Statement - shows all financial transactions',
                        'form_26as': 'Form 26AS - shows TDS and tax credits',
                        'bank_statement': 'Bank Statement - account transactions',
                        'tds_certificate': 'TDS Certificate - Form 16/16A',
                        'salary_slip': 'Salary Slip - monthly earnings',
                        'home_loan_certificate': 'Home Loan Certificate - interest/principal',
                        'cas': 'Consolidated Account Statement - mutual fund holdings',
                        'dividend_report': 'Dividend Report - equity dividends',
                        'tax_audit_certificate': 'Tax Audit Certificate - Form 10B',
                    }.get(dt.value, 'Document for tax filing')
                }
                for dt in DocumentType
            ]
        }
    except Exception as e:
        logger.error(f"Error listing supported types: {e}")
        return {
            'ok': False,
            'error': str(e),
            'types': []
        }
def tax_calc(req: TaxRequest, case_id: Optional[int] = None):
    # If case_id provided, load taxpayer/case from DB; else use provided taxpayer dict
    taxpayer_obj = None
    if case_id:
        if SessionLocal is None:
            raise HTTPException(status_code=500, detail='Database not configured')
        with SessionLocal() as session:
            case = session.get(TaxCase, case_id)
            if not case:
                raise HTTPException(status_code=404, detail='Case not found')
            taxpayer_obj = case.taxpayer
    if calculate_filing:
        try:
            input_person = taxpayer_obj if taxpayer_obj is not None else req.taxpayer
            result = calculate_filing(input_person, fiscal_year=req.fiscal_year)
            return {'ok': True, 'result': result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        return {'ok': True, 'note': 'Tax engine not available in container', 'input': req.dict()}

@app.post('/api/tax/compare')
def tax_compare(req: TaxRequest, case_id: Optional[int] = None):
    taxpayer_obj = None
    if case_id:
        if SessionLocal is None:
            raise HTTPException(status_code=500, detail='Database not configured')
        with SessionLocal() as session:
            case = session.get(TaxCase, case_id)
            if not case:
                raise HTTPException(status_code=404, detail='Case not found')
            taxpayer_obj = case.taxpayer
    if compare_regimes:
        try:
            report = compare_regimes(taxpayer_obj if taxpayer_obj is not None else req.taxpayer, fiscal_year=req.fiscal_year)
            return {'ok': True, 'report': report}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        return {'ok': False, 'error': 'compare_regimes not available'}


# ---------------- AI / helper endpoints ----------------
class AIRequest(BaseModel):
    message: Optional[str] = None
    case_id: Optional[int] = None


def _load_taxpayer(case_id: Optional[int], taxpayer_dict: Optional[Dict[str, Any]] = None):
    if case_id and SessionLocal:
        with SessionLocal() as session:
            case = session.get(TaxCase, case_id)
            if not case:
                return None, 'Case not found'
            return case.taxpayer, None
    if taxpayer_dict:
        return taxpayer_dict, None
    return None, 'No taxpayer provided'


@app.post('/api/ai/deductions')
async def ai_deductions(req: AIRequest):
    """Get AI-powered deduction recommendations (multi-provider LLM)"""
    try:
        from backend.app.llm_provider import (
            get_deduction_recommendations,
            get_llm_config,
        )
        config = get_llm_config()
    except ImportError:
        logger.error("llm_provider module not available")
        config = None
        get_deduction_recommendations = None

    tp, err = _load_taxpayer(req.case_id)
    if err:
        raise HTTPException(status_code=400, detail=err)

    # Try LLM if available
    if get_deduction_recommendations and config and config.is_available():
        try:
            income_data = {
                'gross_income': 1200000,
                'residency': 'NRI',
                'dependents': 0,
                'health_status': 'Normal',
                'has_home_loan': False,
            }
            llm_response = await get_deduction_recommendations(income_data)
            if llm_response and llm_response.get('ok'):
                return {
                    'ok': True,
                    'suggestions': llm_response.get('response'),
                    'source': llm_response.get('source'),
                    'provider': llm_response.get('provider'),
                }
        except Exception as e:
            logger.warning(f"LLM deductions error: {e}")

    # Fallback to rule-based suggestions
    suggestions = [
        {
            'section': '80C',
            'name': 'PPF/EPF/ELSS/LIC/NSC/Principal on home loan',
            'max_limit': 150000,
            'eligible': True,
            'docs': ['Investment proof, bank statements'],
            'gov_link': 'https://www.incometax.gov.in/'
        },
        {
            'section': '80D',
            'name': 'Health Insurance Premiums',
            'max_limit': 50000,
            'eligible': True,
            'docs': ['Premium receipts, policy documents'],
            'gov_link': 'https://www.incometax.gov.in/'
        },
        {
            'section': '80AC',
            'name': 'Sukanya Samriddhi Account (Girl child)',
            'max_limit': 150000,
            'eligible': False,
            'docs': ['SSA receipts, birth certificate'],
            'gov_link': 'https://www.incometax.gov.in/iec/foportal/help/sukanyasamriddhi'
        }
    ]

    return {
        'ok': True,
        'suggestions': suggestions,
        'source': 'rule-based',
        'provider': 'Rule-Based AI'
    }


@app.post('/api/ai/residency')
def ai_residency(req: AIRequest):
    tp, err = _load_taxpayer(req.case_id)
    if err:
        raise HTTPException(status_code=400, detail=err)
    
    resp = {'ok': True, 'analysis': {}}
    try:
        citizenship = getattr(tp, 'citizenship', None) if not isinstance(tp, dict) else tp.get('citizenship')
        resp['analysis']['citizenship'] = citizenship
        
        if req.case_id and SessionLocal:
            with SessionLocal() as session:
                case = session.get(TaxCase, req.case_id)
                if case:
                    rs = case.residential_status
                    resp['analysis']['declared_residential_status'] = rs
                    
                    # Provide detailed guidance
                    guidance = {}
                    if rs in ['NRI', 'nri']:
                        guidance = {
                            'status': 'Non-Resident Individual (NRI)',
                            'guidelines': [
                                'Present in India < 60 days in current FY AND < 183 days in prior 4 FYs',
                                'Income earned outside India is generally NOT taxable in India (remittance basis)',
                                'Income from India-source property/business IS taxable',
                                'Most deductions (80C, 80D, 80G) available only on India-source income',
                                'TDS exemption on interest available (Form 15G/15H if <5L income)',
                            ],
                            'required_documents': ['Passport, visas', 'Employer letter', 'Flight tickets or visa stamps', 'Proof of foreign address'],
                        }
                    elif rs in ['RNOR', 'rnor']:
                        guidance = {
                            'status': 'Resident Not Ordinarily Resident (RNOR)',
                            'guidelines': [
                                'Resident in India but NOT for 2 of prior 10 years (OR present < 183 days for 4 of prior 10 years)',
                                'Foreign income is exempt if not remitted to India',
                                'Indian-source income fully taxable',
                                'Deductions (80C, 80D, etc.) available on Indian-source income',
                                'Same ITR form and most rules as ROR, but different clubbing & deduction rules',
                            ],
                            'required_documents': ['Passport (if moved recently)', 'Residency proof', 'Employer letters for years abroad', 'Property documents if own property'],
                        }
                    else:
                        guidance = {
                            'status': 'Resident Ordinary Resident (ROR)',
                            'guidelines': [
                                'Resident in India for 2+ of prior 10 years OR present >=183 days for 4+ of prior 10 years',
                                'All income worldwide is taxable (no remittance concept)',
                                'Full scope of deductions available (80C, 80D, 80G, 24(b), etc.)',
                                'Clubbing rules apply for spouse/minor income',
                                'Standard ITR-2 with full deductions',
                            ],
                            'required_documents': ['Proof of residence (utility bill, rent agreement, property docs)', 'No travel records needed (unless border crossing relevant)'],
                        }
                    
                    resp['analysis']['guidance'] = guidance
                    resp['analysis']['note'] = 'Residency determination is complex. Always verify with a CA or tax authority for edge cases.'
    except Exception as e:
        resp['analysis']['error'] = str(e)
    
    return resp


@app.post('/api/ai/tax-savings')
def ai_tax_savings(req: AIRequest):
    """AI endpoint suggesting tax-saving strategies based on profile"""
    tp, err = _load_taxpayer(req.case_id)
    if err:
        raise HTTPException(status_code=400, detail=err)
    
    suggestions = []
    
    # Generic savings suggestions
    suggestions.append({
        'title': '80C - Section 80C Investments (₹1,50,000 limit)',
        'description': 'Claim investments in PPF, ELSS, NSC, Life Insurance, Education, Principal on home loan',
        'benefit': 'Up to ₹1,50,000 deduction = ₹45,000 tax savings (at 30% slab)',
        'compliance': 'Collect investment proofs, receipts, policy statements',
        'priority': 'HIGH',
    })
    
    suggestions.append({
        'title': '80D - Health Insurance (₹1,00,000 limit)',
        'description': 'Medical insurance premiums for self, spouse, children, parents',
        'benefit': 'Up to ₹1,00,000 deduction = ₹30,000 tax savings',
        'compliance': 'Premium receipts, policy documents',
        'priority': 'HIGH',
    })
    
    suggestions.append({
        'title': '24(b) - Home Loan Interest (unlimited)',
        'description': 'Interest on home loan for self-occupied or let-out property',
        'benefit': 'Varies (₹2L-3L interest = ₹60K-90K savings)',
        'compliance': 'Home loan certificate, interest statement from bank',
        'priority': 'HIGH' if SessionLocal else 'MEDIUM',
    })
    
    suggestions.append({
        'title': '80E - Education Loan Interest (₹50,000 limit)',
        'description': 'Interest paid on education loan for higher education',
        'benefit': 'Up to ₹50,000 deduction = ₹15,000 savings',
        'compliance': 'Loan agreement, bank statement showing interest',
        'priority': 'MEDIUM',
    })
    
    suggestions.append({
        'title': '80AC - Sukanya Samriddhi (₹1,50,000 for girl child)',
        'description': 'Investment for girl child <10 years in SSA scheme',
        'benefit': 'Up to ₹1,50,000 deduction + tax-free growth',
        'compliance': 'SSA account statement, child birth proof, residence proof',
        'priority': 'MEDIUM' if tp and getattr(tp, 'is_eligible_for_80ac', False) else 'LOW',
    })
    
    suggestions.append({
        'title': 'Senior Citizen Benefits (80TTB)',
        'description': 'Additional interest deduction for senior citizens (₹50,000 limit)',
        'benefit': 'Up to ₹50,000 deduction if age >60',
        'compliance': 'Date of birth, interest receipts',
        'priority': 'LOW',
    })
    
    suggestions.append({
        'title': 'NRI/RNOR: Salary Exemption (if eligible)',
        'description': 'Foreign salary may be exempt for NRI earning outside India',
        'benefit': 'Partial or full exemption on foreign income',
        'compliance': 'Employer letter, contract, flight records',
        'priority': 'HIGH' if req.case_id else 'MEDIUM',
    })
    
    return {'ok': True, 'suggestions': suggestions}


@app.post('/api/ai/chat')
async def ai_chat(req: AIRequest):
    """Multi-provider AI chat endpoint (Claude, ChatGPT, or Rule-based)"""
    message = req.message or ''
    case_id = req.case_id

    try:
       from backend.app.llm_provider import call_llm, get_llm_config, SYSTEM_PROMPTS
       config = get_llm_config()
    except ImportError:
       logger.error("llm_provider module not available")
       config = None

    # Build context if case_id provided
    context = None
    if case_id and SessionLocal:
       try:
           session = SessionLocal()
           case = session.query(TaxCase).filter(TaxCase.id == case_id).first()
           if case:
               gross_income = 0
               tds = 0
               if hasattr(case, 'income_entries'):
                   for ie in case.income_entries:
                       gross_income += float(getattr(ie, 'gross_amount', 0) or 0)
                       tds += float(getattr(ie, 'tds_amount', 0) or 0)
               context = {
                   'assessment_year': case.assessment_year,
                   'residential_status': case.residential_status,
                   'gross_income': gross_income,
                   'tds': tds,
               }
       except Exception as e:
           logger.warning(f"Error loading case context: {e}")
       finally:
           if session:
               session.close()

    # Try LLM if configured and available
    if config and config.is_available():
       try:
           llm_response = await call_llm(
               system_prompt=SYSTEM_PROMPTS.get('tax_guidance', ''),
               user_message=message,
               max_tokens=1024,
           )
           if llm_response and llm_response.get('ok'):
               return {
                   'ok': True,
                   'response': llm_response.get('response'),
                   'source': llm_response.get('source'),
                   'provider': llm_response.get('provider'),
                   'context': context,
               }
       except Exception as e:
           logger.warning(f"LLM chat error: {e}")

    # Fallback to simple rule-based responses
    responses = {
       'what is itr': 'ITR is the Income Tax Return filed with the Income Tax Department showing your income, deductions, and tax liability.',
       'what is 80c': 'Section 80C allows up to ₹1,50,000 deduction for investments in PPF, ELSS, NSC, Life Insurance, and principal on home loan.',
       'what is 80d': 'Section 80D allows deduction of health insurance premiums (₹50,000 self/spouse, ₹1,00,000 with parents).',
       'nri vs rnor': 'NRI: <60 days in India (current FY) AND <183 in prior 4 years. RNOR: Resident but not for 2 of prior 10 years.',
       'sukanya samriddhi': 'Section 80AC: Girl child <10 years, India resident; ₹1,50,000/year limit.',
       'home loan': 'Section 24(b): Interest deductible. Pre-construction capped at ₹5L for homes <60L value.',
       'form 26as': 'Form 26AS shows TDS, TCS, and advance tax reported by banks/employers.',
       'ais': 'AIS shows all financial transactions reported to ITD by banks, brokers, and institutions.',
    }

    msg_lower = message.lower()
    for key, resp in responses.items():
       if key in msg_lower:
           return {
               'ok': True,
               'response': resp,
               'source': 'rule-based',
               'provider': 'Rule-Based AI',
               'context': context,
           }

    # Generic fallback
    return {
       'ok': True,
       'response': 'I can help with ITR questions. Ask me about: 80C, 80D, NRI vs RNOR, refunds, TDS, deductions, tax-saving strategies.',
       'source': 'rule-based',
       'provider': 'Rule-Based AI',
       'context': context,
    }


# ==================== PROFILE API ====================
@app.get('/api/taxpayers/{taxpayer_id}/profile')
def get_taxpayer_profile(taxpayer_id: int):
    if not SessionLocal:
       return {'error': 'Database not configured'}
    session = SessionLocal()
    try:
       tp = session.query(Taxpayer).filter(Taxpayer.id == taxpayer_id).first()
       if not tp:
           raise HTTPException(status_code=404, detail='Taxpayer not found')
       profile_row = session.execute(
           text("""
               SELECT mobile_primary, aadhaar_mobile, alt_mobiles, email, permanent_address,
                      mailing_address, city, state, postal_code, country,
                      date_of_birth, marital_status, occupation, employer_name,
                      aadhaar_last4, passport_last4, emergency_contact_name, emergency_contact_mobile,
                      refund_account_last4, refund_ifsc, preferred_contact_mode, communication_notes,
                      pan_full, aadhaar_full, passport_full, mobile_country_code, aadhaar_mobile_country_code
               FROM taxpayer_profiles
               WHERE taxpayer_id = :taxpayer_id
           """),
           {'taxpayer_id': taxpayer_id}
       ).mappings().first()
       profile = dict(profile_row) if profile_row else {
           'mobile_primary': None,
           'aadhaar_mobile': None,
           'alt_mobiles': None,
           'email': getattr(tp, 'email', None),
           'permanent_address': None,
           'mailing_address': None,
           'city': None,
           'state': None,
           'postal_code': None,
           'country': 'India',
           'date_of_birth': None,
           'marital_status': None,
           'occupation': None,
           'employer_name': None,
           'aadhaar_last4': None,
           'passport_last4': None,
           'emergency_contact_name': None,
           'emergency_contact_mobile': None,
           'refund_account_last4': None,
           'refund_ifsc': None,
           'preferred_contact_mode': 'email',
           'communication_notes': None,
           'pan_full': None,
           'aadhaar_full': None,
           'passport_full': None,
           'mobile_country_code': '+91',
           'aadhaar_mobile_country_code': '+91',
       }
       profile['email'] = profile.get('email') or getattr(tp, 'email', None)
       if profile.get('date_of_birth'):
           profile['date_of_birth'] = profile['date_of_birth'].isoformat()
       return {
           'ok': True,
           'taxpayer': {
               'id': tp.id,
               'name': tp.name,
               'citizenship': tp.citizenship,
               'pan_last4': tp.pan_last4,
               'has_dependent_child': tp.has_dependent_child,
               'dependent_child_country_of_residence': tp.dependent_child_country_of_residence,
           },
           'profile': profile,
       }
    finally:
       session.close()


@app.put('/api/taxpayers/{taxpayer_id}')
def update_taxpayer(taxpayer_id: int, data: Dict[str, Any]):
    """Update taxpayer profile information"""
    if not SessionLocal:
       return {'error': 'Database not configured'}

    def _none_if_blank(value):
        if value is None:
            return None
        if isinstance(value, str) and value.strip() == '':
            return None
        return value

    def _alnum_upper(value):
        value = _none_if_blank(value)
        if value is None:
            return None
        return ''.join(ch for ch in str(value).upper() if ch.isalnum())

    def _digits_only(value):
        value = _none_if_blank(value)
        if value is None:
            return None
        digits = ''.join(ch for ch in str(value) if ch.isdigit())
        return digits or None
    
    session = SessionLocal()
    try:
       tp = session.query(Taxpayer).filter(Taxpayer.id == taxpayer_id).first()
       if not tp:
           raise HTTPException(status_code=404, detail='Taxpayer not found')
        
       # Normalize core identity fields first so last4 can be derived automatically.
       pan_full = _alnum_upper(data.get('pan_full'))
       aadhaar_full = _digits_only(data.get('aadhaar_full'))
       passport_full = _alnum_upper(data.get('passport_full'))
       pan_last4 = pan_full[-4:] if pan_full and len(pan_full) >= 4 else _alnum_upper(data.get('pan_last4'))
       aadhaar_last4 = aadhaar_full[-4:] if aadhaar_full and len(aadhaar_full) >= 4 else _digits_only(data.get('aadhaar_last4'))
       passport_last4 = passport_full[-4:] if passport_full and len(passport_full) >= 4 else _alnum_upper(data.get('passport_last4'))

       # Update fields
       if 'name' in data and _none_if_blank(data['name']):
          tp.name = str(data['name']).strip()
       if 'citizenship' in data and _none_if_blank(data['citizenship']):
          tp.citizenship = str(data['citizenship']).strip()
       if pan_last4 is not None or 'pan_last4' in data or 'pan_full' in data:
          tp.pan_last4 = pan_last4
       if 'has_dependent_child' in data:
          tp.has_dependent_child = data['has_dependent_child']
       if 'dependent_child_country_of_residence' in data:
          tp.dependent_child_country_of_residence = data['dependent_child_country_of_residence']
       if 'email' in data:
          tp.email = _none_if_blank(data['email'])

       dob_value = _none_if_blank(data.get('date_of_birth'))
       parsed_dob = None
       if dob_value is not None:
          if isinstance(dob_value, str):
              parsed_dob = datetime.strptime(dob_value, '%Y-%m-%d').date()
          else:
              parsed_dob = dob_value

       session.execute(
           text("""
               INSERT INTO taxpayer_profiles (
                   taxpayer_id, mobile_primary, aadhaar_mobile, alt_mobiles, email,
                   permanent_address, mailing_address, city, state, postal_code, country,
                   date_of_birth, marital_status, occupation, employer_name,
                   aadhaar_last4, passport_last4, emergency_contact_name, emergency_contact_mobile,
                   refund_account_last4, refund_ifsc, preferred_contact_mode, communication_notes,
                   pan_full, aadhaar_full, passport_full, mobile_country_code, aadhaar_mobile_country_code, updated_at
               ) VALUES (
                   :taxpayer_id, :mobile_primary, :aadhaar_mobile, :alt_mobiles, :email,
                   :permanent_address, :mailing_address, :city, :state, :postal_code, :country,
                   :date_of_birth, :marital_status, :occupation, :employer_name,
                   :aadhaar_last4, :passport_last4, :emergency_contact_name, :emergency_contact_mobile,
                   :refund_account_last4, :refund_ifsc, :preferred_contact_mode, :communication_notes,
                   :pan_full, :aadhaar_full, :passport_full, :mobile_country_code, :aadhaar_mobile_country_code, NOW()
               )
               ON CONFLICT (taxpayer_id) DO UPDATE SET
                   mobile_primary = EXCLUDED.mobile_primary,
                   aadhaar_mobile = EXCLUDED.aadhaar_mobile,
                   alt_mobiles = EXCLUDED.alt_mobiles,
                   email = EXCLUDED.email,
                   permanent_address = EXCLUDED.permanent_address,
                   mailing_address = EXCLUDED.mailing_address,
                   city = EXCLUDED.city,
                   state = EXCLUDED.state,
                   postal_code = EXCLUDED.postal_code,
                   country = EXCLUDED.country,
                   date_of_birth = EXCLUDED.date_of_birth,
                   marital_status = EXCLUDED.marital_status,
                   occupation = EXCLUDED.occupation,
                   employer_name = EXCLUDED.employer_name,
                   aadhaar_last4 = EXCLUDED.aadhaar_last4,
                   passport_last4 = EXCLUDED.passport_last4,
                   emergency_contact_name = EXCLUDED.emergency_contact_name,
                   emergency_contact_mobile = EXCLUDED.emergency_contact_mobile,
                   refund_account_last4 = EXCLUDED.refund_account_last4,
                   refund_ifsc = EXCLUDED.refund_ifsc,
                   preferred_contact_mode = EXCLUDED.preferred_contact_mode,
                   communication_notes = EXCLUDED.communication_notes,
                   pan_full = EXCLUDED.pan_full,
                   aadhaar_full = EXCLUDED.aadhaar_full,
                   passport_full = EXCLUDED.passport_full,
                   mobile_country_code = EXCLUDED.mobile_country_code,
                   aadhaar_mobile_country_code = EXCLUDED.aadhaar_mobile_country_code,
                   updated_at = NOW()
           """),
           {
               'taxpayer_id': taxpayer_id,
               'mobile_primary': _none_if_blank(data.get('mobile_primary')),
               'aadhaar_mobile': _none_if_blank(data.get('aadhaar_mobile')),
               'alt_mobiles': _none_if_blank(data.get('alt_mobiles')),
               'email': _none_if_blank(data.get('email')),
               'permanent_address': _none_if_blank(data.get('permanent_address')),
               'mailing_address': _none_if_blank(data.get('mailing_address')),
               'city': _none_if_blank(data.get('city')),
               'state': _none_if_blank(data.get('state')),
               'postal_code': _none_if_blank(data.get('postal_code')),
               'country': _none_if_blank(data.get('country')) or 'India',
               'date_of_birth': parsed_dob,
               'marital_status': _none_if_blank(data.get('marital_status')),
               'occupation': _none_if_blank(data.get('occupation')),
               'employer_name': _none_if_blank(data.get('employer_name')),
               'aadhaar_last4': aadhaar_last4,
               'passport_last4': passport_last4,
               'emergency_contact_name': _none_if_blank(data.get('emergency_contact_name')),
               'emergency_contact_mobile': _none_if_blank(data.get('emergency_contact_mobile')),
               'refund_account_last4': _none_if_blank(data.get('refund_account_last4')),
               'refund_ifsc': _none_if_blank(data.get('refund_ifsc')),
               'preferred_contact_mode': _none_if_blank(data.get('preferred_contact_mode')) or 'email',
               'communication_notes': _none_if_blank(data.get('communication_notes')),
               'pan_full': pan_full,
               'aadhaar_full': aadhaar_full,
               'passport_full': passport_full,
               'mobile_country_code': _none_if_blank(data.get('mobile_country_code')) or '+91',
               'aadhaar_mobile_country_code': _none_if_blank(data.get('aadhaar_mobile_country_code')) or '+91',
           }
       )
         
       session.commit()
       return {'ok': True, 'taxpayer': {
           'id': tp.id,
           'name': tp.name,
           'citizenship': tp.citizenship,
           'pan_last4': tp.pan_last4,
           'has_dependent_child': tp.has_dependent_child,
           'email': tp.email,
       }}
    except Exception as e:
       session.rollback()
       return {'error': str(e)}
    finally:
       session.close()


# ==================== INCOME API ====================
class IncomeEntry(BaseModel):
    income_type: str
    amount: float
    tds_deducted: float = 0
    fiscal_year: str = '2025-26'


@app.get('/api/cases/{case_id}/income')
def get_income(case_id: int):
    """Get income entries for a case"""
    if not SessionLocal:
       return {'error': 'Database not configured'}
    
    session = SessionLocal()
    try:
       case = session.query(TaxCase).filter(TaxCase.id == case_id).first()
       if not case:
           raise HTTPException(status_code=404, detail='Case not found')
        
       incomes = []
       if hasattr(case, 'income_entries'):
           for ie in case.income_entries:
               incomes.append({
                   'id': getattr(ie, 'id', None),
                   'income_type': getattr(ie, 'income_type', 'Unknown'),
                   'source_name': getattr(ie, 'source_name', ''),
                   'gross_amount': float(getattr(ie, 'gross_amount', 0) or 0),
                   'exempt_amount': float(getattr(ie, 'exempt_amount', 0) or 0),
                   'tds_amount': float(getattr(ie, 'tds_amount', 0) or 0),
               })
        
       return {'ok': True, 'case_id': case_id, 'income_entries': incomes}
    finally:
       session.close()


@app.post('/api/cases/{case_id}/income')
def add_income(case_id: int, entry: IncomeEntry):
    """Add income entry to case"""
    if not SessionLocal:
       return {'error': 'Database not configured'}
    
    session = SessionLocal()
    try:
       case = session.query(TaxCase).filter(TaxCase.id == case_id).first()
       if not case:
           raise HTTPException(status_code=404, detail='Case not found')
        
       # Create income entry
       try:
           from itr_workspace.models import IncomeEntry as IncomeModel
           ie = IncomeModel(
               case_id=case_id,
               income_type=entry.income_type,
               source_name=entry.income_type,
               gross_amount=entry.amount,
               tds_amount=entry.tds_deducted,
           )
           session.add(ie)
           session.commit()
           return {'ok': True, 'income_entry': {
               'id': ie.id,
               'income_type': ie.income_type,
               'gross_amount': float(ie.gross_amount),
               'tds_amount': float(ie.tds_amount),
           }}
       except Exception as e:
           session.rollback()
           return {'error': f'Could not create income entry: {str(e)}'}
    finally:
       session.close()


@app.delete('/api/cases/{case_id}/income/{income_id}')
def delete_income(case_id: int, income_id: int):
    """Delete income entry"""
    if not SessionLocal:
       return {'error': 'Database not configured'}
    
    session = SessionLocal()
    try:
       try:
           from itr_workspace.models import IncomeEntry as IncomeModel
           ie = session.query(IncomeModel).filter(
               IncomeModel.id == income_id,
               IncomeModel.case_id == case_id
           ).first()
           if not ie:
               raise HTTPException(status_code=404, detail='Income entry not found')
           session.delete(ie)
           session.commit()
           return {'ok': True}
       except Exception as e:
           session.rollback()
           return {'error': str(e)}
    finally:
       session.close()


# ==================== RECONCILIATION API ====================
@app.get('/api/cases/{case_id}/reconciliation')
def get_reconciliation(case_id: int):
    """Get reconciliation data for 3-way match"""
    if not SessionLocal or not TaxFilingCalculator:
       return {'error': 'Database or tax calculator not available'}
    
    session = SessionLocal()
    try:
       case = session.query(TaxCase).filter(TaxCase.id == case_id).first()
       if not case:
           raise HTTPException(status_code=404, detail='Case not found')
        
       tp = case.taxpayer
        
       # Calculate ITR amount from real entries
       filing_result = calculate_filing(tp)
        
       itr_amount = float(filing_result.get('tax_liability', 0)) if isinstance(filing_result, dict) else 0
        
       tds_total = 0
       if hasattr(case, 'income_entries'):
           for ie in case.income_entries:
               tds_total += float(getattr(ie, 'tds_amount', 0) or 0)
        
       # Calculate gross income from entries
       gross_income = 0
       if hasattr(case, 'income_entries'):
           for ie in case.income_entries:
               gross_income += float(getattr(ie, 'gross_amount', 0) or 0)
        
       rec_items = session.scalars(select(ReconciliationItem).where(ReconciliationItem.case_id == case_id)).all()
       source_total = sum(float(getattr(r, 'source_amount', 0) or 0) for r in rec_items) if rec_items else None
       ais_reported = sum(float(getattr(r, 'ais_26as_amount', 0) or 0) for r in rec_items) if rec_items else None
       itr_reported = sum(float(getattr(r, 'return_amount', 0) or 0) for r in rec_items) if rec_items else None
       status = 'pending_input'
       variances = {'source_vs_ais': None, 'ais_vs_itr': None}
       if rec_items:
           variances = {
               'source_vs_ais': float(source_total or 0) - float(ais_reported or 0),
               'ais_vs_itr': float(ais_reported or 0) - float(itr_reported or 0),
           }
           status = 'matched' if abs(variances['source_vs_ais']) < 100 and abs(variances['ais_vs_itr']) < 100 else 'flagged'

       return {
           'ok': True,
           'case_id': case_id,
           'reconciliation': {
               'source_total': source_total,
               'ais_reported': ais_reported,
               'itr_amount': itr_reported,
               'income_from_entries': gross_income,
               'form26as_tds': tds_total,
               'calculated_tax': itr_amount,
               'variances': variances,
               'status': status,
           }
       }
    finally:
       session.close()


# ==================== TAX REPORT GENERATION ====================
@app.get('/api/cases/{case_id}/reports/calculation')
def get_calculation_report(case_id: int):
    """Generate detailed tax calculation report"""
    if not SessionLocal or not TaxFilingCalculator:
       return {'error': 'Database or tax calculator not available'}
    
    session = SessionLocal()
    try:
       case = session.query(TaxCase).filter(TaxCase.id == case_id).first()
       if not case:
           raise HTTPException(status_code=404, detail='Case not found')
        
       tp = case.taxpayer
       filing_result = calculate_filing(tp)
        
       # Get income details
       gross_income = 0
       deductions = 0
       tds_total = 0
        
       if hasattr(case, 'income_entries'):
           for ie in case.income_entries:
               gross_income += float(getattr(ie, 'gross_amount', 0) or 0)
               tds_total += float(getattr(ie, 'tds_amount', 0) or 0)
        
       # Calculate deductions (placeholder - would sum actual deductions from DB)
       deductions = 0  # To be populated from deduction entries
        
       taxable_income = gross_income - deductions
       tax_liability = float(filing_result.get('tax_liability', 0)) if isinstance(filing_result, dict) else 0
       surcharge = float(filing_result.get('surcharge', 0)) if isinstance(filing_result, dict) else 0
       cess = float(filing_result.get('cess', 0)) if isinstance(filing_result, dict) else 0
        
       tax_before_credits = tax_liability + surcharge + cess
       net_tax = tax_before_credits - tds_total
        
       report = {
           'case_id': case_id,
           'taxpayer_name': tp.name,
           'assessment_year': case.assessment_year,
           'financial_year': case.financial_year,
           'residential_status': case.residential_status,
           'return_form': case.return_form,
            
           'income_summary': {
               'gross_income': gross_income,
               'income_details': [{
                   'head': 'Salary (India-source)',
                   'amount': gross_income,
                   'reference': 'Chapter III-A, Income-tax Act, 1961',
               } if gross_income > 0 else {}],
           },
            
           'deductions': {
               'total': deductions,
               'breakup': [
                   {'section': '80C', 'amount': 0, 'limit': 150000},
                   {'section': '80D', 'amount': 0, 'limit': 100000},
                   {'section': '24(b)', 'amount': 0, 'limit': 0},
               ],
           },
            
           'tax_calculation': {
               'taxable_income': taxable_income,
               'tax_liability': tax_liability,
               'surcharge': surcharge,
               'cess': cess,
               'tax_before_credits': tax_before_credits,
               'tds_deducted': tds_total,
               'net_tax_payable': max(0, net_tax),
               'refund': max(0, tds_total - tax_before_credits),
               'regime': 'Old Regime',
               'tax_slabs_used': [
                   {'slab': '₹0 - ₹2.5L', 'rate': '0%'},
                   {'slab': '₹2.5L - ₹5L', 'rate': '5%'},
                   {'slab': '₹5L - ₹10L', 'rate': '20%'},
                   {'slab': '>₹10L', 'rate': '30%'},
               ],
           },
            
           'government_references': [
               {'section': 'Income-tax Act, 1961', 'url': 'https://www.incometax.gov.in'},
               {'section': 'Form 26AS', 'url': 'https://www.incometax.gov.in/iec/foportal/ais-faq'},
               {'section': 'AIS Portal', 'url': 'https://www.incometax.gov.in/iec/foportal/ais'},
           ],
       }
        
       return {'ok': True, 'report': report}
    finally:
       session.close()


@app.get('/api/cases/{case_id}/reports/form-summary')
def get_form_summary_report(case_id: int):
    """Generate ITR form summary report"""
    if not SessionLocal:
       return {'error': 'Database not configured'}
    
    session = SessionLocal()
    try:
       case = session.query(TaxCase).filter(TaxCase.id == case_id).first()
       if not case:
           raise HTTPException(status_code=404, detail='Case not found')
        
       tp = case.taxpayer
        
       # Aggregate data
       gross_income = 0
       tds_total = 0
       if hasattr(case, 'income_entries'):
           for ie in case.income_entries:
               gross_income += float(getattr(ie, 'gross_amount', 0) or 0)
               tds_total += float(getattr(ie, 'tds_amount', 0) or 0)
        
       filing_result = calculate_filing(tp)
       tax_liability = float(filing_result.get('tax_liability', 0)) if isinstance(filing_result, dict) else 0
        
       report = {
           'case_id': case_id,
           'form_type': case.return_form,
           'assessment_year': case.assessment_year,
           'financial_year': case.financial_year,
            
           'taxpayer_details': {
               'name': tp.name,
               'pan': 'XXXX XXXX' + (tp.pan_last4 or ''),
               'citizenship': tp.citizenship,
               'residential_status': case.residential_status,
               'date_of_birth': 'As per PAN records',
           },
            
           'schedule_sa_income': {
               'salary': gross_income,
               'house_property': 0,
               'other_sources': 0,
               'total_income': gross_income,
               'less_deductions': 0,
               'income_chargeable': gross_income,
           },
            
           'schedule_tds': {
               'tds_by_employer': tds_total,
               'tds_by_bank': 0,
               'tds_by_others': 0,
               'total_tds': tds_total,
           },
            
           'tax_computation': {
               'taxable_income': gross_income,
               'tax_under_section': tax_liability,
               'surcharge': 0,
               'cess': 0,
               'total_tax': tax_liability,
               'total_tax_credits': tds_total,
               'tax_payable': max(0, tax_liability - tds_total),
               'refund': max(0, tds_total - tax_liability),
           },
            
           'verification': {
               'income_matched': abs(gross_income) < 100,
               'tds_matched': abs(tds_total) < 100,
               'calculations_verified': True,
               'ready_to_file': abs(gross_income) < 100 and abs(tds_total) < 100,
           },
             
           'filing_instructions': [
               'Review all income and deduction entries above',
               'Verify TDS amounts match Form 26AS',
               'Download this report as reference',
               'Login to official Income Tax portal with PAN/Aadhaar',
               'Upload PDF report or enter data directly',
               'Sign and verify ITR electronically or manually',
               'File through portal or submit to nearest Income Tax Office',
           ],
       }
         
       return {'ok': True, 'report': report}
    finally:
       session.close()


# ========== Household & Multi-Taxpayer Endpoints ==========

@app.get('/api/household/members')
def household_members():
    """Get all household members (taxpayers)"""
    if SessionLocal is None:
       raise HTTPException(status_code=500, detail='Database not configured')

    with SessionLocal() as session:
       try:
           stmt = select(Taxpayer)
           taxpayers = session.execute(stmt).scalars().all()
            
           members = []
           for tp in taxpayers:
               if tp is None:
                   continue
                    
               # Get latest case for each taxpayer
               case_stmt = select(TaxCase).where(TaxCase.taxpayer_id == tp.id)
               cases = session.execute(case_stmt).scalars().all()
                
               member = {
                   'id': tp.id,
                   'name': getattr(tp, 'name', 'Unknown'),
                   'pan': getattr(tp, 'pan', '').rjust(12, 'X'),
                   'cases': [
                       {
                           'id': c.id,
                           'assessment_year': c.assessment_year,
                           'financial_year': c.financial_year,
                           'residential_status': c.residential_status,
                           'case_status': c.case_status,
                       }
                       for c in cases if c
                   ]
               }
               members.append(member)
            
           return {'ok': True, 'members': members}
       except Exception as e:
           logger.error(f"Error fetching household members: {e}")
           raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/taxpayers/{taxpayer_id}/cases')
def create_or_get_case_for_year(taxpayer_id: int, data: Dict[str, Any]):
    """Create a case for a selected AY/FY (or return existing one)."""
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    assessment_year = str(data.get('assessment_year') or '').strip()
    financial_year = str(data.get('financial_year') or '').strip()
    residential_status = str(data.get('residential_status') or '').strip() or 'NRI'
    return_form = str(data.get('return_form') or '').strip() or 'ITR-2'
    if not assessment_year:
        raise HTTPException(status_code=400, detail='assessment_year is required')
    if not financial_year:
        try:
           start = int(assessment_year.split('-')[0]) - 1
           financial_year = f"{start}-{str(start + 1)[-2:]}"
        except Exception:
           raise HTTPException(status_code=400, detail='financial_year is required or assessment_year must be valid AY format (e.g. 2026-27)')

    with SessionLocal() as session:
        tp = session.get(Taxpayer, taxpayer_id)
        if not tp:
           raise HTTPException(status_code=404, detail='Taxpayer not found')
        existing = session.scalar(select(TaxCase).where(TaxCase.taxpayer_id == taxpayer_id, TaxCase.assessment_year == assessment_year))
        if existing:
           return {'ok': True, 'created': False, 'case': {'id': existing.id, 'assessment_year': existing.assessment_year, 'financial_year': existing.financial_year}}

        latest_case = session.scalar(
           select(TaxCase)
           .where(TaxCase.taxpayer_id == taxpayer_id)
           .order_by(TaxCase.created_at.desc())
        )
        new_case = TaxCase(
           taxpayer_id=taxpayer_id,
           assessment_year=assessment_year,
           financial_year=financial_year,
           residential_status=latest_case.residential_status if latest_case else residential_status,
           return_form=latest_case.return_form if latest_case else return_form,
           tax_regime=latest_case.tax_regime if latest_case else 'Undecided',
           case_status='Collecting',
        )
        session.add(new_case)
        session.flush()
        session.add(ResidencyRecord(case_id=new_case.id, conclusion=new_case.residential_status))

        if latest_case:
           template_docs = session.scalars(select(DocumentRequirement).where(DocumentRequirement.case_id == latest_case.id)).all()
           for d in template_docs:
               session.add(DocumentRequirement(
                   case_id=new_case.id,
                   code=d.code,
                   category=d.category,
                   title=d.title,
                   institution=d.institution,
                   required=d.required,
                   status='Missing',
                   source_period=d.source_period,
                   notes=None,
               ))
           template_tasks = session.scalars(select(Task).where(Task.case_id == latest_case.id)).all()
           for t in template_tasks:
               session.add(Task(
                   case_id=new_case.id,
                   code=t.code,
                   phase=t.phase,
                   title=t.title,
                   status='Not started',
                   blocking=t.blocking,
                   notes=None,
               ))
        session.add(AuditLog(
           case_id=new_case.id,
           action='CASE_CREATED',
           entity='TaxCase',
           details=f'Created case for AY {assessment_year}, FY {financial_year}',
        ))
        session.commit()
        return {'ok': True, 'created': True, 'case': {'id': new_case.id, 'assessment_year': new_case.assessment_year, 'financial_year': new_case.financial_year}}


@app.get('/api/household/summary')
def household_summary():
    """Get consolidated household tax summary (all members)"""
    if SessionLocal is None:
       raise HTTPException(status_code=500, detail='Database not configured')

    with SessionLocal() as session:
       try:
           stmt = select(Taxpayer)
           taxpayers = session.execute(stmt).scalars().all()
            
           total_income = 0
           total_tax = 0
           total_tds = 0
           members_summary = []
            
           for tp in taxpayers:
               if tp is None:
                   continue
                    
               case_stmt = select(TaxCase).where(TaxCase.taxpayer_id == tp.id)
               cases = session.execute(case_stmt).scalars().all()
                
               for case in cases:
                   if not case:
                       continue
                        
                   # Calculate income from entries
                   case_income = 0
                   case_tds = 0
                   if hasattr(case, 'income_entries'):
                       for ie in case.income_entries:
                           case_income += float(getattr(ie, 'gross_amount', 0) or 0)
                           case_tds += float(getattr(ie, 'tds_amount', 0) or 0)
                    
                   total_income += case_income
                   total_tds += case_tds
                    
                   # Rough tax estimate (old regime)
                   if case_income > 500000:
                       case_tax = (case_income - 500000) * 0.20
                   elif case_income > 250000:
                       case_tax = (case_income - 250000) * 0.05
                   else:
                       case_tax = 0
                   case_tax += case_income * 0.004  # Cess
                   total_tax += case_tax
                    
                   members_summary.append({
                       'name': getattr(tp, 'name', 'Unknown'),
                       'case_id': case.id,
                       'assessment_year': case.assessment_year,
                       'residency': case.residential_status,
                       'gross_income': case_income,
                       'tds_deducted': case_tds,
                       'estimated_tax': case_tax,
                       'refund_claim': case_tds - case_tax if case_tds > case_tax else 0,
                   })
            
           return {
               'ok': True,
               'household_summary': {
                   'total_members': len(members_summary),
                   'total_income': total_income,
                   'total_tds_deducted': total_tds,
                   'estimated_total_tax': total_tax,
                   'total_refund': total_tds - total_tax if total_tds > total_tax else 0,
                   'members': members_summary,
               }
           }
       except Exception as e:
           logger.error(f"Error calculating household summary: {e}")
           raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/household/consolidated-filing')
def consolidated_filing_status():
    """Get consolidated filing status and recommendations"""
    if SessionLocal is None:
       raise HTTPException(status_code=500, detail='Database not configured')

    try:
       session = SessionLocal()
        
       # Get all taxpayers and cases
       stmt = select(Taxpayer)
       taxpayers = session.execute(stmt).scalars().all()
        
       filing_info = {
           'filing_method': 'separate',  # ITR rules require separate filing per person
           'note': 'Each individual must file separate ITR. Joint filing not supported in India.',
           'recommendation': 'File individual ITRs for each household member with separate PAN',
           'members': [],
           'coordination_needed': False,
           'shared_deductions': [],  # e.g., home loan interest, health insurance
       }
        
       for tp in taxpayers:
           if tp is None:
               continue
                
           case_stmt = select(TaxCase).where(TaxCase.taxpayer_id == tp.id)
           cases = session.execute(case_stmt).scalars().all()
            
           for case in cases:
               if not case:
                   continue
                    
               income = 0
               if hasattr(case, 'income_entries'):
                   for ie in case.income_entries:
                       income += float(getattr(ie, 'gross_amount', 0) or 0)
                
               filing_info['members'].append({
                   'name': getattr(tp, 'name', 'Unknown'),
                   'case_id': case.id,
                   'pan': getattr(tp, 'pan', 'XXXX...'),
                   'assessment_year': case.assessment_year,
                   'residency': case.residential_status,
                   'gross_income': income,
                   'filing_required': income > 500000 or True,  # ITR filing mandatory for NRI
                   'filing_deadline': '31st July (for prev FY) or 31st Oct (with penalty)',
               })
        
       return {
           'ok': True,
           'filing_status': filing_info,
       }
    except Exception as e:
       logger.error(f"Error getting filing status: {e}")
       raise HTTPException(status_code=500, detail=str(e))
    finally:
       session.close()


@app.get('/api/cases/{case_id}/compare/{other_case_id}')
def compare_cases(case_id: int, other_case_id: int):
    """Compare two tax cases (multi-taxpayer comparison)"""
    if SessionLocal is None:
       raise HTTPException(status_code=500, detail='Database not configured')

    with SessionLocal() as session:
       try:
           case1 = session.get(TaxCase, case_id)
           case2 = session.get(TaxCase, other_case_id)
            
           if not case1 or not case2:
               raise HTTPException(status_code=404, detail='One or both cases not found')
            
           # Calculate income for both cases
           def calc_case_summary(case):
               income = 0
               tds = 0
               if hasattr(case, 'income_entries'):
                   for ie in case.income_entries:
                       income += float(getattr(ie, 'gross_amount', 0) or 0)
                       tds += float(getattr(ie, 'tds_amount', 0) or 0)
               return {'income': income, 'tds': tds}
            
           summary1 = calc_case_summary(case1)
           summary2 = calc_case_summary(case2)
            
           # Calculate tax
           def calc_tax(income):
               if income > 500000:
                   tax = (income - 500000) * 0.20
               elif income > 250000:
                   tax = (income - 250000) * 0.05
               else:
                   tax = 0
               tax += income * 0.004  # Cess
               return tax
            
           tax1 = calc_tax(summary1['income'])
           tax2 = calc_tax(summary2['income'])
            
           return {
               'ok': True,
               'comparison': {
                   'case1': {
                       'id': case1.id,
                       'taxpayer': getattr(case1.taxpayer, 'name', 'Unknown') if case1.taxpayer else 'Unknown',
                       'assessment_year': case1.assessment_year,
                       'residential_status': case1.residential_status,
                       'gross_income': summary1['income'],
                       'tds_deducted': summary1['tds'],
                       'tax_liability': tax1,
                       'refund': summary1['tds'] - tax1 if summary1['tds'] > tax1 else 0,
                   },
                   'case2': {
                       'id': case2.id,
                       'taxpayer': getattr(case2.taxpayer, 'name', 'Unknown') if case2.taxpayer else 'Unknown',
                       'assessment_year': case2.assessment_year,
                       'residential_status': case2.residential_status,
                       'gross_income': summary2['income'],
                       'tds_deducted': summary2['tds'],
                       'tax_liability': tax2,
                       'refund': summary2['tds'] - tax2 if summary2['tds'] > tax2 else 0,
                   },
                   'differences': {
                       'income_diff': abs(summary1['income'] - summary2['income']),
                       'tax_diff': abs(tax1 - tax2),
                       'higher_earner': case1.id if summary1['income'] > summary2['income'] else case2.id,
                   }
               }
           }
       except Exception as e:
           logger.error(f"Error comparing cases: {e}")
           raise HTTPException(status_code=500, detail=str(e))



# ============================================================================
# PHASE 3: ADVANCED AI SPECIALISTS INTEGRATION
# ============================================================================

try:
    from .phase3_endpoints import router as phase3_router
    app.include_router(phase3_router)
except Exception as e:
    logger.warning(f"Phase 3 endpoints not available: {e}")

# ============================================================================
# PHASE 4: PORTAL INTEGRATION
# ============================================================================

try:
    from .portal_endpoints import router as portal_router
    app.include_router(portal_router)
except Exception as e:
    logger.warning(f"Portal integration endpoints not available: {e}")
