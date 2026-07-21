from __future__ import annotations

from sqlalchemy import select

from .db import Base, engine, session_scope
from .models import BankAccount, DocumentRequirement, ResidencyRecord, Task, TaxCase, Taxpayer
from .services import log


COMMON_DOCS = [
    ("ID_PAN", "Identity", "PAN record / profile verification", None, True),
    ("ID_PASSPORT", "Identity", "Passport and immigration stamps", None, True),
    ("PORTAL_AIS", "Tax portal", "Annual Information Statement (AIS PDF/JSON)", "Income Tax Portal", True),
    ("PORTAL_TIS", "Tax portal", "Taxpayer Information Summary (TIS)", "Income Tax Portal", True),
    ("PORTAL_26AS", "Tax portal", "Form 26AS", "TRACES / Income Tax Portal", True),
    ("PRIOR_ITR", "Prior year", "Previous ITR, computation and 143(1)", "Income Tax Portal", False),
    ("TRAVEL_WORKING", "Residency", "Travel-day calculation and supporting itinerary", None, True),
    ("MF_CAS", "Investments", "Mutual fund consolidated account statement", "CAMS/KFintech/Depository", True),
    ("MF_CG", "Investments", "Mutual fund capital-gains report confirming redemptions/switches", "AMC/Platform", True),
    ("HOUSE_DEED", "House property", "Sale deed / ownership document", None, True),
    ("HOUSE_POSSESSION", "House property", "Possession/completion/occupancy evidence", None, True),
    ("LOAN_CERT", "House property", "FY home-loan interest and principal certificate", "Lender", True),
    ("LOAN_STATEMENT", "House property", "Home-loan account statement and EMI evidence", "Lender", True),
]

NILESH_DOCS = [
    ("HDFC_NRE_STMT", "Banking", "HDFC NRE full-year statement", "HDFC Bank", True),
    ("HDFC_NRE_INT", "Banking", "HDFC NRE interest certificate", "HDFC Bank", True),
    ("HDFC_NRO_STMT", "Banking", "HDFC NRO full-year statement", "HDFC Bank", True),
    ("HDFC_NRO_INT", "Banking", "HDFC NRO interest certificate and Form 16A", "HDFC Bank", True),
    ("BOB_NRE_STMT", "Banking", "Bank of Baroda NRE full-year statement", "Bank of Baroda", True),
    ("BOB_NRE_INT", "Banking", "Bank of Baroda NRE interest certificate", "Bank of Baroda", True),
    ("BOB_NRO_STMT", "Banking", "Bank of Baroda NRO full-year statement", "Bank of Baroda", True),
    ("BOB_NRO_INT", "Banking", "Bank of Baroda NRO interest certificate and Form 16A", "Bank of Baroda", True),
    ("ZERODHA_DIV", "Investments", "Zerodha dividend statement", "Zerodha", True),
    ("ZERODHA_TAXPL", "Investments", "Zerodha Tax P&L / capital-gains report", "Zerodha", True),
    ("ZERODHA_LEDGER", "Investments", "Zerodha ledger and holdings as of 31 March", "Zerodha", True),
]

AVANI_DOCS = [
    ("HDFC_SAV_STMT", "Banking", "HDFC regular savings full-year statement", "HDFC Bank", True),
    ("HDFC_SAV_INT", "Banking", "HDFC savings/FD interest certificate and Form 16A", "HDFC Bank", True),
    ("BOB_NRO_STMT", "Banking", "Bank of Baroda NRO full-year statement", "Bank of Baroda", True),
    ("BOB_NRO_INT", "Banking", "Bank of Baroda NRO interest certificate and Form 16A", "Bank of Baroda", True),
    ("FOREIGN_INCOME", "Foreign income", "Foreign salary, interest, dividend and gains statements", None, True),
    ("FOREIGN_RECEIPT", "Foreign income", "Evidence of first receipt location and India remittances", None, True),
    ("FOREIGN_RETIREMENT", "Foreign income", "401(k), IRA/Roth IRA and HSA annual statements", None, False),
]

