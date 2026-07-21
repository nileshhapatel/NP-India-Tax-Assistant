from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
import shutil
import tempfile
import zipfile

import pandas as pd
import streamlit as st
from sqlalchemy import select

from itr_workspace.db import Base, engine, session_scope
from itr_workspace.models import (
    AuditLog, BankAccount, DocumentRequirement, IncomeEntry, PropertyLoan,
    ReconciliationItem, ResidencyRecord, Task, TaxCase, TaxCredit, Taxpayer
)
from itr_workspace.services import export_case, log, progress, review_checks, save_upload

st.set_page_config(page_title="Family ITR Workspace", page_icon="₹", layout="wide")
Base.metadata.create_all(engine)

STATUS_DOC = ["Missing", "Requested", "Received", "Verified", "Not applicable"]
STATUS_TASK = ["Not started", "In progress", "Waiting", "Complete", "Not applicable"]


def rerun():
    st.rerun()


def case_picker(session):
    cases = session.scalars(
        select(TaxCase).order_by(TaxCase.assessment_year.desc(), TaxCase.taxpayer_id)
    ).all()
    if not cases:
        st.error("No cases found. Run: python -m itr_workspace.seed")
        st.stop()
    labels = {}
    for c in cases:
        t = session.get(Taxpayer, c.taxpayer_id)
        labels[c.id] = f"{t.name} — AY {c.assessment_year} — {c.residential_status}"
    case_id = st.sidebar.selectbox("Tax case", list(labels), format_func=labels.get)
    case = session.get(TaxCase, case_id)
    taxpayer = session.get(Taxpayer, case.taxpayer_id)
    return taxpayer, case


def money_input(label, value=0.0, key=None):
    return st.number_input(label, min_value=0.0, value=float(value or 0), step=100.0, format="%.2f", key=key)


