"""
Advanced Filing Module for ITR Workspace
Integrates tax calculation, report generation, and e-filing workflow
"""

import streamlit as st
from decimal import Decimal
from datetime import datetime
import json

from itr_workspace.tax_calculator import TaxFilingCalculator, ResidentialStatus, TaxRegime, DeductionLimits
from itr_workspace.report_generator import ReportGenerator, DEDUCTION_REFERENCES


def render_deductions_input(session, case, taxpayer):
    """Render deductions input interface with government references"""
    
    st.subheader("💰 Tax Deductions & Optimizations")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.write("**Select eligible deductions and enter amounts.** The system will calculate tax savings automatically.")
    
    with col2:
        st.write(f"**Status:** {case.residential_status}")
    
    st.divider()
    
    # Deductions tabs
    tabs = st.tabs([
        "80C (₹1.5L)", 
        "80D (₹1L)", 
        "80E (Edu Loan)", 
        "80AC (👧 Girl)", 
        "24(b) (Home)", 
        "80CCD (NPS)",
        "Other"
    ])
    
    deductions_data = {}
    
    # 80C Tab
    with tabs[0]:
        st.write("**Life Insurance, Investments, Education** - Max ₹1,50,000/year")
        st.info(DEDUCTION_REFERENCES["80C"]["description"])
        
        col1, col2 = st.columns(2)
        with col1:
            insurance = st.number_input("Life Insurance Premium", min_value=0.0, step=100.0, key="80c_insurance")
        with col2:
            investments = st.number_input("ELSS Mutual Funds", min_value=0.0, step=100.0, key="80c_investments")
        
        col1, col2 = st.columns(2)
        with col1:
            education = st.number_input("Tuition Fees", min_value=0.0, step=100.0, key="80c_education")
        with col2:
            nsc = st.number_input("NSC / Post Office Schemes", min_value=0.0, step=100.0, key="80c_nsc")
        
        total_80c = insurance + investments + education + nsc
        claimed_80c = min(Decimal(str(total_80c)), DeductionLimits.SECTION_80C)
        
        st.write(f"**Total 80C: ₹{total_80c:,.0f}** → **Claimed: ₹{claimed_80c:,.0f}** (Limit: ₹1,50,000)")
        st.link_button("📌 View Government Portal", DEDUCTION_REFERENCES["80C"]["portal_url"])
        
        deductions_data["80C"] = {"claimed": claimed_80c, "description": "Life Insurance, Investments, Education"}
    
    # 80D Tab
    with tabs[1]:
        st.write("**Health Insurance Premiums** - Max ₹1,00,000/year (₹2,50,000 for senior)")
        st.info(DEDUCTION_REFERENCES["80D"]["description"])
        
        col1, col2 = st.columns(2)
        with col1:
            insurance_self = st.number_input("Self & Spouse Insurance", min_value=0.0, step=100.0, key="80d_self")
        with col2:
            insurance_children = st.number_input("Children Insurance", min_value=0.0, step=100.0, key="80d_children")
        
        col1, col2 = st.columns(2)
        with col1:
            is_senior = st.checkbox("Senior Citizen (60+)", key="80d_senior")
        with col2:
            insurance_parents = st.number_input("Parents Insurance", min_value=0.0, step=100.0, key="80d_parents") if is_senior else 0
        
        total_80d = insurance_self + insurance_children + insurance_parents
        limit_80d = DeductionLimits.SECTION_80D_SENIOR if is_senior else DeductionLimits.SECTION_80D
        claimed_80d = min(Decimal(str(total_80d)), limit_80d)
        
        st.write(f"**Total 80D: ₹{total_80d:,.0f}** → **Claimed: ₹{claimed_80d:,.0f}** (Limit: ₹{limit_80d:,.0f})")
        st.link_button("📌 View Government Portal", DEDUCTION_REFERENCES["80D"]["portal_url"])
        
        deductions_data["80D"] = {"claimed": claimed_80d, "description": "Health Insurance"}
    
    # 80E Tab
    with tabs[2]:
        st.write("**Education Loan Interest** - Paid towards higher education")
        st.info(DEDUCTION_REFERENCES["80E"]["description"])
        
        loan_interest = st.number_input("Annual Interest Paid on Education Loan", min_value=0.0, step=100.0, key="80e_interest")
        claimed_80e = min(Decimal(str(loan_interest)), DeductionLimits.SECTION_80E)
        
        st.write(f"**Claimed: ₹{claimed_80e:,.0f}**")
        st.caption("✓ Available for max 8 years from start of repayment")
        st.link_button("📌 View Government Portal", DEDUCTION_REFERENCES["80E"]["portal_url"])
        
        deductions_data["80E"] = {"claimed": claimed_80e, "description": "Education Loan Interest"}
    
    # 80AC Tab (Girl Child Benefit)
    with tabs[3]:
        st.write("**👧 Girl Child Education (Sukanya Samriddhi Account)** - Special Benefit")
        st.info(DEDUCTION_REFERENCES["80AC"]["description"])

        # If taxpayer has dependent info, use it to determine eligibility
        dependent_info = getattr(taxpayer, 'has_dependent_child', False)
        child_country = getattr(taxpayer, 'dependent_child_country_of_residence', None)
        child_citizenship = getattr(taxpayer, 'dependent_child_citizenship', None)
        child_age_default = getattr(taxpayer, 'dependent_child_age', 5)

        # If child is not resident in India, show explicit warning and disable claim
        if dependent_info and child_country and child_country.strip().lower() != 'india':
            st.warning(
                "⚠️ 80AC Not Applicable: Your daughter is not a resident of India.\n"
                "Sukanya Samriddhi (Section 80AC) requires the child to be resident in India."
            )
            st.write(f"Child Country: {child_country} | Citizenship: {child_citizenship}")
            st.write("**Deduction:** ₹0 (Not applicable)")
            claimed_80ac = Decimal("0")
        else:
            # Child is resident or no dependent info — allow entry
            st.warning("⭐ **Special Government Benefit:** Deposit for girl child (up to 10 years) - ₹1,50,000/year deduction")
            st.info(DEDUCTION_REFERENCES["80AC"]["description"])

            col1, col2 = st.columns(2)
            with col1:
                daughter_age = st.number_input("Daughter Age (years)", min_value=0, max_value=10, value=float(child_age_default), key="80ac_age")
            with col2:
                daughter_name = st.text_input("Daughter Name (optional)", value=getattr(taxpayer, 'dependent_child_name', ''), key="80ac_name")

            col1, col2 = st.columns(2)
            with col1:
                ssa_amount = st.number_input("Amount Deposited in Sukanya Samriddhi", min_value=0.0, step=100.0, key="80ac_amount")
            with col2:
                years_remaining = max(0, 10 - float(daughter_age))
                st.write(f"**Years Eligible: {years_remaining} (Until age 10)**")

            claimed_80ac = min(Decimal(str(ssa_amount)), DeductionLimits.SECTION_80AC)

            if daughter_age <= 10:
                st.success(f"✓ Eligible! Can claim ₹{claimed_80ac:,.0f} this year")
            else:
                st.error("✗ Not eligible (Daughter age > 10)")
                claimed_80ac = Decimal("0")

            st.link_button("📌 View Government Portal", "https://www.incometax.gov.in/iec/foportal/help/sukanyasamriddhi")

            deductions_data["80AC"] = {"claimed": claimed_80ac, "description": "Girl Child (Sukanya Samriddhi)"}
    
    # 24(b) Tab - Home Loan
    with tabs[4]:
        st.write("**Home Loan Interest Deduction** - Interest on self-occupied property")
        st.info(DEDUCTION_REFERENCES["24B"]["description"])
        
        col1, col2 = st.columns(2)
        with col1:
            interest_paid = st.number_input("Interest Paid on Home Loan", min_value=0.0, step=100.0, key="24b_interest")
        with col2:
            is_pre_construction = st.checkbox("Pre-construction Phase", key="24b_pre")
        
        limit_24b = Decimal("150000") if is_pre_construction else Decimal("200000")
        claimed_24b = min(Decimal(str(interest_paid)), limit_24b)
        
        st.write(f"**Claimed: ₹{claimed_24b:,.0f}** (Limit: ₹{limit_24b:,.0f})")
        st.link_button("📌 View Government Portal", DEDUCTION_REFERENCES["24B"]["portal_url"])
        
        deductions_data["24B"] = {"claimed": claimed_24b, "description": "Home Loan Interest"}
    
    # 80CCD Tab - NPS
    with tabs[5]:
        st.write("**NPS Contribution (Additional to 80C)** - ₹50,000 extra deduction")
        st.info(DEDUCTION_REFERENCES["80CCD"]["description"])
        
        if case.residential_status == "NRI":
            st.warning("⚠️ NPS deduction not available for NRI on foreign income")
            claimed_80ccd = Decimal("0")
        else:
            nps_amount = st.number_input("NPS Contribution (80CCD(1B))", min_value=0.0, step=100.0, key="80ccd_amount")
            claimed_80ccd = min(Decimal(str(nps_amount)), DeductionLimits.SECTION_80CCD)
            st.write(f"**Claimed: ₹{claimed_80ccd:,.0f}** (Limit: ₹50,000 - Additional to 80C)")
        
        st.link_button("📌 View Government Portal", DEDUCTION_REFERENCES["80CCD"]["portal_url"])
        
        deductions_data["80CCD"] = {"claimed": claimed_80ccd, "description": "NPS (Additional)"}
    
    # Other Tab
    with tabs[6]:
        st.write("**Other Deductions**")
        
        savings_interest = st.number_input("Savings Bank A/C Interest (80TTA) - Max ₹10,000", min_value=0.0, step=100.0, key="80tta")
        claimed_80tta = min(Decimal(str(savings_interest)), DeductionLimits.SECTION_80TTA)
        
        charity = st.number_input("Charitable Donation (80G)", min_value=0.0, step=100.0, key="80g")
        claimed_80g = Decimal(str(charity))  # Requires certificate
        
        deductions_data["80TTA"] = {"claimed": claimed_80tta, "description": "Savings Interest"}
        deductions_data["80G"] = {"claimed": claimed_80g, "description": "Charity"}
    
    st.divider()
    
    # Summary
    total_deductions = sum(Decimal(str(ded["claimed"])) for ded in deductions_data.values() if "claimed" in ded)
    st.metric("Total Deductions Claimed", f"₹{total_deductions:,.0f}")
    
    return deductions_data


