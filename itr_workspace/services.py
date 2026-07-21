from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Iterable

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import DATA_DIR
from .models import (
    AuditLog, DocumentRequirement, IncomeEntry, PropertyLoan, ReconciliationItem,
    ResidencyRecord, Task, TaxCase, TaxCredit, Taxpayer
)


@dataclass
class ReviewCheck:
    severity: str
    area: str
    message: str


def log(session: Session, case_id: int | None, action: str, entity: str, details: str = ""):
    session.add(AuditLog(case_id=case_id, action=action, entity=entity, details=details))


def progress(session: Session, case_id: int) -> dict:
    docs = session.scalars(
        select(DocumentRequirement).where(DocumentRequirement.case_id == case_id)
    ).all()
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


def save_upload(case: TaxCase, taxpayer: Taxpayer, req: DocumentRequirement, uploaded_file) -> str:
    safe_name = Path(uploaded_file.name).name
    digest = hashlib.sha256(uploaded_file.getvalue()).hexdigest()[:12]
    folder = DATA_DIR / case.assessment_year / taxpayer.name.replace(" ", "_") / req.category.replace(" ", "_")
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{req.code}__{digest}__{safe_name}"
    target.write_bytes(uploaded_file.getvalue())
    return str(target)


def money(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(Decimal("0.01"))


def review_checks(session: Session, case: TaxCase) -> list[ReviewCheck]:
    checks: list[ReviewCheck] = []
    docs = session.scalars(
        select(DocumentRequirement).where(DocumentRequirement.case_id == case.id)
    ).all()
    missing = [d.title for d in docs if d.required and d.status == "Missing"]
    if missing:
        checks.append(ReviewCheck("BLOCK", "Documents", f"{len(missing)} required documents are still missing."))

    residency = session.scalar(select(ResidencyRecord).where(ResidencyRecord.case_id == case.id))
    if not residency or residency.days_in_india_current_fy is None:
        checks.append(ReviewCheck("BLOCK", "Residency", "Current-FY India presence days have not been entered."))
    elif residency.conclusion and residency.conclusion != case.residential_status:
        checks.append(ReviewCheck(
            "BLOCK", "Residency",
            f"Residency worksheet concludes {residency.conclusion}, but case is set to {case.residential_status}."
        ))

    incomes = session.scalars(select(IncomeEntry).where(IncomeEntry.case_id == case.id)).all()
    for i in incomes:
        if money(i.amount_in_return) == 0 and money(i.gross_amount) > 0 and money(i.exempt_amount) == 0:
            checks.append(ReviewCheck(
                "WARN", "Income",
                f"{i.source_name}: gross income exists but return amount and exempt amount are both zero."
            ))
        if money(i.tds_amount) > money(i.gross_amount):
            checks.append(ReviewCheck("BLOCK", "Income", f"{i.source_name}: TDS exceeds gross income."))

    credits = session.scalars(select(TaxCredit).where(TaxCredit.case_id == case.id)).all()
    for c in credits:
        if abs(money(c.tax_amount_26as) - money(c.tax_claimed)) > Decimal("1.00"):
            checks.append(ReviewCheck(
                "WARN", "Tax credit",
                f"{c.deductor}: 26AS tax and claimed tax differ by ₹{abs(money(c.tax_amount_26as)-money(c.tax_claimed)):,.2f}."
            ))

    recs = session.scalars(select(ReconciliationItem).where(ReconciliationItem.case_id == case.id)).all()
    for r in recs:
        delta1 = abs(money(r.source_amount) - money(r.ais_26as_amount))
        delta2 = abs(money(r.source_amount) - money(r.return_amount))
        if r.status != "Resolved" and max(delta1, delta2) > Decimal("1.00"):
            checks.append(ReviewCheck(
                "BLOCK", "Reconciliation",
                f"{r.category}/{r.source}: unresolved difference up to ₹{max(delta1, delta2):,.2f}."
            ))

    loans = session.scalars(select(PropertyLoan).where(PropertyLoan.case_id == case.id)).all()
    for p in loans:
        if p.ownership_percent > 0 and p.actual_payment_percent == 0:
            checks.append(ReviewCheck(
                "WARN", "House property",
                f"{p.property_name}: ownership entered but actual EMI/payment share is zero."
            ))
        if p.possession_date is None and money(p.interest_fy) > 0:
            checks.append(ReviewCheck(
                "WARN", "House property",
                f"{p.property_name}: possession date is blank; review whether interest is pre-construction."
            ))

    if case.residential_status in {"NRI", "RNOR"} and case.return_form == "ITR-1":
        checks.append(ReviewCheck("BLOCK", "Return form", "ITR-1 is not appropriate for NRI/RNOR status."))

    if not checks:
        checks.append(ReviewCheck("OK", "Review", "No automated exceptions found. Manual tax review is still required."))
    return checks


def export_case(session: Session, case: TaxCase, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    taxpayer = session.get(Taxpayer, case.taxpayer_id)

    tables = {
        "documents": DocumentRequirement,
        "tasks": Task,
        "residency": ResidencyRecord,
        "income": IncomeEntry,
        "tax_credits": TaxCredit,
        "reconciliation": ReconciliationItem,
        "property_loans": PropertyLoan,
    }
    manifest = {
        "taxpayer": taxpayer.name,
        "pan_last4": taxpayer.pan_last4,
        "assessment_year": case.assessment_year,
        "financial_year": case.financial_year,
        "residential_status": case.residential_status,
        "return_form": case.return_form,
        "tax_regime": case.tax_regime,
        "case_status": case.case_status,
        "automated_review": [asdict(c) for c in review_checks(session, case)],
    }

    for name, model in tables.items():
        rows = session.scalars(select(model).where(model.case_id == case.id)).all()
        serial = []
        for row in rows:
            item = {}
            for col in row.__table__.columns:
                value = getattr(row, col.name)
                if isinstance(value, Decimal):
                    value = float(value)
                elif hasattr(value, "isoformat"):
                    value = value.isoformat()
                item[col.name] = value
            serial.append(item)
        pd.DataFrame(serial).to_csv(destination / f"{name}.csv", index=False)

    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return destination