TASKS = [
    ("PROFILE", "Setup", "Verify profile, PAN suffix and bank refund account", True),
    ("RESIDENCY", "Residency", "Complete day-count and status review", True),
    ("DOCS", "Collection", "Collect and verify required documents", True),
    ("BANK_RECON", "Reconciliation", "Reconcile bank interest to AIS and 26AS", True),
    ("DIV_RECON", "Reconciliation", "Reconcile Zerodha gross dividends, bank credits and AIS", True),
    ("MF_REVIEW", "Investments", "Confirm no MF redemption, switch, STP or IDCW was missed", True),
    ("HOUSE_REVIEW", "House property", "Confirm possession, ownership and actual EMI payment shares", True),
    ("REGIME", "Tax", "Compare old and new tax regimes using verified amounts", True),
    ("FORM", "Return", "Confirm correct ITR form and schedules", True),
    ("PORTAL_VALIDATE", "Filing", "Validate in official portal/offline utility", True),
    ("FILE_VERIFY", "Filing", "File, e-verify and save acknowledgement/143(1)", True),
]


def get_or_create_taxpayer(session, name: str, status: str):
    taxpayer = session.scalar(select(Taxpayer).where(Taxpayer.name == name))
    if not taxpayer:
        taxpayer = Taxpayer(name=name, citizenship="Indian")
        session.add(taxpayer)
        session.flush()

    case = session.scalar(
        select(TaxCase).where(
            TaxCase.taxpayer_id == taxpayer.id,
            TaxCase.assessment_year == "2026-27",
        )
    )
    if not case:
        case = TaxCase(
            taxpayer_id=taxpayer.id,
            assessment_year="2026-27",
            financial_year="2025-26",
            residential_status=status,
            return_form="ITR-2",
        )
        session.add(case)
        session.flush()
        session.add(ResidencyRecord(case_id=case.id, conclusion=status))
    return taxpayer, case


def seed():
    Base.metadata.create_all(engine)
    with session_scope() as session:
        nilesh, n_case = get_or_create_taxpayer(session, "Nilesh", "NRI")
        avani, a_case = get_or_create_taxpayer(session, "Avani", "RNOR")

        # Ensure Avani's dependent child is recorded correctly: Daughter lives in India on OCI
        # This will set the taxpayer record to reflect dependent child residency and citizenship
        try:
            avani.has_dependent_child = True
            avani.dependent_child_name = avani.dependent_child_name or "Daughter"
            avani.dependent_child_age = avani.dependent_child_age or 5.5
            # Daughter resides in India on OCI
            avani.dependent_child_country_of_residence = "India"
            avani.dependent_child_citizenship = "US (OCI)"
            session.add(avani)
            session.flush()
        except Exception:
            # Non-fatal: seed continues even if updating dependent fields fails
            pass

        accounts = [
            (nilesh.id, "HDFC Bank", "NRE"),
            (nilesh.id, "HDFC Bank", "NRO"),
            (nilesh.id, "Bank of Baroda", "NRE"),
            (nilesh.id, "Bank of Baroda", "NRO"),
            (nilesh.id, "Zerodha", "Brokerage"),
            (avani.id, "HDFC Bank", "Regular Savings"),
            (avani.id, "Bank of Baroda", "NRO"),
        ]
        for taxpayer_id, bank, kind in accounts:
            exists = session.scalar(select(BankAccount).where(
                BankAccount.taxpayer_id == taxpayer_id,
                BankAccount.bank_name == bank,
                BankAccount.account_type == kind,
            ))
            if not exists:
                session.add(BankAccount(
                    taxpayer_id=taxpayer_id, bank_name=bank, account_type=kind
                ))

        for case, specific in [(n_case, NILESH_DOCS), (a_case, AVANI_DOCS)]:
            for code, category, title, institution, required in COMMON_DOCS + specific:
                exists = session.scalar(select(DocumentRequirement).where(
                    DocumentRequirement.case_id == case.id,
                    DocumentRequirement.code == code,
                ))
                if not exists:
                    session.add(DocumentRequirement(
                        case_id=case.id, code=code, category=category, title=title,
                        institution=institution, required=required,
                        source_period="01-Apr-2025 to 31-Mar-2026",
                    ))
            for code, phase, title, blocking in TASKS:
                exists = session.scalar(select(Task).where(
                    Task.case_id == case.id, Task.code == code
                ))
                if not exists:
                    session.add(Task(
                        case_id=case.id, code=code, phase=phase, title=title,
                        blocking=blocking
                    ))
            log(session, case.id, "SEED", "TaxCase", "Initial tailored checklist created.")

    print("Database initialized and tailored AY 2026-27 cases seeded.")


if __name__ == "__main__":
    seed()