with session_scope() as session:
    taxpayer, case = case_picker(session)
    page = st.sidebar.radio(
        "Workspace",
        ["Dashboard", "Profile", "Residency", "Documents", "Income", "Tax credits",
         "Reconciliation", "Property & loan", "Tasks", "Review", "Export", "History"]
    )

    st.title("₹ Family ITR Workspace")
    st.caption(f"{taxpayer.name} · FY {case.financial_year} · AY {case.assessment_year} · {case.residential_status}")

    if page == "Dashboard":
        p = progress(session, case.id)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Overall progress", f"{p['overall']}%")
        c2.metric("Documents", f"{p['documents']}%")
        c3.metric("Missing required", p["missing_required"])
        c4.metric("Open tasks", p["open_tasks"])
        st.progress(p["overall"] / 100)

        docs = session.scalars(select(DocumentRequirement).where(
            DocumentRequirement.case_id == case.id
        )).all()
        df = pd.DataFrame([{
            "Category": d.category, "Document": d.title, "Institution": d.institution,
            "Required": d.required, "Status": d.status
        } for d in docs])
        if not df.empty:
            st.subheader("Collection status")
            st.dataframe(
                df.groupby(["Category", "Status"]).size().reset_index(name="Count"),
                use_container_width=True, hide_index=True
            )

        checks = review_checks(session, case)
        st.subheader("Current exceptions")
        for chk in checks[:8]:
            fn = st.error if chk.severity == "BLOCK" else st.warning if chk.severity == "WARN" else st.success
            fn(f"**{chk.area}:** {chk.message}")

    elif page == "Profile":
        with st.form("profile"):
            name = st.text_input("Name", taxpayer.name)
            pan4 = st.text_input("PAN last 4 only", taxpayer.pan_last4 or "", max_chars=4)
            status = st.selectbox("Residential status", ["NRI", "RNOR", "ROR"], index=["NRI","RNOR","ROR"].index(case.residential_status))
            form = st.selectbox("Expected return form", ["ITR-2", "ITR-3", "Needs review"], index=["ITR-2","ITR-3","Needs review"].index(case.return_form if case.return_form in ["ITR-2","ITR-3","Needs review"] else "Needs review"))
            regime = st.selectbox("Tax regime", ["Undecided", "New", "Old"], index=["Undecided","New","Old"].index(case.tax_regime))
            case_status = st.selectbox("Case status", ["Collecting", "Reconciling", "Ready for review", "Filed", "Verified"])
            notes = st.text_area("Notes", case.notes or "")
            if st.form_submit_button("Save profile"):
                taxpayer.name, taxpayer.pan_last4 = name, pan4.upper() or None
                case.residential_status, case.return_form = status, form
                case.tax_regime, case.case_status, case.notes = regime, case_status, notes
                log(session, case.id, "UPDATE", "Profile", "Profile and case settings updated.")
                st.success("Saved.")

        st.subheader("Start another assessment year")
        new_ay = st.text_input("Assessment year, e.g. 2027-28")
        new_fy = st.text_input("Financial year, e.g. 2026-27")
        if st.button("Create year from this checklist"):
            if not new_ay or not new_fy:
                st.error("Enter both years.")
            else:
                existing = session.scalar(select(TaxCase).where(
                    TaxCase.taxpayer_id == taxpayer.id, TaxCase.assessment_year == new_ay
                ))
                if existing:
                    st.warning("That case already exists.")
                else:
                    nc = TaxCase(
                        taxpayer_id=taxpayer.id, assessment_year=new_ay,
                        financial_year=new_fy, residential_status=case.residential_status,
                        return_form="ITR-2"
                    )
                    session.add(nc); session.flush()
                    session.add(ResidencyRecord(case_id=nc.id))
                    old_docs = session.scalars(select(DocumentRequirement).where(DocumentRequirement.case_id == case.id)).all()
                    for d in old_docs:
                        session.add(DocumentRequirement(
                            case_id=nc.id, code=d.code, category=d.category, title=d.title,
                            institution=d.institution, required=d.required, source_period=new_fy
                        ))
                    old_tasks = session.scalars(select(Task).where(Task.case_id == case.id)).all()
                    for t in old_tasks:
                        session.add(Task(case_id=nc.id, code=t.code, phase=t.phase, title=t.title, blocking=t.blocking))
                    log(session, nc.id, "CREATE", "TaxCase", f"Created from AY {case.assessment_year} structure.")
                    st.success("New year created.")

    elif page == "Residency":
        r = session.scalar(select(ResidencyRecord).where(ResidencyRecord.case_id == case.id))
        if not r:
            r = ResidencyRecord(case_id=case.id); session.add(r); session.flush()
        with st.form("residency"):
            current = st.number_input("Days in India during current FY", 0, 366, r.days_in_india_current_fy or 0)
            prior4 = st.number_input("Days in India during preceding 4 FYs", 0, 1461, r.days_in_india_prior_4y or 0)
            prior7 = st.number_input("Days in India during preceding 7 FYs", 0, 2557, r.days_in_india_prior_7y or 0)
            nr10 = st.number_input("Number of non-resident years in preceding 10 FYs", 0, 10, r.nonresident_years_prior_10y or 0)
            returned = st.date_input("Date returned to India (leave today as placeholder only if applicable)", value=r.date_returned_to_india or date.today())
            foreign_receipt = st.checkbox("Foreign income first received directly in India", r.foreign_income_received_in_india)
            controlled = st.checkbox("Business controlled/profession set up in India", r.business_controlled_from_india)
            conclusion = st.selectbox("Reviewed conclusion", ["", "NRI", "RNOR", "ROR"], index=["", "NRI", "RNOR", "ROR"].index(r.conclusion or ""))
            reviewer = st.text_input("Reviewed by", r.reviewed_by or "")
            notes = st.text_area("Travel/status notes", r.notes or "")
            if st.form_submit_button("Save residency worksheet"):
                r.days_in_india_current_fy = current
                r.days_in_india_prior_4y = prior4
                r.days_in_india_prior_7y = prior7
                r.nonresident_years_prior_10y = nr10
                r.date_returned_to_india = returned
                r.foreign_income_received_in_india = foreign_receipt
                r.business_controlled_from_india = controlled
                r.conclusion = conclusion or None
                r.reviewed_by = reviewer or None
                r.notes = notes
                log(session, case.id, "UPDATE", "ResidencyRecord", "Residency worksheet updated.")
                st.success("Saved.")
        st.info("The app records evidence and flags inconsistencies. It deliberately does not auto-decide residency because citizenship, visit purpose, Indian income and special statutory rules may alter the day-count test.")

    elif page == "Documents":
        docs = session.scalars(select(DocumentRequirement).where(
            DocumentRequirement.case_id == case.id
        ).order_by(DocumentRequirement.category, DocumentRequirement.title)).all()
        category = st.selectbox("Category", ["All"] + sorted({d.category for d in docs}))
        shown = docs if category == "All" else [d for d in docs if d.category == category]
        for d in shown:
            with st.expander(f"{'✅' if d.status in ['Verified','Not applicable'] else '📄'} {d.title} — {d.status}"):
                c1, c2 = st.columns([1, 2])
                new_status = c1.selectbox("Status", STATUS_DOC, index=STATUS_DOC.index(d.status), key=f"ds{d.id}")
                notes = c2.text_input("Notes", d.notes or "", key=f"dn{d.id}")
                upload = st.file_uploader("Upload evidence", key=f"du{d.id}")
                if st.button("Save", key=f"db{d.id}"):
                    d.status, d.notes = new_status, notes
                    if upload:
                        d.file_path = save_upload(case, taxpayer, d, upload)
                        if d.status in {"Missing", "Requested"}:
                            d.status = "Received"
                    log(session, case.id, "UPDATE", "DocumentRequirement", f"{d.code}: {d.status}")
                    st.success("Saved.")
                    rerun()
                if d.file_path:
                    st.caption(f"Stored locally: {d.file_path}")

    elif page == "Income":
        st.subheader("Add income entry")
        with st.form("income_add"):
            kind = st.selectbox("Income type", ["NRO interest", "NRE interest (review exemption)", "Dividend", "MF IDCW", "House property", "Foreign income", "Other"])
            source = st.text_input("Source / institution")
            gross = money_input("Gross amount before TDS")
            tds = money_input("TDS")
            return_amt = money_input("Amount included in return")
            exempt = money_input("Exempt amount")
            evidence = st.text_input("Evidence code, e.g. ZERODHA_DIV")
            notes = st.text_area("Notes")
            if st.form_submit_button("Add income"):
                session.add(IncomeEntry(
                    case_id=case.id, income_type=kind, source_name=source,
                    gross_amount=gross, tds_amount=tds, amount_in_return=return_amt,
                    exempt_amount=exempt, evidence_code=evidence or None, notes=notes
                ))
                log(session, case.id, "CREATE", "IncomeEntry", f"{kind}: {source}")
                st.success("Added.")

        rows = session.scalars(select(IncomeEntry).where(IncomeEntry.case_id == case.id).order_by(IncomeEntry.id)).all()
        st.subheader("Income register")
        if rows:
            edited = st.data_editor(pd.DataFrame([{
                "ID": r.id, "Type": r.income_type, "Source": r.source_name,
                "Gross": float(r.gross_amount), "TDS": float(r.tds_amount),
                "Return amount": float(r.amount_in_return), "Exempt": float(r.exempt_amount),
                "Evidence": r.evidence_code or "", "Notes": r.notes or ""
            } for r in rows]), disabled=["ID"], use_container_width=True, hide_index=True)
            if st.button("Save income edits"):
                byid = {r.id:r for r in rows}
                for _, x in edited.iterrows():
                    r=byid[int(x["ID"])]
                    r.income_type=x["Type"]; r.source_name=x["Source"]
                    r.gross_amount=Decimal(str(x["Gross"])); r.tds_amount=Decimal(str(x["TDS"]))
                    r.amount_in_return=Decimal(str(x["Return amount"])); r.exempt_amount=Decimal(str(x["Exempt"]))
                    r.evidence_code=x["Evidence"] or None; r.notes=x["Notes"]
                log(session, case.id, "UPDATE", "IncomeEntry", "Income register edited.")
                st.success("Saved.")

    elif page == "Tax credits":
        with st.form("credit_add"):
            deductor = st.text_input("Deductor")
            ctype = st.selectbox("Credit type", ["TDS", "TCS", "Advance tax", "Self-assessment tax"])
            section = st.text_input("Section code")
            gross26 = money_input("Gross amount in 26AS")
            tax26 = money_input("Tax in 26AS")
            claimed = money_input("Tax claimed in return")
            if st.form_submit_button("Add credit"):
                session.add(TaxCredit(case_id=case.id, deductor=deductor, credit_type=ctype,
                    section_code=section or None, gross_amount_26as=gross26,
                    tax_amount_26as=tax26, tax_claimed=claimed))
                log(session, case.id, "CREATE", "TaxCredit", deductor)
                st.success("Added.")
        rows = session.scalars(select(TaxCredit).where(TaxCredit.case_id == case.id)).all()
        if rows:
            st.dataframe(pd.DataFrame([{
                "Deductor":r.deductor, "Type":r.credit_type, "Section":r.section_code,
                "Gross 26AS":float(r.gross_amount_26as), "Tax 26AS":float(r.tax_amount_26as),
                "Claimed":float(r.tax_claimed), "Difference":float(r.tax_amount_26as-r.tax_claimed)
            } for r in rows]), use_container_width=True, hide_index=True)

    elif page == "Reconciliation":
        with st.form("recon_add"):
            cat = st.selectbox("Category", ["Bank interest", "Dividend", "MF transaction", "Tax credit", "House property", "Other"])
            source = st.text_input("Source")
            source_amt = money_input("Primary source amount")
            ais_amt = money_input("AIS / 26AS amount")
            return_amt = money_input("Return amount")
            explanation = st.text_area("Explanation")
            if st.form_submit_button("Add reconciliation"):
                status = "Resolved" if max(abs(source_amt-ais_amt), abs(source_amt-return_amt)) <= 1 else "Open"
                session.add(ReconciliationItem(case_id=case.id, category=cat, source=source,
                    source_amount=source_amt, ais_26as_amount=ais_amt, return_amount=return_amt,
                    status=status, explanation=explanation))
                log(session, case.id, "CREATE", "ReconciliationItem", f"{cat}: {source}")
                st.success("Added.")
        rows = session.scalars(select(ReconciliationItem).where(ReconciliationItem.case_id == case.id)).all()
        if rows:
            df=pd.DataFrame([{
                "ID":r.id,"Category":r.category,"Source":r.source,
                "Primary":float(r.source_amount),"AIS/26AS":float(r.ais_26as_amount),
                "Return":float(r.return_amount),
                "Max difference":float(max(abs(r.source_amount-r.ais_26as_amount),abs(r.source_amount-r.return_amount))),
                "Status":r.status,"Explanation":r.explanation or ""
            } for r in rows])
            edited=st.data_editor(df, disabled=["ID","Max difference"], use_container_width=True, hide_index=True)
            if st.button("Save reconciliation edits"):
                byid={r.id:r for r in rows}
                for _,x in edited.iterrows():
                    r=byid[int(x["ID"])]
                    r.category=x["Category"];r.source=x["Source"]
                    r.source_amount=Decimal(str(x["Primary"]));r.ais_26as_amount=Decimal(str(x["AIS/26AS"]))
                    r.return_amount=Decimal(str(x["Return"]));r.status=x["Status"];r.explanation=x["Explanation"]
                log(session,case.id,"UPDATE","ReconciliationItem","Reconciliation register edited.")
                st.success("Saved.")

    elif page == "Property & loan":
        loans = session.scalars(select(PropertyLoan).where(PropertyLoan.case_id == case.id)).all()
        p = loans[0] if loans else None
        with st.form("loan"):
            name=st.text_input("Property name", p.property_name if p else "Primary house")
            address=st.text_area("Address", p.property_address if p else "")
            ownership=money_input("Legal ownership %", p.ownership_percent if p else 0)
            payment=money_input("Actual EMI/payment contribution %", p.actual_payment_percent if p else 0)
            selfocc=st.checkbox("Self occupied", p.self_occupied if p else True)
            possession=st.date_input("Possession/completion date", value=p.possession_date if p and p.possession_date else date.today())
            loanstart=st.date_input("Loan start date", value=p.loan_start_date if p and p.loan_start_date else date(2025,11,1))
            lender=st.text_input("Lender", p.lender if p else "")
            interest=money_input("Interest for this FY only", p.interest_fy if p else 0)
            principal=money_input("Principal for this FY only", p.principal_fy if p else 0)
            precon=money_input("Tracked pre-construction interest", p.preconstruction_interest if p else 0)
            notes=st.text_area("Notes", p.notes if p else "")
            if st.form_submit_button("Save property"):
                if not p:
                    p=PropertyLoan(case_id=case.id,property_name=name);session.add(p)
                p.property_name=name;p.property_address=address;p.ownership_percent=ownership
                p.actual_payment_percent=payment;p.self_occupied=selfocc;p.possession_date=possession
                p.loan_start_date=loanstart;p.lender=lender;p.interest_fy=interest
                p.principal_fy=principal;p.preconstruction_interest=precon;p.notes=notes
                log(session,case.id,"UPDATE","PropertyLoan",name)
                st.success("Saved.")
        st.warning("Enter only FY 2025-26 amounts for AY 2026-27. Payments from 1 April 2026 onward belong to the next assessment year.")

    elif page == "Tasks":
        tasks=session.scalars(select(Task).where(Task.case_id==case.id).order_by(Task.phase,Task.id)).all()
        for t in tasks:
            c1,c2,c3=st.columns([2,4,2])
            c1.write(t.phase)
            c2.write(t.title)
            new=c3.selectbox("Status",STATUS_TASK,index=STATUS_TASK.index(t.status),key=f"t{t.id}",label_visibility="collapsed")
            if new!=t.status:
                t.status=new
                log(session,case.id,"UPDATE","Task",f"{t.code}: {new}")
        st.caption("Changes save when the page reruns or you navigate.")

    elif page == "Review":
        checks=review_checks(session,case)
        blocks=sum(c.severity=="BLOCK" for c in checks)
        warns=sum(c.severity=="WARN" for c in checks)
        c1,c2=st.columns(2);c1.metric("Blocking checks",blocks);c2.metric("Warnings",warns)
        for chk in checks:
            fn=st.error if chk.severity=="BLOCK" else st.warning if chk.severity=="WARN" else st.success
            fn(f"**{chk.area}** — {chk.message}")
        st.info("Automated checks catch omissions and inconsistencies; they are not a substitute for final review in the official utility or by a qualified tax professional.")

    elif page == "Export":
        st.write("Creates a portable filing pack containing registers and an automated-review manifest. Uploaded evidence remains in the private evidence folder.")
        if st.button("Generate filing pack"):
            tmp=Path(tempfile.mkdtemp())
            folder=export_case(session,case,tmp/f"{taxpayer.name}_AY_{case.assessment_year}")
            zpath=tmp/f"{taxpayer.name}_AY_{case.assessment_year}_filing_pack.zip"
            with zipfile.ZipFile(zpath,"w",zipfile.ZIP_DEFLATED) as z:
                for f in folder.rglob("*"):
                    if f.is_file(): z.write(f,f.relative_to(folder.parent))
            st.download_button("Download filing pack",zpath.read_bytes(),file_name=zpath.name,mime="application/zip")
            log(session,case.id,"EXPORT","TaxCase",zpath.name)

    elif page == "History":
        rows=session.scalars(select(AuditLog).where(AuditLog.case_id==case.id).order_by(AuditLog.event_time.desc()).limit(500)).all()
        st.dataframe(pd.DataFrame([{
            "Time":r.event_time,"Action":r.action,"Entity":r.entity,"Details":r.details
        } for r in rows]),use_container_width=True,hide_index=True)