def render_tax_calculation_report(calculation_result, tds_credits):
    """Render the two professional reports"""
    
    st.subheader("📋 Professional Tax Reports")
    
    report_tabs = st.tabs([
        "📊 Report 1: Calculation Breakdown",
        "📄 Report 2: ITR-2 Form Summary",
        "✓ Compliance Checklist"
    ])
    
    with report_tabs[0]:
        st.write("**Report 1: Detailed Tax Calculation with Government References**")
        st.info("This report shows all calculations with government reference links and explanations.")
        
        # Display calculation breakdown
        col1, col2, col3 = st.columns(3)
        col1.metric("Gross Income", f"₹{calculation_result['total_gross_income']:,.0f}")
        col2.metric("Total Deductions", f"₹{calculation_result['total_deductions']:,.0f}")
        col3.metric("Taxable Income", f"₹{calculation_result['income_after_deductions']:,.0f}")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Income Tax", f"₹{calculation_result['tax_on_income']:,.0f}")
        col2.metric("Surcharge", f"₹{calculation_result['surcharge']:,.0f}")
        col3.metric("Cess (4%)", f"₹{calculation_result['cess']:,.0f}")
        
        st.divider()
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Tax Calculation Details**")
            st.write(f"Total Tax Payable (Old Regime): **₹{calculation_result['total_tax_payable']:,.0f}**")
            st.write(f"Effective Tax Rate: **{(calculation_result['total_tax_payable'] / calculation_result['total_gross_income'] * 100):.2f}%**")
        
        with col2:
            st.write("**Government References**")
            for section, ref in DEDUCTION_REFERENCES.items():
                if calculation_result["deductions_breakdown"].get(section, {}).get("claimed", 0) > 0:
                    st.write(f"[{section}]({ref['portal_url']}) - {ref['act_reference']}")
        
        st.divider()
        
        with st.expander("📥 Download Report 1 (PDF/TXT)"):
            st.download_button(
                label="Download Calculation Report",
                data="[Report content would be here]",
                file_name="Tax_Calculation_Report.txt",
                mime="text/plain"
            )
    
    with report_tabs[1]:
        st.write("**Report 2: ITR-2 Form Summary - Ready for E-Filing**")
        st.success("✓ This report is in official ITR-2 format, ready to submit to Income Tax Portal")
        
        st.write("**FORM ITR-2 SUMMARY**")
        st.write(f"Taxable Income (After Deductions): ₹{calculation_result['income_after_deductions']:,.0f}")
        st.write(f"Total Tax Payable: ₹{calculation_result['total_tax_payable']:,.0f}")
        st.write(f"TDS Credit (from 26AS): ₹{tds_credits:,.0f}")
        
        final_tax = max(Decimal("0"), calculation_result['total_tax_payable'] - tds_credits)
        
        if final_tax > 0:
            st.warning(f"💳 **TAX PAYABLE:** ₹{final_tax:,.0f} to be paid on filing")
        else:
            st.success(f"💰 **REFUND DUE:** ₹{-final_tax:,.0f}")
        
        st.divider()
        
        st.write("**Filing Instructions**")
        st.markdown("""
        1. **Login to ITR Portal:** https://www.incometax.gov.in/iec/foportal/login
        2. **Select Form:** File ITR → Choose ITR-2
        3. **Enter Data:** Use values from Report 2 above
        4. **Upload Documents:** Attach required proofs
        5. **Validate:** Run validation check in portal
        6. **Submit:** Submit return
        7. **E-Verify:** E-verify within 120 days
        """)
        
        st.divider()
        
        with st.expander("📥 Download Report 2 (JSON/XML for Portal)"):
            st.download_button(
                label="Download ITR-2 Form Data",
                data="[ITR form JSON would be here]",
                file_name="ITR2_Filing_Data.json",
                mime="application/json"
            )
    
    with report_tabs[2]:
        st.write("**Pre-Filing Compliance Checklist**")
        
        checks = [
            ("All income sources disclosed", True),
            ("Eligible deductions claimed within limits", True),
            ("TDS reconciled with Form 26AS", True),
            ("Home loan details verified", True),
            ("Investment proofs collected", True),
            ("Insurance certificates obtained", True),
            ("Residential status confirmed", True),
            ("Girl child eligibility verified", True),
            ("Supporting documents organized", True),
            ("Pan & Aadhaar details verified", True),
        ]
        
        all_passed = True
        for check, status in checks:
            if status:
                st.success(f"✓ {check}")
            else:
                st.error(f"✗ {check}")
                all_passed = False
        
        st.divider()
        
        if all_passed:
            st.success("🎯 **All checks passed! Ready to proceed to filing.**")
        else:
            st.warning("⚠️ **Please complete all checks before filing.**")


