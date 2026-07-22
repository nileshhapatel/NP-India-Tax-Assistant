from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse, Response, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, Optional, List
from decimal import Decimal
import os
import csv
import io
import mimetypes
from datetime import datetime, date, timedelta
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
        DocumentEvidence,
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
    DocumentEvidence = None
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


def _looks_like_filename(value: Optional[str]) -> bool:
    if not value:
        return False
    lowered = value.strip().lower()
    return any(lowered.endswith(ext) for ext in (".pdf", ".png", ".jpg", ".jpeg", ".csv", ".json", ".xlsx", ".xls", ".zip"))


def _checklist_display_title(doc) -> str:
    raw = (doc.title or "").strip()
    if raw and not _looks_like_filename(raw):
        return raw
    code = (doc.code or "DOCUMENT").strip()
    institution = (doc.institution or "").strip()
    if institution:
        return f"{institution} - {code}"
    return code.replace("_", " ").title()


def _parse_not_applicable_reason(notes: Optional[str]) -> Optional[str]:
    text_value = (notes or "").strip()
    prefix = "Not applicable:"
    if text_value.lower().startswith(prefix.lower()):
        return text_value[len(prefix):].strip() or None
    return None


def _to_amount(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    text_value = str(value).replace(",", "").replace("₹", "").strip()
    if not text_value:
        return 0.0
    try:
        return float(text_value)
    except ValueError:
        return 0.0


def _deduplicate_draft_entries(entries: List[Dict]) -> List[Dict]:
    """
    Detect entries representing the same underlying income from different sources.

    Duplicate = same income_type + gross_amount within 0.5% + tds_amount within 0.5%.

    Source preference (lower rank = kept as primary):
      0 → Specific bank interest certificate (cert, NRE, NRO in source name)
      5 → Zerodha / MF dividend report
     10 → Combined or generic certificate
     20 → Form 26AS (authoritative for TDS, but secondary for gross income)

    Duplicate entries get:  is_duplicate=True, selected=False, duplicate_of=<primary source name>
    Primary entries get:    is_duplicate=False, selected=True
    """

    def _amounts_close(a: float, b: float) -> bool:
        if a == b:
            return True
        if max(abs(a), abs(b)) < 0.01:
            return True
        return abs(a - b) / max(abs(a), abs(b)) < 0.005

    def _source_rank(entry: Dict) -> int:
        src = (entry.get('source_name') or '').lower()
        code = (entry.get('doc_code') or '').upper()
        if '26as' in src:
            return 20
        if 'combined' in src or 'cum' in src:
            return 10
        if 'zerodha' in src or 'dividend' in src or code == 'ZERODHA_DIV':
            return 5
        return 0  # Specific interest cert — most preferred

    for i, e in enumerate(entries):
        e.setdefault('is_duplicate', False)
        e.setdefault('duplicate_of', None)
        e.setdefault('duplicate_group', None)
        e.setdefault('selected', True)

    n = len(entries)
    processed = set()
    group_counter = 0

    for i in range(n):
        if i in processed:
            continue
        ei = entries[i]
        group = [i]

        for j in range(i + 1, n):
            ej = entries[j]
            if (ei['income_type'] == ej['income_type']
                    and _amounts_close(ei['gross_amount'], ej['gross_amount'])
                    and _amounts_close(ei['tds_amount'], ej['tds_amount'])
                    and ei['gross_amount'] > 0):
                group.append(j)
                processed.add(j)

        if len(group) > 1:
            group_counter += 1
            gid = f"DG{group_counter}"
            group.sort(key=lambda idx: _source_rank(entries[idx]))
            preferred_idx = group[0]

            for idx in group:
                entries[idx]['duplicate_group'] = gid
                if idx == preferred_idx:
                    entries[idx]['is_duplicate'] = False
                    entries[idx]['selected'] = True
                else:
                    entries[idx]['is_duplicate'] = True
                    entries[idx]['selected'] = False
                    entries[idx]['duplicate_of'] = entries[preferred_idx]['source_name']

    return entries


def _doc_type_for_code(doc_code: str) -> Optional[str]:
    """Map document checklist code to parser DocumentType string."""
    code = (doc_code or "").upper()
    if code == "PORTAL_AIS":
        return "AIS"
    if code == "PORTAL_26AS":
        return "FORM_26AS"
    # Bank interest / TDS certificates → dedicated interest parser
    # LOAN_CERT is excluded — it's a home-loan deduction doc, not income
    if code.endswith("_INT"):
        return "INTEREST_CERTIFICATE"
    if code == "ZERODHA_DIV":
        return "DIV_REPORT"
    if code in {"ZERODHA_TAXPL", "MF_CG"}:
        return "CAS"
    return None


def _map_income_type(label: str) -> str:
    text_value = (label or "").strip().lower()
    if "salary" in text_value and "foreign" in text_value:
        return "salary_foreign"
    if "salary" in text_value:
        return "salary_india"
    if "interest" in text_value:
        return "interest_other"
    if "dividend" in text_value:
        return "dividend"
    if "rent" in text_value:
        return "rental"
    if "professional" in text_value:
        return "professional"
    if "capital" in text_value or "gain" in text_value:
        return "cg_long"
    return "other"


def _build_income_drafts_from_parse(doc, parse_result: Dict[str, Any], evidence_id: Optional[int]) -> List[Dict[str, Any]]:
    drafts: List[Dict[str, Any]] = []
    data = parse_result.get("extracted_data") or {}
    doc_type = (parse_result.get("document_type") or "").lower()
    source_label = _checklist_display_title(doc)

    if doc_type == "ais":
        for section in (data.get("sections") or []):
            section_name = section.get("section") or "Other"
            amount = _to_amount(section.get("amount"))
            income_type = section.get("income_type") or _map_income_type(section_name)
            if amount <= 0:
                continue
            drafts.append({
                "income_type": income_type,
                "source_name": f"{source_label} – {section_name}",
                "gross_amount": amount,
                "tds_amount": 0.0,
                "confidence": "medium",
                "rationale": f"Extracted from AIS section: {section_name}.",
                "doc_code": doc.code,
                "evidence_id": evidence_id,
            })

    elif doc_type == "form_26as":
        # tds_entries have: deductor, gross_amount, tds
        for row in (data.get("tds_entries") or []):
            gross = _to_amount(row.get("gross_amount") or row.get("amount"))
            tds = _to_amount(row.get("tds") or row.get("tds_amount"))
            if gross <= 0 and tds <= 0:
                continue
            deductor = row.get("deductor") or "TDS Deductor"
            drafts.append({
                "income_type": "interest_other",
                "source_name": f"26AS – {deductor}",
                "gross_amount": gross,
                "tds_amount": tds,
                "confidence": "high",
                "rationale": "Extracted from Form 26AS PART-I TDS entry. Gross = total amount paid/credited by deductor.",
                "doc_code": doc.code,
                "evidence_id": evidence_id,
            })

    elif doc_type == "interest_certificate":
        code_upper = (doc.code or "").upper()
        is_nre_code = "NRE" in code_upper
        is_nro_code = "NRO" in code_upper
        is_combined = data.get("is_combined", False)

        if is_combined and is_nre_code:
            gross = _to_amount(data.get("nre_total_interest"))
            tds = _to_amount(data.get("nre_total_tds"))
            label_suffix = "NRE Interest (tax-exempt for NRI)"
        elif is_combined and is_nro_code:
            gross = _to_amount(data.get("nro_total_interest"))
            tds = _to_amount(data.get("nro_total_tds"))
            label_suffix = "NRO Interest"
        elif data.get("is_nre"):
            gross = _to_amount(data.get("total_interest"))
            tds = _to_amount(data.get("total_tds"))
            label_suffix = "NRE Interest (tax-exempt for NRI)"
        else:
            gross = _to_amount(data.get("total_interest"))
            tds = _to_amount(data.get("total_tds"))
            label_suffix = "NRO Interest"

        if gross > 0 or tds > 0:
            is_nre = "NRE" in label_suffix
            drafts.append({
                "income_type": "interest_other",
                "source_name": f"{source_label} – {label_suffix}",
                "gross_amount": gross,
                "tds_amount": tds,
                "confidence": "high",
                "rationale": (
                    "Extracted from interest/TDS certificate. "
                    + ("NRE interest is exempt from Indian income tax for NRI." if is_nre
                       else "NRO interest is taxable; TDS already deducted by bank.")
                ),
                "doc_code": doc.code,
                "evidence_id": evidence_id,
            })

    elif doc_type == "dividend_report":
        total_div = _to_amount(data.get("total_dividend"))
        entries = data.get("entries") or []
        n_stocks = len(set(e.get("symbol") for e in entries if e.get("symbol")))
        if total_div > 0:
            drafts.append({
                "income_type": "dividend",
                "source_name": f"{source_label} – Equity Dividends ({n_stocks} stocks)",
                "gross_amount": total_div,
                "tds_amount": 0.0,
                "confidence": "high",
                "rationale": (
                    f"Extracted from Zerodha dividend report: {len(entries)} dividend credits, "
                    f"{n_stocks} stocks, total ₹{total_div:,.2f}. "
                    "TDS deducted by companies appears in Form 26AS — cross-check there."
                ),
                "doc_code": doc.code,
                "evidence_id": evidence_id,
            })

    elif doc_type in {"bank_statement", "cas"}:
        # Legacy path for statements incorrectly routed as bank_statement
        raw_interest = _to_amount((data or {}).get("interest_amount"))
        raw_tds = _to_amount((data or {}).get("tds_amount"))
        if raw_interest > 0 or raw_tds > 0:
            drafts.append({
                "income_type": "interest_other",
                "source_name": source_label,
                "gross_amount": raw_interest,
                "tds_amount": raw_tds,
                "confidence": "low",
                "rationale": "Heuristic read from statement. Verify values manually.",
                "doc_code": doc.code,
                "evidence_id": evidence_id,
            })

    return drafts


def _load_evidences_for_requirements(session, requirement_ids: list[int]) -> Dict[int, list]:
    if not requirement_ids or DocumentEvidence is None:
        return {}
    rows = session.scalars(
        select(DocumentEvidence)
        .where(DocumentEvidence.document_requirement_id.in_(requirement_ids))
        .order_by(DocumentEvidence.is_primary.desc(), DocumentEvidence.created_at.asc(), DocumentEvidence.id.asc())
    ).all()
    grouped: Dict[int, list] = {}
    for row in rows:
        grouped.setdefault(row.document_requirement_id, []).append(row)
    return grouped


def _sync_requirement_from_evidences(requirement, evidences: list) -> None:
    if not evidences:
        requirement.file_path = None
        requirement.status = "Missing" if requirement.required else "Not applicable"
        requirement.notes = None
        return

    primary = next((e for e in evidences if e.is_primary), evidences[0])
    for e in evidences:
        e.is_primary = (e.id == primary.id)
    requirement.file_path = primary.file_path
    requirement.status = "Received"
    requirement.notes = f"Primary source: {primary.title or os.path.basename(primary.file_path)}"


def _add_document_evidence(
    session,
    requirement,
    file_path: str,
    title: Optional[str] = None,
    source_document_requirement_id: Optional[int] = None,
    make_primary: bool = False,
):
    existing = session.scalars(
        select(DocumentEvidence).where(DocumentEvidence.document_requirement_id == requirement.id)
    ).all() if DocumentEvidence is not None else []
    duplicate = next((row for row in existing if row.file_path == file_path), None)
    if duplicate:
        if title:
            duplicate.title = title
        if make_primary:
            for row in existing:
                row.is_primary = (row.id == duplicate.id)
                session.add(row)
        _sync_requirement_from_evidences(requirement, existing)
        session.add(requirement)
        session.flush()
        return duplicate
    if make_primary:
        for row in existing:
            row.is_primary = False
            session.add(row)
    elif not existing:
        make_primary = True
    evidence = DocumentEvidence(
        document_requirement_id=requirement.id,
        title=title or os.path.basename(file_path),
        file_path=file_path,
        is_primary=make_primary,
        source_document_requirement_id=source_document_requirement_id,
    )
    session.add(evidence)
    session.flush()
    _sync_requirement_from_evidences(requirement, existing + [evidence])
    session.add(requirement)
    return evidence


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


def _ensure_document_evidence_table() -> None:
    if engine is None or DocumentEvidence is None:
        return
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS document_evidences (
                id SERIAL PRIMARY KEY,
                document_requirement_id INTEGER NOT NULL REFERENCES document_requirements(id) ON DELETE CASCADE,
                title VARCHAR(240),
                file_path TEXT NOT NULL,
                is_primary BOOLEAN NOT NULL DEFAULT FALSE,
                source_document_requirement_id INTEGER REFERENCES document_requirements(id),
                notes TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_document_evidences_requirement_id ON document_evidences(document_requirement_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_document_evidences_file_path ON document_evidences(file_path)"))
        conn.execute(text("""
            INSERT INTO document_evidences (document_requirement_id, title, file_path, is_primary, notes)
            SELECT dr.id, dr.title, dr.file_path, TRUE, 'Backfilled from legacy single-file link'
            FROM document_requirements dr
            WHERE dr.file_path IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM document_evidences de
                  WHERE de.document_requirement_id = dr.id
              )
        """))
        conn.execute(text("""
            WITH ranked AS (
                SELECT id, document_requirement_id,
                       ROW_NUMBER() OVER (PARTITION BY document_requirement_id ORDER BY is_primary DESC, created_at ASC, id ASC) AS rn
                FROM document_evidences
            )
            UPDATE document_evidences de
            SET is_primary = (ranked.rn = 1)
            FROM ranked
            WHERE de.id = ranked.id
        """))
        conn.execute(text("""
            UPDATE document_requirements dr
            SET file_path = de.file_path,
                status = 'Received',
                notes = COALESCE(de.title, dr.title)
            FROM document_evidences de
            WHERE de.document_requirement_id = dr.id
              AND de.is_primary = TRUE
        """))


_ensure_profile_table()
_ensure_document_evidence_table()


def _ensure_family_members_table() -> None:
    if engine is None:
        return
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS family_members (
                id SERIAL PRIMARY KEY,
                name VARCHAR(160) NOT NULL,
                relationship VARCHAR(60) NOT NULL,
                date_of_birth DATE,
                citizenship VARCHAR(80),
                residential_status VARCHAR(60),
                oci_card_last4 VARCHAR(6),
                pan_last4 VARCHAR(4),
                living_in_india BOOLEAN DEFAULT TRUE,
                currently_studying BOOLEAN DEFAULT FALSE,
                institution_name VARCHAR(200),
                course_details VARCHAR(200),
                currently_working BOOLEAN DEFAULT FALSE,
                employer_country VARCHAR(80),
                has_india_income BOOLEAN DEFAULT FALSE,
                india_income_notes TEXT,
                govt_scheme_eligibility TEXT,
                tax_relevance_notes TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.execute(text("ALTER TABLE family_members ADD COLUMN IF NOT EXISTS currently_studying BOOLEAN DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE family_members ADD COLUMN IF NOT EXISTS institution_name VARCHAR(200)"))
        conn.execute(text("ALTER TABLE family_members ADD COLUMN IF NOT EXISTS course_details VARCHAR(200)"))
        conn.execute(text("ALTER TABLE family_members ADD COLUMN IF NOT EXISTS currently_working BOOLEAN DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE family_members ADD COLUMN IF NOT EXISTS employer_country VARCHAR(80)"))
        conn.execute(text("ALTER TABLE family_members ADD COLUMN IF NOT EXISTS has_india_income BOOLEAN DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE family_members ADD COLUMN IF NOT EXISTS india_income_notes TEXT"))
        conn.execute(text("ALTER TABLE family_members ADD COLUMN IF NOT EXISTS govt_scheme_eligibility TEXT"))
        conn.execute(text("ALTER TABLE family_members ADD COLUMN IF NOT EXISTS tax_relevance_notes TEXT"))


_ensure_family_members_table()


def _ensure_travel_history_table() -> None:
    if engine is None:
        return
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS case_travel_history (
                id SERIAL PRIMARY KEY,
                case_id INTEGER NOT NULL REFERENCES tax_cases(id) ON DELETE CASCADE,
                departure_date DATE NOT NULL,
                arrival_date DATE NOT NULL,
                from_country VARCHAR(80) DEFAULT 'India',
                to_country VARCHAR(80) DEFAULT 'Outside India',
                trip_purpose VARCHAR(120),
                notes TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.execute(text("ALTER TABLE case_travel_history ADD COLUMN IF NOT EXISTS from_country VARCHAR(80) DEFAULT 'India'"))
        conn.execute(text("ALTER TABLE case_travel_history ADD COLUMN IF NOT EXISTS to_country VARCHAR(80) DEFAULT 'Outside India'"))
        conn.execute(text("ALTER TABLE case_travel_history ADD COLUMN IF NOT EXISTS trip_purpose VARCHAR(120)"))
        conn.execute(text("ALTER TABLE case_travel_history ADD COLUMN IF NOT EXISTS notes TEXT"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_case_travel_history_case_id ON case_travel_history(case_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_case_travel_history_departure_date ON case_travel_history(departure_date)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_case_travel_history_arrival_date ON case_travel_history(arrival_date)"))


_ensure_travel_history_table()


def _ensure_residency_settings_table() -> None:
    if engine is None:
        return
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS case_residency_settings (
                id SERIAL PRIMARY KEY,
                case_id INTEGER UNIQUE NOT NULL REFERENCES tax_cases(id) ON DELETE CASCADE,
                fy_start_location VARCHAR(20) NOT NULL DEFAULT 'outside_india',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.execute(text("ALTER TABLE case_residency_settings ADD COLUMN IF NOT EXISTS fy_start_location VARCHAR(20) NOT NULL DEFAULT 'outside_india'"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_case_residency_settings_case_id ON case_residency_settings(case_id)"))


_ensure_residency_settings_table()

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


def _fy_start_year(financial_year: str) -> int:
    """
    Convert FY labels like '2025-26' to start year (2025).
    Falls back to current FY start year if parsing fails.
    """
    try:
        raw = (financial_year or "").strip()
        if "-" in raw:
            return int(raw.split("-")[0])
        return int(raw[:4])
    except Exception:
        today = date.today()
        return today.year if today.month >= 4 else today.year - 1


def _fy_bounds(start_year: int) -> tuple[date, date]:
    return date(start_year, 4, 1), date(start_year + 1, 3, 31)


def _travel_days_outside_india(trips: List[Dict[str, Any]], period_start: date, period_end: date) -> int:
    """
    Count days outside India in a period.
    Assumption: departure date is first day outside India; arrival date is day back in India.
    So outside interval = [departure_date, arrival_date - 1 day].
    """
    outside_days = 0
    for trip in trips:
        dep = trip.get("departure_date")
        arr = trip.get("arrival_date")
        if not dep or not arr:
            continue
        if isinstance(dep, str):
            dep = datetime.strptime(dep, "%Y-%m-%d").date()
        if isinstance(arr, str):
            arr = datetime.strptime(arr, "%Y-%m-%d").date()
        if arr <= dep:
            continue
        trip_start = dep
        trip_end = arr - timedelta(days=1)
        overlap_start = max(period_start, trip_start)
        overlap_end = min(period_end, trip_end)
        if overlap_end >= overlap_start:
            outside_days += (overlap_end - overlap_start).days + 1
    return outside_days


def _load_case_travel_history(session, case_id: int) -> List[Dict[str, Any]]:
    rows = session.execute(
        text("""
            SELECT id, case_id, departure_date, arrival_date, from_country, to_country, trip_purpose, notes, created_at, updated_at
            FROM case_travel_history
            WHERE case_id = :case_id
            ORDER BY departure_date ASC, arrival_date ASC, id ASC
        """),
        {"case_id": case_id},
    ).mappings().all()
    result: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        for key in ("departure_date", "arrival_date", "created_at", "updated_at"):
            if item.get(key):
                item[key] = str(item[key])
        result.append(item)
    return result


def _is_india_country(value: Optional[str]) -> bool:
    text_value = (value or "").strip().lower()
    if not text_value:
        return False
    if text_value in {"india", "ind", "in", "bharat", "republic of india"}:
        return True
    # Avoid false positives like "Outside India", "Non-India", etc.
    negative_phrases = ("outside india", "non india", "non-india", "not india")
    if any(phrase in text_value for phrase in negative_phrases):
        return False
    return False


def _normalize_fy_start_location(raw: Optional[str], case_status: str = "NRI") -> str:
    text_value = (raw or "").strip().lower()
    if text_value in {"india", "outside_india"}:
        return text_value
    return "outside_india" if case_status in {"NRI", "RNOR"} else "india"


def _load_residency_settings(session, case_id: int, case_status: str = "NRI") -> Dict[str, Any]:
    row = session.execute(
        text("SELECT fy_start_location FROM case_residency_settings WHERE case_id = :case_id"),
        {"case_id": case_id},
    ).mappings().first()
    fy_start_location = _normalize_fy_start_location(row["fy_start_location"] if row else None, case_status)
    return {"fy_start_location": fy_start_location}


def _upsert_residency_settings(session, case_id: int, fy_start_location: Optional[str], case_status: str = "NRI") -> Dict[str, Any]:
    normalized = _normalize_fy_start_location(fy_start_location, case_status)
    session.execute(
        text("""
            INSERT INTO case_residency_settings (case_id, fy_start_location, updated_at)
            VALUES (:case_id, :fy_start_location, NOW())
            ON CONFLICT (case_id)
            DO UPDATE SET fy_start_location = EXCLUDED.fy_start_location, updated_at = NOW()
        """),
        {"case_id": case_id, "fy_start_location": normalized},
    )
    return {"fy_start_location": normalized}


def _add_segment_days_to_fy(segment_start: date, segment_end: date, location: str, fy_day_counts: Dict[int, Dict[str, int]]) -> None:
    if segment_end < segment_start:
        return
    cursor = segment_start
    while cursor <= segment_end:
        fy_start_year = cursor.year if cursor.month >= 4 else cursor.year - 1
        fy_start, fy_end = _fy_bounds(fy_start_year)
        chunk_end = min(segment_end, fy_end)
        days = (chunk_end - cursor).days + 1
        bucket = fy_day_counts.setdefault(fy_start_year, {"india": 0, "outside_india": 0})
        bucket[location] += days
        cursor = chunk_end + timedelta(days=1)


def _compute_residency_day_counts_from_travel(financial_year: str, trips: List[Dict[str, Any]], fy_start_location: str = "outside_india", case_status: str = "NRI") -> Dict[str, Any]:
    current_start_year = _fy_start_year(financial_year)
    window_start_year = current_start_year - 10
    window_start, _ = _fy_bounds(window_start_year)
    _, window_end = _fy_bounds(current_start_year)
    location = _normalize_fy_start_location(fy_start_location, case_status)

    events: List[Dict[str, Any]] = []
    for trip in trips:
        dep = trip.get("departure_date")
        arr = trip.get("arrival_date")
        from_country = trip.get("from_country")
        to_country = trip.get("to_country")
        if dep:
            dep_date = dep if isinstance(dep, date) else datetime.strptime(str(dep), "%Y-%m-%d").date()
            if window_start <= dep_date <= window_end and _is_india_country(from_country):
                events.append({"date": dep_date, "location": "outside_india", "priority": 1})
        if arr:
            arr_date = arr if isinstance(arr, date) else datetime.strptime(str(arr), "%Y-%m-%d").date()
            if window_start <= arr_date <= window_end and _is_india_country(to_country):
                events.append({"date": arr_date, "location": "india", "priority": 2})

    events.sort(key=lambda x: (x["date"], x["priority"]))
    fy_day_counts: Dict[int, Dict[str, int]] = {}
    cursor = window_start
    current_location = location

    for ev in events:
        ev_date: date = ev["date"]
        if ev_date > window_end:
            break
        if ev_date > cursor:
            _add_segment_days_to_fy(cursor, ev_date - timedelta(days=1), current_location, fy_day_counts)
        current_location = ev["location"]
        cursor = ev_date

    if cursor <= window_end:
        _add_segment_days_to_fy(cursor, window_end, current_location, fy_day_counts)

    yearly_breakdown = []
    prior4_days = 0
    prior7_days = 0
    for offset in range(1, 11):
        y = current_start_year - offset
        y_start, y_end = _fy_bounds(y)
        bucket = fy_day_counts.get(y, {"india": 0, "outside_india": (y_end - y_start).days + 1})
        in_india = bucket["india"]
        outside = bucket["outside_india"]
        yearly_breakdown.append({
            "financial_year": f"{y_start.year}-{str(y_end.year)[-2:]}",
            "days_in_india": in_india,
            "days_outside_india": outside,
        })
        if offset <= 4:
            prior4_days += in_india
        if offset <= 7:
            prior7_days += in_india

    current_bucket = fy_day_counts.get(current_start_year, {"india": 0})
    current_in_india = current_bucket["india"]

    return {
        "days_in_india_current_fy": current_in_india,
        "days_in_india_prior_4y": prior4_days,
        "days_in_india_prior_7y": prior7_days,
        "yearly_breakdown": yearly_breakdown,
        "calculation_basis": {
            "assumption": "Departure from India counts as outside from departure date; arrival into India counts as in India from arrival date.",
            "current_financial_year": financial_year,
            "fy_start_location_assumed": _normalize_fy_start_location(fy_start_location, case_status),
        },
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
    headers = {'User-Agent': 'ITR-Assistant/1.0'}
    try:
        if country_norm == 'india':
            if not code.isdigit() or len(code) != 6:
                return {'ok': True, 'valid': False, 'country': 'India', 'message': 'Indian PIN must be 6 digits'}
            r = requests.get(f'https://api.postalpincode.in/pincode/{code}', timeout=8, headers=headers)
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
            r = requests.get(f'https://api.zippopotam.us/us/{query_code}', timeout=8, headers=headers)
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
    except requests.RequestException:
        return {
            'ok': True,
            'valid': False,
            'country': 'India' if country_norm == 'india' else 'US' if country_norm in {'us', 'usa', 'united states', 'united states of america'} else None,
            'message': 'Postal lookup service is temporarily unavailable. You can continue and save address details manually.',
        }
    except Exception:
        return {
            'ok': True,
            'valid': False,
            'message': 'Unable to validate postal code right now. Please save manually and retry later.',
        }


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
        evidence_map = _load_evidences_for_requirements(session, [r.id for r in rows])
        out = [
            {
                'id': r.id,
                'code': r.code,
                'title': r.title,
                'display_title': _checklist_display_title(r),
                'category': r.category,
                'institution': r.institution,
                'required': r.required,
                'status': r.status,
                'file_path': r.file_path,
                'is_not_applicable': r.status == 'Not applicable',
                'not_applicable_reason': _parse_not_applicable_reason(r.notes),
                'portal': {
                    'name': DOCUMENT_PORTAL_MAP.get(r.code, (r.institution or 'Source Portal', None))[0],
                    'url': DOCUMENT_PORTAL_MAP.get(r.code, (None, None))[1],
                },
                'evidences': [
                    {
                        'id': e.id,
                        'title': e.title,
                        'file_path': e.file_path,
                        'is_primary': e.is_primary,
                        'source_document_requirement_id': e.source_document_requirement_id,
                    }
                    for e in evidence_map.get(r.id, [])
                ],
                'has_multiple_sources': len(evidence_map.get(r.id, [])) > 1,
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
                _add_document_evidence(session, dr, dest, title=filename, make_primary=True)
                session.add(AuditLog(
                    case_id=case_id,
                    action='DOCUMENT_UPLOAD',
                    entity='DocumentRequirement',
                    details=f'{dr.code}:{filename} (set as primary source)'
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
                session.flush()
                _add_document_evidence(session, dr, dest, title=filename, make_primary=True)
                session.add(AuditLog(
                    case_id=case_id,
                    action='DOCUMENT_UPLOAD',
                    entity='DocumentRequirement',
                    details=f'{code}:{filename} (new category with primary source)'
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


@app.get('/api/cases/{case_id}/documents/{doc_code}/preview')
def preview_case_document(case_id: int, doc_code: str, download: bool = False):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        doc = session.scalar(
            select(DocumentRequirement).where(
                DocumentRequirement.case_id == case_id,
                DocumentRequirement.code == doc_code,
            )
        )
        if not doc or not doc.file_path:
            raise HTTPException(status_code=404, detail='Document file not found')
        path = doc.file_path
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail='Linked file path is missing on disk')
        media_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'
        filename = os.path.basename(path)
        disposition = 'attachment' if download else 'inline'
        return FileResponse(
            path=path,
            media_type=media_type,
            filename=filename,
            headers={'Content-Disposition': f'{disposition}; filename="{filename}"'},
        )


@app.get('/api/documents/{document_id}/preview')
def preview_vault_document(document_id: int, download: bool = False):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        doc = session.get(DocumentRequirement, document_id)
        if not doc or not doc.file_path:
            raise HTTPException(status_code=404, detail='Document file not found')
        path = doc.file_path
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail='Linked file path is missing on disk')
        media_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'
        filename = os.path.basename(path)
        disposition = 'attachment' if download else 'inline'
        return FileResponse(
            path=path,
            media_type=media_type,
            filename=filename,
            headers={'Content-Disposition': f'{disposition}; filename="{filename}"'},
        )


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

        evidence = _add_document_evidence(
            session,
            target_doc,
            source_doc.file_path,
            title=source_doc.title or f"{doc_code} from case {source_case.id}",
            source_document_requirement_id=source_doc.id,
            make_primary=(target_doc.file_path is None),
        )
        session.add(AuditLog(
            case_id=case_id,
            action='DOCUMENT_REUSED',
            entity='DocumentRequirement',
            details=f'{doc_code} linked from case {source_case.id} as {"primary" if evidence.is_primary else "supporting"} source',
        ))
        session.commit()
        return {'ok': True, 'linked_from_case_id': source_case.id, 'path': evidence.file_path, 'evidence_id': evidence.id, 'is_primary': evidence.is_primary}


@app.post('/api/cases/{case_id}/documents/{doc_code}/link')
def link_document_from_vault(case_id: int, doc_code: str, data: Dict[str, Any]):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    source_document_id = data.get('source_document_id')
    if not source_document_id:
        raise HTTPException(status_code=400, detail='source_document_id is required')
    with SessionLocal() as session:
        case = session.get(TaxCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail='Case not found')
        source_doc = session.get(DocumentRequirement, int(source_document_id))
        if not source_doc or not source_doc.file_path:
            raise HTTPException(status_code=404, detail='Source document not found or has no linked file')
        source_case = session.get(TaxCase, source_doc.case_id)
        if not source_case or source_case.taxpayer_id != case.taxpayer_id:
            raise HTTPException(status_code=400, detail='Source document must belong to the same taxpayer')
        if not _is_doc_reusable_across_years(doc_code):
            raise HTTPException(status_code=400, detail='This document code is not reusable across years')

        target_doc = session.scalar(
            select(DocumentRequirement).where(
                DocumentRequirement.case_id == case_id,
                DocumentRequirement.code == doc_code,
            )
        )
        if not target_doc:
            target_doc = DocumentRequirement(
                case_id=case_id,
                code=doc_code,
                category=source_doc.category or 'Uploaded',
                title=source_doc.title or doc_code,
                required=False,
                status='Missing',
            )
            session.add(target_doc)
            session.flush()

        evidence = _add_document_evidence(
            session,
            target_doc,
            source_doc.file_path,
            title=source_doc.title or f"{doc_code} from case {source_doc.case_id}",
            source_document_requirement_id=source_doc.id,
            make_primary=(target_doc.file_path is None),
        )
        session.add(AuditLog(
            case_id=case_id,
            action='DOCUMENT_LINKED',
            entity='DocumentRequirement',
            details=f'{doc_code} linked from document {source_doc.id} (case {source_doc.case_id}) as {"primary" if evidence.is_primary else "supporting"} source',
        ))
        session.commit()
        return {'ok': True, 'document_id': target_doc.id, 'path': evidence.file_path, 'evidence_id': evidence.id, 'is_primary': evidence.is_primary}


@app.put('/api/cases/{case_id}/documents/{doc_code}/rename')
def rename_document(case_id: int, doc_code: str, data: Dict[str, Any]):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    new_title = (data.get('title') or '').strip()
    if not new_title:
        raise HTTPException(status_code=400, detail='title is required')
    evidence_id = data.get('evidence_id')
    with SessionLocal() as session:
        doc = session.scalar(
            select(DocumentRequirement).where(
                DocumentRequirement.case_id == case_id,
                DocumentRequirement.code == doc_code,
            )
        )
        if not doc:
            raise HTTPException(status_code=404, detail='Document requirement not found')
        target_evidence = None
        evidences = session.scalars(
            select(DocumentEvidence).where(DocumentEvidence.document_requirement_id == doc.id).order_by(
                DocumentEvidence.is_primary.desc(), DocumentEvidence.id.asc()
            )
        ).all() if DocumentEvidence is not None else []
        if evidence_id:
            target_evidence = next((e for e in evidences if e.id == int(evidence_id)), None)
            if not target_evidence:
                raise HTTPException(status_code=404, detail='Document evidence not found')
        elif evidences:
            target_evidence = evidences[0]

        old_title = target_evidence.title if target_evidence else doc.title
        if target_evidence:
            target_evidence.title = new_title
            session.add(target_evidence)
        elif not evidences:
            doc.title = new_title
            session.add(doc)
        session.add(AuditLog(
            case_id=case_id,
            action='DOCUMENT_RENAMED',
            entity='DocumentRequirement',
            details=(
                f'{doc_code} file label renamed: "{old_title}" -> "{new_title}" (evidence {target_evidence.id})'
                if target_evidence
                else f'{doc_code}: "{old_title}" -> "{new_title}"'
            ),
        ))
        session.commit()
        return {'ok': True, 'title': doc.title}


@app.post('/api/cases/{case_id}/documents/{doc_code}/applicability')
def set_document_applicability(case_id: int, doc_code: str, data: Dict[str, Any]):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    applicable = bool(data.get('applicable', True))
    reason = (data.get('reason') or '').strip()
    with SessionLocal() as session:
        doc = session.scalar(
            select(DocumentRequirement).where(
                DocumentRequirement.case_id == case_id,
                DocumentRequirement.code == doc_code,
            )
        )
        if not doc:
            raise HTTPException(status_code=404, detail='Document requirement not found')
        evidences = session.scalars(
            select(DocumentEvidence).where(DocumentEvidence.document_requirement_id == doc.id)
        ).all() if DocumentEvidence is not None else []

        if not applicable:
            doc.status = 'Not applicable'
            doc.notes = f"Not applicable: {reason}" if reason else "Not applicable: User marked this item as not applicable for current filing."
        else:
            if evidences:
                _sync_requirement_from_evidences(doc, evidences)
            else:
                doc.file_path = None
                doc.status = 'Missing' if doc.required else 'Not applicable'
            if _parse_not_applicable_reason(doc.notes):
                doc.notes = None
        session.add(doc)
        session.add(AuditLog(
            case_id=case_id,
            action='DOCUMENT_APPLICABILITY_UPDATED',
            entity='DocumentRequirement',
            details=f'{doc_code} marked as {"applicable" if applicable else "not applicable"}' + (f' ({reason})' if reason else ''),
        ))
        session.commit()
        return {
            'ok': True,
            'status': doc.status,
            'is_not_applicable': doc.status == 'Not applicable',
            'not_applicable_reason': _parse_not_applicable_reason(doc.notes),
        }


@app.post('/api/cases/{case_id}/documents/{doc_code}/unlink')
def unlink_document(case_id: int, doc_code: str, data: Optional[Dict[str, Any]] = None):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    payload = data or {}
    delete_file = bool(payload.get('delete_file'))
    evidence_id = payload.get('evidence_id')
    with SessionLocal() as session:
        doc = session.scalar(
            select(DocumentRequirement).where(
                DocumentRequirement.case_id == case_id,
                DocumentRequirement.code == doc_code,
            )
        )
        if not doc:
            raise HTTPException(status_code=404, detail='Document requirement not found')
        evidences = session.scalars(
            select(DocumentEvidence).where(DocumentEvidence.document_requirement_id == doc.id).order_by(
                DocumentEvidence.is_primary.desc(), DocumentEvidence.id.asc()
            )
        ).all() if DocumentEvidence is not None else []
        if not evidences:
            doc.file_path = None
            doc.status = 'Missing' if doc.required else 'Not applicable'
            doc.notes = None
            session.add(doc)
            session.commit()
            return {'ok': True, 'file_deleted': False}

        target = evidences[0]
        if evidence_id:
            target = next((e for e in evidences if e.id == int(evidence_id)), None)
            if not target:
                raise HTTPException(status_code=404, detail='Document evidence not found')
        old_path = target.file_path
        was_primary = target.is_primary
        session.delete(target)
        remaining = [e for e in evidences if e.id != target.id]
        if was_primary and remaining:
            remaining[0].is_primary = True
            session.add(remaining[0])
        _sync_requirement_from_evidences(doc, remaining)
        session.add(doc)
        session.add(AuditLog(
            case_id=case_id,
            action='DOCUMENT_UNLINKED',
            entity='DocumentRequirement',
            details=f'{doc_code} evidence unlinked (id {target.id})',
        ))
        session.commit()

        file_deleted = False
        if delete_file and old_path:
            with SessionLocal() as verify_session:
                ref_count = verify_session.scalar(
                    select(text('COUNT(1)')).select_from(DocumentRequirement).where(
                        DocumentRequirement.file_path == old_path
                    )
                ) or 0
                evidence_ref_count = verify_session.scalar(
                    select(text('COUNT(1)')).select_from(DocumentEvidence).where(
                        DocumentEvidence.file_path == old_path
                    )
                ) or 0
            if ref_count == 0 and evidence_ref_count == 0 and os.path.exists(old_path):
                try:
                    os.remove(old_path)
                    file_deleted = True
                except OSError:
                    file_deleted = False

        return {'ok': True, 'file_deleted': file_deleted}


@app.delete('/api/cases/{case_id}/documents/{doc_code}')
def delete_document(case_id: int, doc_code: str, delete_file: bool = False):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        doc = session.scalar(
            select(DocumentRequirement).where(
                DocumentRequirement.case_id == case_id,
                DocumentRequirement.code == doc_code,
            )
        )
        if not doc:
            raise HTTPException(status_code=404, detail='Document requirement not found')

        evidence_rows = session.scalars(
            select(DocumentEvidence).where(DocumentEvidence.document_requirement_id == doc.id)
        ).all() if DocumentEvidence is not None else []
        old_paths = [e.file_path for e in evidence_rows if e.file_path]
        for e in evidence_rows:
            session.delete(e)
        if doc.required:
            doc.file_path = None
            doc.status = 'Missing'
            doc.notes = None
            session.add(doc)
            action = 'DOCUMENT_CLEARED'
            details = f'{doc_code} is required, so record kept and file link cleared'
        else:
            session.delete(doc)
            action = 'DOCUMENT_DELETED'
            details = f'{doc_code} optional record deleted'

        session.add(AuditLog(
            case_id=case_id,
            action=action,
            entity='DocumentRequirement',
            details=details,
        ))
        session.commit()

        file_deleted = False
        if delete_file and old_paths:
            with SessionLocal() as verify_session:
                for old_path in old_paths:
                    ref_count = verify_session.scalar(
                        select(text('COUNT(1)')).select_from(DocumentRequirement).where(
                            DocumentRequirement.file_path == old_path
                        )
                    ) or 0
                    evidence_ref_count = verify_session.scalar(
                        select(text('COUNT(1)')).select_from(DocumentEvidence).where(
                            DocumentEvidence.file_path == old_path
                        )
                    ) or 0
                    if ref_count == 0 and evidence_ref_count == 0 and os.path.exists(old_path):
                        try:
                            os.remove(old_path)
                            file_deleted = True
                        except OSError:
                            pass

        return {'ok': True, 'file_deleted': file_deleted}


@app.post('/api/cases/{case_id}/documents/{doc_code}/evidence/{evidence_id}/primary')
def set_document_primary_evidence(case_id: int, doc_code: str, evidence_id: int):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        doc = session.scalar(
            select(DocumentRequirement).where(
                DocumentRequirement.case_id == case_id,
                DocumentRequirement.code == doc_code,
            )
        )
        if not doc:
            raise HTTPException(status_code=404, detail='Document requirement not found')
        evidences = session.scalars(
            select(DocumentEvidence).where(DocumentEvidence.document_requirement_id == doc.id).order_by(DocumentEvidence.id.asc())
        ).all() if DocumentEvidence is not None else []
        if not evidences:
            raise HTTPException(status_code=404, detail='No evidence linked for this document')
        target = next((e for e in evidences if e.id == evidence_id), None)
        if not target:
            raise HTTPException(status_code=404, detail='Document evidence not found')
        for e in evidences:
            e.is_primary = (e.id == target.id)
            session.add(e)
        _sync_requirement_from_evidences(doc, evidences)
        session.add(doc)
        session.add(AuditLog(
            case_id=case_id,
            action='DOCUMENT_PRIMARY_SET',
            entity='DocumentRequirement',
            details=f'{doc_code} primary evidence set to id {target.id}',
        ))
        session.commit()
        return {'ok': True, 'evidence_id': target.id, 'file_path': target.file_path}


@app.get('/api/document-evidences/{evidence_id}/preview')
def preview_evidence_document(evidence_id: int, download: bool = False):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        evidence = session.get(DocumentEvidence, evidence_id)
        if not evidence:
            raise HTTPException(status_code=404, detail='Document evidence not found')
        path = evidence.file_path
        if not path or not os.path.exists(path):
            raise HTTPException(status_code=404, detail='Linked file path is missing on disk')
        media_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'
        filename = os.path.basename(path)
        disposition = 'attachment' if download else 'inline'
        return FileResponse(
            path=path,
            media_type=media_type,
            filename=filename,
            headers={'Content-Disposition': f'{disposition}; filename="{filename}"'},
        )


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
        evidence_map = _load_evidences_for_requirements(session, [d.id for d in docs])
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
                    'evidence_count': len(evidence_map.get(d.id, [])),
                    'has_multiple_sources': len(evidence_map.get(d.id, [])) > 1,
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
        residency_settings = _load_residency_settings(session, case_id, case.residential_status)
        travel_history = _load_case_travel_history(session, case_id)
        travel_counts = _compute_residency_day_counts_from_travel(
            case.financial_year, travel_history, residency_settings.get("fy_start_location"), case.residential_status
        )
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
            'travel_history': travel_history,
            'residency_settings': residency_settings,
            'computed_days_from_travel': {
                'days_in_india_current_fy': travel_counts['days_in_india_current_fy'],
                'days_in_india_prior_4y': travel_counts['days_in_india_prior_4y'],
                'days_in_india_prior_7y': travel_counts['days_in_india_prior_7y'],
                'yearly_breakdown': travel_counts['yearly_breakdown'],
                'calculation_basis': travel_counts['calculation_basis'],
            },
            'case_status': case.residential_status,
        }


@app.get('/api/cases/{case_id}/travel-history')
def get_travel_history(case_id: int):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        case = session.get(TaxCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail='Case not found')
        settings = _load_residency_settings(session, case_id, case.residential_status)
        history = _load_case_travel_history(session, case_id)
        counts = _compute_residency_day_counts_from_travel(
            case.financial_year, history, settings.get("fy_start_location"), case.residential_status
        )
        return {'ok': True, 'travel_history': history, 'computed_days': counts, 'residency_settings': settings}


@app.post('/api/cases/{case_id}/travel-history')
def add_travel_history(case_id: int, data: Dict[str, Any]):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    departure = str(data.get('departure_date') or '').strip()
    arrival = str(data.get('arrival_date') or '').strip()
    if not departure or not arrival:
        raise HTTPException(status_code=400, detail='departure_date and arrival_date are required')
    try:
        dep_date = datetime.strptime(departure, '%Y-%m-%d').date()
        arr_date = datetime.strptime(arrival, '%Y-%m-%d').date()
    except ValueError:
        raise HTTPException(status_code=400, detail='Dates must be YYYY-MM-DD')
    if arr_date <= dep_date:
        raise HTTPException(status_code=400, detail='arrival_date must be after departure_date')

    with SessionLocal() as session:
        case = session.get(TaxCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail='Case not found')
        row = session.execute(
            text("""
                INSERT INTO case_travel_history
                    (case_id, departure_date, arrival_date, from_country, to_country, trip_purpose, notes, updated_at)
                VALUES
                    (:case_id, :departure_date, :arrival_date, :from_country, :to_country, :trip_purpose, :notes, NOW())
                RETURNING id
            """),
            {
                'case_id': case_id,
                'departure_date': dep_date,
                'arrival_date': arr_date,
                'from_country': data.get('from_country') or 'India',
                'to_country': data.get('to_country') or 'Outside India',
                'trip_purpose': data.get('trip_purpose'),
                'notes': data.get('notes'),
            },
        ).first()
        session.commit()
        return {'ok': True, 'id': row[0]}


@app.put('/api/cases/{case_id}/travel-history/{travel_id}')
def update_travel_history(case_id: int, travel_id: int, data: Dict[str, Any]):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        case = session.get(TaxCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail='Case not found')
        current = session.execute(
            text("SELECT id, departure_date, arrival_date FROM case_travel_history WHERE case_id = :case_id AND id = :id"),
            {'case_id': case_id, 'id': travel_id},
        ).mappings().first()
        if not current:
            raise HTTPException(status_code=404, detail='Travel history entry not found')

        dep_raw = data.get('departure_date', current['departure_date'])
        arr_raw = data.get('arrival_date', current['arrival_date'])
        dep_date = dep_raw if isinstance(dep_raw, date) else datetime.strptime(str(dep_raw), '%Y-%m-%d').date()
        arr_date = arr_raw if isinstance(arr_raw, date) else datetime.strptime(str(arr_raw), '%Y-%m-%d').date()
        if arr_date <= dep_date:
            raise HTTPException(status_code=400, detail='arrival_date must be after departure_date')

        session.execute(
            text("""
                UPDATE case_travel_history
                SET departure_date = :departure_date,
                    arrival_date = :arrival_date,
                    from_country = :from_country,
                    to_country = :to_country,
                    trip_purpose = :trip_purpose,
                    notes = :notes,
                    updated_at = NOW()
                WHERE case_id = :case_id AND id = :id
            """),
            {
                'case_id': case_id,
                'id': travel_id,
                'departure_date': dep_date,
                'arrival_date': arr_date,
                'from_country': data.get('from_country') or 'India',
                'to_country': data.get('to_country') or 'Outside India',
                'trip_purpose': data.get('trip_purpose'),
                'notes': data.get('notes'),
            },
        )
        session.commit()
        return {'ok': True}


@app.delete('/api/cases/{case_id}/travel-history/{travel_id}')
def delete_travel_history(case_id: int, travel_id: int):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        case = session.get(TaxCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail='Case not found')
        session.execute(
            text("DELETE FROM case_travel_history WHERE case_id = :case_id AND id = :id"),
            {'case_id': case_id, 'id': travel_id},
        )
        session.commit()
        return {'ok': True}


@app.post('/api/cases/{case_id}/residency/recompute-from-travel')
def recompute_residency_from_travel(case_id: int, data: Dict[str, Any] | None = None):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    payload = data or {}
    with SessionLocal() as session:
        case = session.get(TaxCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail='Case not found')
        taxpayer = session.get(Taxpayer, case.taxpayer_id)
        fy_start_location = payload.get('fy_start_location')
        if fy_start_location:
            settings = _upsert_residency_settings(session, case_id, fy_start_location, case.residential_status)
        else:
            settings = _load_residency_settings(session, case_id, case.residential_status)

        travel_history = _load_case_travel_history(session, case_id)
        computed = _compute_residency_day_counts_from_travel(
            case.financial_year, travel_history, settings.get('fy_start_location'), case.residential_status
        )

        record = session.scalar(select(ResidencyRecord).where(ResidencyRecord.case_id == case_id))
        if not record:
            record = ResidencyRecord(case_id=case_id)
        record.days_in_india_current_fy = computed['days_in_india_current_fy']
        record.days_in_india_prior_4y = computed['days_in_india_prior_4y']
        record.days_in_india_prior_7y = computed['days_in_india_prior_7y']
        if 'nonresident_years_prior_10y' in payload:
            record.nonresident_years_prior_10y = payload.get('nonresident_years_prior_10y')
        elif record.nonresident_years_prior_10y is None:
            record.nonresident_years_prior_10y = 0
        if 'date_returned_to_india' in payload:
            raw_date = payload.get('date_returned_to_india')
            record.date_returned_to_india = None if not raw_date else datetime.strptime(raw_date, '%Y-%m-%d').date()
        session.add(record)
        session.commit()

        citizenship = (getattr(taxpayer, 'citizenship', 'Indian') or 'Indian').strip().lower()
        req = ResidencyAssessmentRequest(
            days_in_india_current_fy=record.days_in_india_current_fy or 0,
            days_in_india_prior_4y=record.days_in_india_prior_4y or 0,
            days_in_india_prior_7y=record.days_in_india_prior_7y or 0,
            nonresident_years_prior_10y=record.nonresident_years_prior_10y or 0,
            indian_citizen_or_pio=citizenship != 'foreign',
            visiting_india=bool(record.date_returned_to_india),
            indian_income_excluding_foreign=float(payload.get('indian_income_excluding_foreign') or 0),
            not_liable_to_tax_elsewhere=bool(payload.get('not_liable_to_tax_elsewhere') or False),
        )
        assessment = _compute_residency_status(req)
        return {
            'ok': True,
            'residency_settings': settings,
            'computed_days': computed,
            'assessment': assessment,
            'residency': {
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
        if 'fy_start_location' in data:
            _upsert_residency_settings(session, case_id, data.get('fy_start_location'), case.residential_status)
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


@app.post('/api/cases/{case_id}/loan-cert/parse')
def parse_loan_certificate(case_id: int):
    """
    Parse the uploaded LOAN_CERT document and return calculated interest/principal
    via monthly-rest amortization. Used by the Property page to auto-populate fields.
    """
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        doc = session.scalars(
            select(DocumentRequirement).where(
                DocumentRequirement.case_id == case_id,
                DocumentRequirement.code == 'LOAN_CERT',
            )
        ).first()
        if not doc:
            raise HTTPException(status_code=404, detail='LOAN_CERT requirement not found')

        evidences = _load_evidences_for_requirements(session, [doc.id]).get(doc.id, [])
        primary = next((e for e in evidences if e.is_primary), evidences[0] if evidences else None)
        file_path = primary.file_path if primary else doc.file_path

        if not file_path or not os.path.exists(file_path):
            return {
                'ok': False,
                'error': 'No file uploaded for LOAN_CERT yet. Upload the home loan statement first.',
            }

        try:
            from backend.app.document_parser import DocumentParserFactory, DocumentType
            parsed = DocumentParserFactory.parse_document(file_path, DocumentType.HOME_LOAN_CERT)
            d = parsed.extracted_data

            return {
                'ok': parsed.success,
                'extracted': d,
                'warnings': parsed.warnings,
                'errors': parsed.errors,
                'deduction_summary': {
                    'interest_paid': d.get('interest_paid', 0),
                    'principal_paid': d.get('principal_paid', 0),
                    'section_24b_self_occ_limit': d.get('section_24b_deductible_self_occ', 0),
                    'section_80c_principal_limit': d.get('section_80c_deductible', 0),
                    'note': (
                        'Section 24(b): Interest deduction capped at ₹2,00,000 for self-occupied. '
                        'No cap if property is let-out. '
                        'Section 80C: Principal repayment deductible up to ₹1,50,000 overall limit.'
                    ),
                },
            }
        except Exception as e:
            return {'ok': False, 'error': str(e)}
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
    source_name: Optional[str] = None
    evidence_code: Optional[str] = None
    notes: Optional[str] = None
    amount_in_return: Optional[float] = None


class AutoIncomeDraftEntry(BaseModel):
    income_type: str
    source_name: str
    gross_amount: float = 0
    tds_amount: float = 0
    doc_code: Optional[str] = None
    evidence_id: Optional[int] = None
    rationale: Optional[str] = None
    confidence: Optional[str] = None


class AutoIncomeApplyRequest(BaseModel):
    entries: List[AutoIncomeDraftEntry]
    replace_existing: bool = False


@app.post('/api/cases/{case_id}/income/auto-draft')
def generate_income_auto_draft(case_id: int):
    if not SessionLocal:
        return {'error': 'Database not configured'}
    session = SessionLocal()
    try:
        case = session.query(TaxCase).filter(TaxCase.id == case_id).first()
        if not case:
            raise HTTPException(status_code=404, detail='Case not found')

        docs = session.scalars(
            select(DocumentRequirement).where(DocumentRequirement.case_id == case_id)
        ).all()
        evidence_map = _load_evidences_for_requirements(session, [d.id for d in docs])
        parsed_docs = []
        draft_entries: List[Dict[str, Any]] = []
        skipped = []

        for doc in docs:
            if doc.status == 'Not applicable':
                skipped.append({'code': doc.code, 'reason': 'Marked not applicable'})
                continue
            evidences = evidence_map.get(doc.id, [])
            primary = next((e for e in evidences if e.is_primary), evidences[0] if evidences else None)
            file_path = primary.file_path if primary else doc.file_path
            if not file_path or not os.path.exists(file_path):
                continue
            doc_type_name = _doc_type_for_code(doc.code)
            if not doc_type_name:
                continue
            try:
                from backend.app.document_parser import DocumentParserFactory, DocumentType
                doc_type_enum = DocumentType[doc_type_name]
                parsed = DocumentParserFactory.parse_document(file_path, doc_type_enum)
                parsed_payload = {
                    'ok': parsed.success,
                    'document_type': parsed.doc_type,
                    'extracted_data': parsed.extracted_data,
                    'warnings': parsed.warnings,
                    'errors': parsed.errors,
                }
                parsed_docs.append({
                    'doc_code': doc.code,
                    'display_title': _checklist_display_title(doc),
                    'document_type': parsed.doc_type,
                    'warnings': parsed.warnings,
                    'errors': parsed.errors,
                    'evidence_id': primary.id if primary else None,
                })
                draft_entries.extend(_build_income_drafts_from_parse(doc, parsed_payload, primary.id if primary else None))
            except Exception as e:
                parsed_docs.append({
                    'doc_code': doc.code,
                    'display_title': _checklist_display_title(doc),
                    'document_type': doc_type_name.lower(),
                    'warnings': [],
                    'errors': [str(e)],
                    'evidence_id': primary.id if primary else None,
                })

        # Smart deduplication: detect same income from multiple sources
        draft_entries = _deduplicate_draft_entries(draft_entries)

        selected_entries = [e for e in draft_entries if e.get('selected', True)]
        dup_count = sum(1 for e in draft_entries if e.get('is_duplicate', False))

        totals = {
            'gross_amount': round(sum(_to_amount(e.get('gross_amount')) for e in selected_entries), 2),
            'tds_amount': round(sum(_to_amount(e.get('tds_amount')) for e in selected_entries), 2),
            'entries': len(selected_entries),
            'total_draft': len(draft_entries),
            'duplicate_count': dup_count,
            'documents_scanned': len(parsed_docs),
        }
        return {
            'ok': True,
            'case_id': case_id,
            'draft_entries': draft_entries,
            'parsed_documents': parsed_docs,
            'skipped_documents': skipped,
            'totals': totals,
            'disclaimer': 'Auto-draft is assistance only. Review and edit before applying.',
        }
    finally:
        session.close()


@app.post('/api/cases/{case_id}/income/auto-apply')
def apply_income_auto_draft(case_id: int, payload: AutoIncomeApplyRequest):
    if not SessionLocal:
        return {'error': 'Database not configured'}
    session = SessionLocal()
    try:
        case = session.query(TaxCase).filter(TaxCase.id == case_id).first()
        if not case:
            raise HTTPException(status_code=404, detail='Case not found')
        from itr_workspace.models import IncomeEntry as IncomeModel

        if payload.replace_existing:
            existing = session.query(IncomeModel).filter(IncomeModel.case_id == case_id).all()
            for row in existing:
                session.delete(row)
            session.flush()

        created = 0
        skipped = 0
        for entry in payload.entries:
            gross_amount = _to_amount(entry.gross_amount)
            tds_amount = _to_amount(entry.tds_amount)
            if gross_amount <= 0 and tds_amount <= 0:
                skipped += 1
                continue
            duplicate = session.query(IncomeModel).filter(
                IncomeModel.case_id == case_id,
                IncomeModel.income_type == entry.income_type,
                IncomeModel.source_name == entry.source_name,
                IncomeModel.gross_amount == gross_amount,
                IncomeModel.tds_amount == tds_amount,
            ).first()
            if duplicate:
                skipped += 1
                continue
            item = IncomeModel(
                case_id=case_id,
                income_type=entry.income_type,
                source_name=entry.source_name,
                gross_amount=gross_amount,
                tds_amount=tds_amount,
                amount_in_return=max(gross_amount, 0),
                evidence_code=entry.doc_code,
                notes=f"Auto-drafted from documents. {entry.rationale or ''}".strip(),
            )
            session.add(item)
            created += 1
        session.add(AuditLog(
            case_id=case_id,
            action='INCOME_AUTO_APPLIED',
            entity='IncomeEntry',
            details=f'Auto-applied entries: created={created}, skipped={skipped}, replace_existing={payload.replace_existing}',
        ))
        session.commit()
        return {'ok': True, 'created': created, 'skipped': skipped}
    finally:
        session.close()


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
                   'amount_in_return': float(getattr(ie, 'amount_in_return', 0) or 0),
                   'tds_amount': float(getattr(ie, 'tds_amount', 0) or 0),
                   'evidence_code': getattr(ie, 'evidence_code', None),
                   'notes': getattr(ie, 'notes', None),
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
               source_name=(entry.source_name or entry.income_type),
               gross_amount=entry.amount,
               tds_amount=entry.tds_deducted,
               amount_in_return=entry.amount_in_return if entry.amount_in_return is not None else entry.amount,
               evidence_code=entry.evidence_code,
               notes=entry.notes,
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
       income_return_total = 0
       if hasattr(case, 'income_entries'):
           for ie in case.income_entries:
               gross_income += float(getattr(ie, 'gross_amount', 0) or 0)
               tds_total += float(getattr(ie, 'tds_amount', 0) or 0)
               income_return_total += float(getattr(ie, 'amount_in_return', 0) or 0)

       tax_credits = session.scalars(select(TaxCredit).where(TaxCredit.case_id == case_id)).all()
       tds_26as_total: Optional[float] = None
       tds_26as_source = "not_available"
       if tax_credits:
           tds_26as_total = sum(float(getattr(c, 'tax_amount_26as', 0) or 0) for c in tax_credits)
           tds_26as_source = "tax_credits_table"
       else:
           # Fallback: derive total TDS from uploaded Form 26AS documents if tax-credits table is not filled yet.
           try:
               docs = session.scalars(
                   select(DocumentRequirement).where(DocumentRequirement.case_id == case_id)
               ).all()
               target_docs = [d for d in docs if _doc_type_for_code(getattr(d, "code", "")) == "FORM_26AS"]
               evidence_map = _load_evidences_for_requirements(session, [d.id for d in target_docs]) if target_docs else {}
               parsed_totals: List[float] = []
               if target_docs:
                   from backend.app.document_parser import DocumentParserFactory, DocumentType
                   for doc in target_docs:
                       evidences = evidence_map.get(doc.id) or []
                       if not evidences:
                           continue
                       file_path = evidences[0].file_path
                       if not file_path:
                           continue
                       parsed = DocumentParserFactory.parse_document(file_path, DocumentType.FORM_26AS)
                       if parsed.success:
                           total_tds = float((parsed.extracted_data or {}).get("total_tds") or 0)
                           if total_tds > 0:
                               parsed_totals.append(total_tds)
               if parsed_totals:
                   tds_26as_total = sum(parsed_totals)
                   tds_26as_source = "parsed_form26as_document"
           except Exception:
               # keep not_available; we surface this explicitly in verification details
               pass

       tds_claimed_total = sum(float(getattr(c, 'tax_claimed', 0) or 0) for c in tax_credits) if tax_credits else tds_total

       income_variance = gross_income - income_return_total
       tds_variance = None if tds_26as_total is None else (tds_26as_total - tds_claimed_total)

       def _variance_status(delta: float) -> str:
           abs_delta = abs(delta)
           if abs_delta <= 1:
               return "matched"
           if abs_delta <= 100:
               return "minor_variance"
           return "variance"

       income_status = _variance_status(income_variance)
       tds_status = "missing_reference" if tds_variance is None else _variance_status(tds_variance)
        
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
               'total_tds_26as': tds_26as_total,
               'total_tds_claimed': tds_claimed_total,
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
               'income_matched': income_status == 'matched',
               'tds_matched': tds_status == 'matched',
               'calculations_verified': True,
               'ready_to_file': income_status in {'matched', 'minor_variance'} and tds_status in {'matched', 'minor_variance'},
           },
           'verification_details': {
               'income': {
                   'source_total': gross_income,
                   'itr_total': income_return_total,
                   'variance': income_variance,
                   'status': income_status,
                   'recommended_action': (
                       'No action needed'
                       if income_status == 'matched'
                       else 'Review income lines and align ITR amount with source docs'
                   ),
                   'action_steps': [
                       'Open Income page and compare each source row with document-backed gross amount.',
                       'If exempt income exists (e.g., NRE interest), move amount to exempt instead of taxable return amount.',
                       'If difference is rounding only (<= ₹100), keep note in reconciliation and proceed.',
                   ],
               },
               'tds': {
                   'as_per_26as': tds_26as_total,
                   'as_per_26as_source': tds_26as_source,
                   'claimed_in_case': tds_claimed_total,
                   'variance': tds_variance,
                   'status': tds_status,
                   'recommended_action': (
                       'No action needed'
                       if tds_status == 'matched'
                       else (
                           'Tax Credits is empty. Add/import deductor-wise 26AS credits in Tax Credits page.'
                           if tds_status == 'missing_reference'
                           else 'Reconcile deductor-wise TDS with Form 26AS before filing'
                       )
                   ),
                   'action_steps': [
                       'Open Tax Credits and compare deductor TAN-wise values with Form 26AS.',
                       'Update claimed TDS to match valid 26AS credits; do not over-claim.',
                       'If 26AS has not refreshed yet, keep evidence and re-check later before final submission.',
                   ],
               },
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


# ============================================================================
# FAMILY MEMBERS ENDPOINTS
# ============================================================================

def _oci_scheme_eligibility(citizenship: str, residential_status: str) -> dict:
    """Legacy wrapper — kept for backward compat; real logic is in run_scheme_eligibility_engine."""
    is_oci = (residential_status or '').upper() in ('OCI', 'OCI CARD HOLDER')
    is_foreign_citizen = citizenship and citizenship.strip().lower() not in ('india', 'indian')
    return {'is_oci': is_oci, 'is_foreign_citizen': is_foreign_citizen, 'eligible': [], 'ineligible': [], 'notes': []}


# ============================================================================
# SCHEME ELIGIBILITY ENGINE
# ============================================================================

from datetime import date as _date
import math as _math

SCHEME_DB = [
    # --- GIRL CHILD / DAUGHTER ---
    {
        'id': 'SSY', 'name': 'Sukanya Samriddhi Yojana (SSY)',
        'category': 'Savings / Girl Child',
        'description': 'High-interest government savings scheme for girl child, tax-free under 80C.',
        'benefit': 'Interest rate ~8.2% p.a., tax-free, up to ₹1.5L/yr deposit. 80C deduction for depositor.',
        'how_to_apply': "Post office or authorised bank. Account in girl's name, operated by parent.",
        'criteria': {'gender': 'female', 'max_age': 10, 'citizenship_required': True, 'oci_eligible': False},
        'authority': 'Ministry of Finance / India Post',
    },
    {
        'id': 'BBBP', 'name': 'Beti Bachao Beti Padhao (BBBP)',
        'category': 'Girl Child / Welfare',
        'description': 'National programme for girl child welfare, education and protection.',
        'benefit': 'Awareness, conditional cash transfers in some states, education support.',
        'how_to_apply': 'Through Anganwadi, district Women and Child Development office.',
        'criteria': {'gender': 'female', 'citizenship_required': True, 'oci_eligible': False},
        'authority': 'Ministry of Women & Child Development',
    },
    {
        'id': 'CBSE_MERIT', 'name': 'CBSE Merit Scholarship for Single Girl Child',
        'category': 'Scholarship / Education',
        'description': 'Scholarship for single girl child who passed Class X from CBSE with 60%+ marks.',
        'benefit': '₹500/month for Class XI-XII continuation.',
        'how_to_apply': 'Apply on CBSE scholarship portal after Class X results.',
        'criteria': {'gender': 'female', 'citizenship_required': True, 'oci_eligible': False, 'min_age': 15, 'max_age': 20},
        'authority': 'CBSE',
    },
    {
        'id': 'NSP_POST_MATRIC', 'name': 'National Scholarship Portal — Post-Matric',
        'category': 'Scholarship / Education',
        'description': 'Central government scholarship for students after Class X from minority/SC/ST/OBC/general categories.',
        'benefit': 'Up to ₹12,000/yr tuition + maintenance allowance.',
        'how_to_apply': 'scholarships.gov.in',
        'criteria': {'citizenship_required': True, 'oci_eligible': False, 'min_age': 15, 'max_age': 30},
        'authority': 'Ministry of Education / NSP',
    },
    {
        'id': 'AICTE_PG', 'name': 'AICTE PG Scholarship',
        'category': 'Scholarship / Education',
        'description': 'Scholarship for GATE/GPAT qualified students in AICTE-approved colleges.',
        'benefit': '₹12,400/month for M.Tech/M.Pharm students.',
        'how_to_apply': 'Through institution after GATE/GPAT qualification.',
        'criteria': {'citizenship_required': True, 'oci_eligible': False, 'min_age': 20, 'max_age': 35},
        'authority': 'AICTE',
    },
    # --- OCI / NRI ELIGIBLE ---
    {
        'id': 'OCI_ADMISSION', 'name': 'NRI/OCI Quota Admission — IITs, NITs, AIIMS, Central Universities',
        'category': 'Education / Admission',
        'description': 'Reserved NRI/OCI seats in premier institutions via JEE/NEET/university entrance.',
        'benefit': 'Access to IIT, NIT, AIIMS, IIM, BITS, and other top colleges under NRI/OCI quota.',
        'how_to_apply': 'Apply during regular JEE/NEET cycle — select NRI/OCI category.',
        'criteria': {'citizenship_required': False, 'oci_eligible': True, 'min_age': 16, 'max_age': 25},
        'authority': 'JoSAA / MCC / respective institutions',
    },
    {
        'id': 'OCI_PVTSCHOOL', 'name': 'School Admission — Treated at par with Indian nationals',
        'category': 'Education / Admission',
        'description': 'OCI children can be admitted to private schools on the same terms as Indian students (no PIO/NRI premium).',
        'benefit': 'Access to CBSE/ICSE/IB private schools at domestic fee rates.',
        'how_to_apply': 'Directly at school with OCI card + documents.',
        'criteria': {'citizenship_required': False, 'oci_eligible': True, 'max_age': 18},
        'authority': 'Ministry of Education notification',
    },
    {
        'id': 'AIF_SCHOLARSHIP', 'name': 'American India Foundation (AIF) Fellowship / Scholarships',
        'category': 'Private Scholarship',
        'description': 'US-based non-profit offering fellowships and scholarships for Indian-origin students.',
        'benefit': 'Varies — project-based fellowships, education grants.',
        'how_to_apply': 'aif.org — open to Indian-origin students globally.',
        'criteria': {'citizenship_required': False, 'oci_eligible': True},
        'authority': 'American India Foundation (private)',
    },
    {
        'id': 'AKF_SCHOLARSHIP', 'name': 'Aga Khan Foundation International Scholarship',
        'category': 'Private Scholarship',
        'description': 'Merit + need-based scholarship for students from developing countries pursuing postgrad.',
        'benefit': "Covers tuition + living expenses for master's programmes.",
        'how_to_apply': 'akdn.org/akf — annual application cycle.',
        'criteria': {'citizenship_required': False, 'oci_eligible': True, 'min_age': 18, 'max_age': 30},
        'authority': 'Aga Khan Foundation (private)',
    },
    {
        'id': 'OCI_STUDY_NOVISA', 'name': 'Right to Study/Live in India without Visa (OCI)',
        'category': 'OCI Rights',
        'description': 'OCI card holders can reside, study and work in India indefinitely without requiring a visa or residency permit.',
        'benefit': 'Lifelong multiple-entry visa equivalent. Parity with Indian nationals for most purposes except election voting, govt jobs.',
        'how_to_apply': 'OCI card obtained from Indian mission abroad.',
        'criteria': {'citizenship_required': False, 'oci_eligible': True},
        'authority': 'Ministry of Home Affairs',
    },
    {
        'id': 'OCI_PROPERTY', 'name': 'OCI — Right to acquire immovable property in India',
        'category': 'OCI Rights',
        'description': 'OCI holders can buy residential and commercial property in India (not agricultural land).',
        'benefit': 'Can own property in own name. No RBI permission needed.',
        'how_to_apply': 'Direct purchase through registered sale deed.',
        'criteria': {'citizenship_required': False, 'oci_eligible': True, 'min_age': 18},
        'authority': 'FEMA / Ministry of Home Affairs',
    },
    {
        'id': 'NRO_ACCOUNT', 'name': 'NRO Savings / FD Account',
        'category': 'Banking',
        'description': 'Non-Resident Ordinary account to receive and manage India-sourced income (rent, dividends, etc.).',
        'benefit': 'Earn interest on India funds. Interest taxable in India — TDS at 30%.',
        'how_to_apply': 'Any Indian bank with FEMA KYC documents.',
        'criteria': {'citizenship_required': False, 'oci_eligible': True, 'min_age': 18},
        'authority': 'RBI / FEMA',
    },
    # --- EDUCATION LOAN TAX ---
    {
        'id': 'SEC80E_PARENT', 'name': 'Section 80E — Education Loan Interest Deduction (for Parent)',
        'category': 'Tax Benefit',
        'description': 'Parent paying education loan EMI for child (incl. OCI child) can deduct interest from taxable income.',
        'benefit': 'Full interest deduction (no cap) for up to 8 years from start of repayment.',
        'how_to_apply': 'Loan from bank/approved institution. Claim in ITR of the parent paying the EMI.',
        'criteria': {'citizenship_required': False, 'oci_eligible': True, 'relationship': ['daughter', 'son']},
        'authority': 'Income Tax Act Section 80E',
    },
    # --- HEALTH ---
    {
        'id': 'PMJAY', 'name': 'PM Jan Arogya Yojana / Ayushman Bharat',
        'category': 'Health Insurance',
        'description': 'Government health insurance scheme providing ₹5L/year hospital coverage.',
        'benefit': '₹5 lakh per year free hospitalisation at empanelled hospitals.',
        'how_to_apply': 'pmjay.gov.in — based on SECC data or Ration Card/BPL list.',
        'criteria': {'citizenship_required': True, 'oci_eligible': False},
        'authority': 'National Health Authority',
    },
    {
        'id': 'SEC80D_PARENT', 'name': 'Section 80D — Health Insurance Premium Deduction (for Parent)',
        'category': 'Tax Benefit',
        'description': 'Parent paying health insurance premium for child can claim deduction even if child is OCI/NRI.',
        'benefit': '₹25,000 deduction per year (₹50,000 if parent is senior citizen).',
        'how_to_apply': 'Buy health insurance policy. Claim in ITR.',
        'criteria': {'citizenship_required': False, 'oci_eligible': True},
        'authority': 'Income Tax Act Section 80D',
    },
    # --- STATE-SPECIFIC (Gujarat) ---
    {
        'id': 'GJ_VIDYADEEP', 'name': 'Gujarat — Vidyadeep Yojana (State Scholarship)',
        'category': 'State Scholarship',
        'description': 'Gujarat state scholarship for meritorious students from economically weaker sections.',
        'benefit': 'Varies by category — tuition + stipend.',
        'how_to_apply': 'sje.gujarat.gov.in',
        'criteria': {'citizenship_required': True, 'oci_eligible': False, 'state': 'Gujarat'},
        'authority': 'Govt of Gujarat — Social Justice Dept',
    },
    {
        'id': 'GJ_KANYA_KELAVANI', 'name': 'Gujarat — Kanya Kelavani Nidhi',
        'category': 'State / Girl Child',
        'description': 'Gujarat scheme promoting girl child education.',
        'benefit': 'Conditional cash transfers to families enrolling daughters in school.',
        'how_to_apply': 'District primary education office.',
        'criteria': {'gender': 'female', 'citizenship_required': True, 'oci_eligible': False, 'max_age': 14},
        'authority': 'Govt of Gujarat — Education Dept',
    },
]


def run_scheme_eligibility_engine(profile: dict) -> dict:
    """
    Evaluate all schemes in SCHEME_DB against the family member profile.
    Returns categorised results: eligible, ineligible, partial, unknown.
    """
    citizenship = (profile.get('citizenship') or '').strip().lower()
    residential_status = (profile.get('residential_status') or '').strip().lower()
    relationship = (profile.get('relationship') or '').strip().lower()
    gender_guess = 'female' if relationship in ('daughter', 'mother', 'sister', 'mother-in-law') else (
        'male' if relationship in ('son', 'father', 'brother', 'father-in-law') else None)
    living_in_india = profile.get('living_in_india', True)
    currently_studying = profile.get('currently_studying', False)
    has_india_income = profile.get('has_india_income', False)

    is_indian_citizen = citizenship in ('india', 'indian', '')
    is_oci = 'oci' in residential_status
    is_nri = 'nri' in residential_status
    is_foreign_citizen = not is_indian_citizen

    # Calculate age
    dob = profile.get('date_of_birth')
    age = None
    if dob:
        try:
            dob_date = _date.fromisoformat(str(dob))
            today = _date.today()
            age = today.year - dob_date.year - ((today.month, today.day) < (dob_date.month, dob_date.day))
        except Exception:
            age = None

    eligible = []
    ineligible = []
    partial = []

    for scheme in SCHEME_DB:
        c = scheme['criteria']
        reasons_no = []
        reasons_partial = []

        # Citizenship check
        if c.get('citizenship_required') and is_foreign_citizen:
            if not (is_oci and c.get('oci_eligible')):
                reasons_no.append('Requires Indian citizenship — OCI/foreign national not eligible')

        # OCI specifically eligible
        if c.get('oci_eligible') is False and is_oci:
            reasons_no.append('OCI card holders explicitly excluded')

        # Gender check
        if c.get('gender') and gender_guess and c['gender'] != gender_guess:
            reasons_no.append(f"For {c['gender']}s only")

        # Age check
        if age is not None:
            if c.get('min_age') and age < c['min_age']:
                reasons_no.append(f"Minimum age {c['min_age']} (currently {age})")
            if c.get('max_age') and age > c['max_age']:
                reasons_no.append(f"Maximum age {c['max_age']} (currently {age})")
        else:
            if c.get('max_age') or c.get('min_age'):
                reasons_partial.append('Age not provided — cannot confirm age eligibility')

        # Relationship check (e.g. 80E needs to be child)
        if c.get('relationship'):
            if relationship not in [r.lower() for r in c['relationship']]:
                reasons_no.append(f"Applies to {', '.join(c['relationship'])} relationship only")

        entry = {
            'id': scheme['id'],
            'name': scheme['name'],
            'category': scheme['category'],
            'description': scheme['description'],
            'benefit': scheme['benefit'],
            'how_to_apply': scheme['how_to_apply'],
            'authority': scheme['authority'],
        }

        if reasons_no:
            entry['reasons'] = reasons_no
            ineligible.append(entry)
        elif reasons_partial:
            entry['reasons'] = reasons_partial
            partial.append(entry)
        else:
            eligible.append(entry)

    # Categorise eligible schemes
    categories = {}
    for s in eligible:
        categories.setdefault(s['category'], []).append(s)

    return {
        'eligible': eligible,
        'ineligible': ineligible,
        'partial': partial,
        'categories': list(categories.keys()),
        'summary': {
            'total_schemes_checked': len(SCHEME_DB),
            'eligible_count': len(eligible),
            'ineligible_count': len(ineligible),
            'needs_info_count': len(partial),
        },
        'profile_used': {
            'citizenship': profile.get('citizenship'),
            'residential_status': profile.get('residential_status'),
            'age': age,
            'gender_inferred': gender_guess,
            'is_oci': is_oci,
            'is_indian_citizen': is_indian_citizen,
        }
    }


def _tax_relevance_notes(relationship: str, citizenship: str, residential_status: str, has_india_income: bool) -> list:
    """Generate tax relevance notes for the family member."""
    notes = []
    rel = (relationship or '').lower()
    is_oci = (residential_status or '').upper() in ('OCI', 'OCI CARD HOLDER')
    is_foreign = citizenship and citizenship.strip().lower() not in ('india', 'indian')

    if rel == 'daughter' and is_oci:
        notes.append("Clubbing provisions (Sec 64): If minor daughter earns income, it clubs with parent's income. If she is 18+, income is independently taxable only if India-sourced.")
        notes.append("Education loan (Sec 80E): Nilesh/Avani can claim 80E deduction for interest on education loan taken for her studies — applies even for OCI child.")
        notes.append("No HUF inclusion: OCI card holders are NOT members of Hindu Undivided Family for tax purposes.")
    if has_india_income:
        notes.append("India-sourced income (rent, interest, salary) is taxable in India even for OCI/foreign citizens — ITR filing may be required if income exceeds basic exemption.")
        notes.append("TDS may be deducted on India income; Form 26AS should be linked to her PAN (if any).")
    if is_oci or is_foreign:
        notes.append("DTAA (India-US treaty): If she becomes a US tax resident in future, DTAA provisions will apply to avoid double taxation on India income.")

    return notes


@app.get('/api/family-members')
def get_family_members():
    if engine is None:
        return {'ok': False, 'error': 'Database not connected'}
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT * FROM family_members ORDER BY id")).mappings().all()
            members = [dict(r) for r in rows]
            for m in members:
                if m.get('date_of_birth'):
                    m['date_of_birth'] = str(m['date_of_birth'])
                if m.get('created_at'):
                    m['created_at'] = str(m['created_at'])
                if m.get('updated_at'):
                    m['updated_at'] = str(m['updated_at'])
            return {'ok': True, 'members': members}
    except Exception as e:
        logger.error(f"Error fetching family members: {e}")
        return {'ok': False, 'error': str(e)}


@app.post('/api/family-members')
async def add_family_member(request: Request):
    if engine is None:
        return {'ok': False, 'error': 'Database not connected'}
    try:
        data = await request.json()
        engine_result = run_scheme_eligibility_engine(data)
        tax_notes = _tax_relevance_notes(
            data.get('relationship', ''), data.get('citizenship', ''),
            data.get('residential_status', ''), data.get('has_india_income', False)
        )
        with engine.begin() as conn:
            result = conn.execute(text("""
                INSERT INTO family_members
                    (name, relationship, date_of_birth, citizenship, residential_status,
                     oci_card_last4, pan_last4, living_in_india, currently_studying,
                     institution_name, course_details, currently_working, employer_country,
                     has_india_income, india_income_notes, govt_scheme_eligibility,
                     tax_relevance_notes, notes)
                VALUES
                    (:name, :relationship, :dob, :citizenship, :residential_status,
                     :oci_card_last4, :pan_last4, :living_in_india, :currently_studying,
                     :institution_name, :course_details, :currently_working, :employer_country,
                     :has_india_income, :india_income_notes, :govt_scheme_eligibility,
                     :tax_relevance_notes, :notes)
                RETURNING id
            """), {
                'name': data.get('name', ''),
                'relationship': data.get('relationship', ''),
                'dob': data.get('date_of_birth') or None,
                'citizenship': data.get('citizenship', ''),
                'residential_status': data.get('residential_status', ''),
                'oci_card_last4': data.get('oci_card_last4', ''),
                'pan_last4': data.get('pan_last4', ''),
                'living_in_india': data.get('living_in_india', True),
                'currently_studying': data.get('currently_studying', False),
                'institution_name': data.get('institution_name', ''),
                'course_details': data.get('course_details', ''),
                'currently_working': data.get('currently_working', False),
                'employer_country': data.get('employer_country', ''),
                'has_india_income': data.get('has_india_income', False),
                'india_income_notes': data.get('india_income_notes', ''),
                'govt_scheme_eligibility': f"Engine checked {len(SCHEME_DB)} schemes. Eligible: {engine_result['summary']['eligible_count']}",
                'tax_relevance_notes': '\n'.join(tax_notes),
                'notes': data.get('notes', ''),
            })
            new_id = result.scalar()
        return {'ok': True, 'id': new_id, 'engine_result': engine_result, 'tax_notes': tax_notes}
    except Exception as e:
        logger.error(f"Error adding family member: {e}")
        return {'ok': False, 'error': str(e)}



@app.put('/api/family-members/{member_id}')
async def update_family_member(member_id: int, request: Request):
    if engine is None:
        return {'ok': False, 'error': 'Database not connected'}
    try:
        data = await request.json()
        engine_result = run_scheme_eligibility_engine(data)
        tax_notes = _tax_relevance_notes(
            data.get('relationship', ''), data.get('citizenship', ''),
            data.get('residential_status', ''), data.get('has_india_income', False)
        )
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE family_members SET
                    name = :name, relationship = :relationship, date_of_birth = :dob,
                    citizenship = :citizenship, residential_status = :residential_status,
                    oci_card_last4 = :oci_card_last4, pan_last4 = :pan_last4,
                    living_in_india = :living_in_india, currently_studying = :currently_studying,
                    institution_name = :institution_name, course_details = :course_details,
                    currently_working = :currently_working, employer_country = :employer_country,
                    has_india_income = :has_india_income, india_income_notes = :india_income_notes,
                    govt_scheme_eligibility = :govt_scheme_eligibility,
                    tax_relevance_notes = :tax_relevance_notes, notes = :notes,
                    updated_at = NOW()
                WHERE id = :id
            """), {
                'id': member_id,
                'name': data.get('name', ''),
                'relationship': data.get('relationship', ''),
                'dob': data.get('date_of_birth') or None,
                'citizenship': data.get('citizenship', ''),
                'residential_status': data.get('residential_status', ''),
                'oci_card_last4': data.get('oci_card_last4', ''),
                'pan_last4': data.get('pan_last4', ''),
                'living_in_india': data.get('living_in_india', True),
                'currently_studying': data.get('currently_studying', False),
                'institution_name': data.get('institution_name', ''),
                'course_details': data.get('course_details', ''),
                'currently_working': data.get('currently_working', False),
                'employer_country': data.get('employer_country', ''),
                'has_india_income': data.get('has_india_income', False),
                'india_income_notes': data.get('india_income_notes', ''),
                'govt_scheme_eligibility': f"Engine checked {len(SCHEME_DB)} schemes. Eligible: {engine_result['summary']['eligible_count']}",
                'tax_relevance_notes': '\n'.join(tax_notes),
                'notes': data.get('notes', ''),
            })
        return {'ok': True, 'engine_result': engine_result, 'tax_notes': tax_notes}
    except Exception as e:
        logger.error(f"Error updating family member: {e}")
        return {'ok': False, 'error': str(e)}



@app.delete('/api/family-members/{member_id}')
def delete_family_member(member_id: int):
    if engine is None:
        return {'ok': False, 'error': 'Database not connected'}
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM family_members WHERE id = :id"), {'id': member_id})
        return {'ok': True}
    except Exception as e:
        logger.error(f"Error deleting family member: {e}")
        return {'ok': False, 'error': str(e)}


@app.get('/api/family-members/{member_id}/scheme-check')
def check_scheme_eligibility(member_id: int):
    """Run eligibility engine against saved profile of a member."""
    if engine is None:
        return {'ok': False, 'error': 'Database not connected'}
    try:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM family_members WHERE id = :id"), {'id': member_id}).mappings().first()
            if not row:
                return {'ok': False, 'error': 'Member not found'}
        m = dict(row)
        engine_result = run_scheme_eligibility_engine(m)
        tax_notes = _tax_relevance_notes(
            m.get('relationship', ''), m.get('citizenship', ''),
            m.get('residential_status', ''), m.get('has_india_income', False)
        )
        return {'ok': True, 'member': m['name'], 'engine_result': engine_result, 'tax_notes': tax_notes}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


@app.post('/api/scheme-eligibility/check')
async def check_scheme_eligibility_adhoc(request: Request):
    """Run eligibility engine on an ad-hoc profile (no DB record needed)."""
    try:
        profile = await request.json()
        engine_result = run_scheme_eligibility_engine(profile)
        tax_notes = _tax_relevance_notes(
            profile.get('relationship', ''), profile.get('citizenship', ''),
            profile.get('residential_status', ''), profile.get('has_india_income', False)
        )
        return {'ok': True, 'engine_result': engine_result, 'tax_notes': tax_notes}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


@app.get('/api/scheme-eligibility/schemes')
def list_all_schemes():
    """Return the full scheme database."""
    return {'ok': True, 'schemes': SCHEME_DB, 'total': len(SCHEME_DB)}