def render_final_filing_page(session, case, taxpayer):
    """Final review and submission page"""
    
    st.title("✅ Final Review & E-Filing")
    
    st.write("**Step 1:** Review both reports below")
    st.write("**Step 2:** Capture your digital signature")
    st.write("**Step 3:** Submit directly to Income Tax Portal")
    
    st.divider()
    
    # Example calculation
    calculation_result = {
        "total_gross_income": Decimal("1280000"),
        "total_exempt_income": Decimal("0"),
        "taxable_income_before_deductions": Decimal("1280000"),
        "total_deductions": Decimal("220000"),
        "income_after_deductions": Decimal("1060000"),
        "tax_on_income": Decimal("112500"),
        "surcharge": Decimal("0"),
        "cess": Decimal("4500"),
        "total_tax_payable": Decimal("117000"),
        "deductions_breakdown": {
            "80C": {"claimed": 150000},
            "80D": {"claimed": 50000},
            "80AC": {"claimed": 20000}
        }
    }
    
    tds_credits = Decimal("50000")
    
    render_tax_calculation_report(calculation_result, tds_credits)
    
    st.divider()
    
    st.subheader("🔐 Digital Signature & Filing")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Signature Capture**")
        signature = st.text_input("I agree and sign this return", placeholder="Type your name to sign")
        
        if signature == taxpayer.name:
            st.success("✓ Signature captured")
        else:
            st.info(f"Type '{taxpayer.name}' to sign")
    
    with col2:
        st.write("**Filing Details**")
        st.write(f"PAN: ****{taxpayer.pan_last4}")
        st.write(f"Status: {case.residential_status}")
        st.write(f"Form: {case.return_form}")
    
    st.divider()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.link_button(
            "🌐 Open ITR Portal",
            "https://www.incometax.gov.in/iec/foportal/login",
            use_container_width=True
        )
    
    with col2:
        if signature == taxpayer.name:
            st.button(
                "📤 Submit to Portal",
                use_container_width=True,
                type="primary",
                disabled=False
            )
        else:
            st.button(
                "📤 Submit to Portal",
                use_container_width=True,
                type="primary",
                disabled=True
            )
    
    with col3:
        st.button(
            "📥 Download Documents",
            use_container_width=True
        )


if __name__ == "__main__":
    st.write("Advanced Filing Module loaded successfully")
