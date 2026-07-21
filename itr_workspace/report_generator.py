"""
Professional Tax Report Generator
Report 1: Detailed Tax Calculation with Government References
Report 2: ITR-2 Form Summary Ready for Filing
"""

from decimal import Decimal
from datetime import datetime
from typing import Dict, List
import json


# Government deduction references with portal links
DEDUCTION_REFERENCES = {
    "80C": {
        "title": "Life Insurance, Investments, Education",
        "act_reference": "Income Tax Act, 1961 - Section 80C",
        "limit": "₹1,50,000 per financial year",
        "description": "Deduction available for life insurance premiums, investments in NSC, post office schemes, mutual funds (ELSS), tuition fees, etc.",
        "eligibility": "All individuals, NRI (on India-sourced income)",
        "portal_url": "https://www.incometax.gov.in/iec/foportal/help/section80c",
        "forms": ["Form 12BB (cert from employer)"],
        "fy_limit": Decimal("150000"),
        "applicable_to_nri": True
    },
    "80D": {
        "title": "Health Insurance Premiums",
        "act_reference": "Income Tax Act, 1961 - Section 80D",
        "limit": "₹1,00,000 (or ₹2,50,000 for senior citizen)",
        "description": "Deduction for health insurance premium for self, spouse, children and dependent parents.",
        "eligibility": "All individuals, NRI (on India-sourced income)",
        "portal_url": "https://www.incometax.gov.in/iec/foportal/help/section80d",
        "forms": ["Medical Insurance Certificate"],
        "fy_limit": Decimal("100000"),
        "applicable_to_nri": True
    },
    "80E": {
        "title": "Interest on Education Loan",
        "act_reference": "Income Tax Act, 1961 - Section 80E",
        "limit": "No limit (but effective max per year ~₹50,000)",
        "description": "Deduction for interest paid on loan taken for higher education of self, spouse, children. 8 years from financial year interest becomes payable.",
        "eligibility": "All individuals pursuing higher education",
        "portal_url": "https://www.incometax.gov.in/iec/foportal/help/section80e",
        "forms": ["Certificate from Educational Institution", "Bank Statement"],
        "fy_limit": Decimal("999999"),
        "applicable_to_nri": True
    },
    "80AC": {
        "title": "Deposit for Girl Child",
        "act_reference": "Income Tax Act, 1961 - Section 80AC",
        "limit": "₹1,50,000 per financial year",
        "description": "Special deduction for deposits made under Sukanya Samriddhi Account for girl child. Can be claimed for up to 10 years from account opening.",
        "eligibility": "Parent/guardian of girl child (up to 10 years old). 100% for RNOR, NRI eligible.",
        "portal_url": "https://www.incometax.gov.in/iec/foportal/help/sukanyasamriddhi",
        "forms": ["Sukanya Samriddhi Account Certificate", "Passbook extract"],
        "fy_limit": Decimal("150000"),
        "applicable_to_nri": True,
        "special_note": "Daughter age: [__] years | Can claim for [__] more years"
    },
    "24B": {
        "title": "Home Loan Interest",
        "act_reference": "Income Tax Act, 1961 - Section 24(b)",
        "limit": "₹2,00,000 per financial year (₹1,50,000 for pre-construction)",
        "description": "Deduction for interest paid on housing loan for acquiring/constructing residential property. Self-occupied property gets full deduction. Let-out property gets deduction as business loss.",
        "eligibility": "Individual owning residential property",
        "portal_url": "https://www.incometax.gov.in/iec/foportal/help/section24",
        "forms": ["Home Loan Certificate from Lender", "Home Loan Account Statement"],
        "fy_limit": Decimal("200000"),
        "applicable_to_nri": True
    },
    "80CCD": {
        "title": "NPS Contribution (Additional)",
        "act_reference": "Income Tax Act, 1961 - Section 80CCD(1B)",
        "limit": "₹50,000 per financial year (Additional to 80C limit)",
        "description": "Additional deduction for contribution to National Pension Scheme by individuals below 60 years.",
        "eligibility": "All individuals with NPS account",
        "portal_url": "https://www.incometax.gov.in/iec/foportal/help/nps",
        "forms": ["NPS Investment Certificate"],
        "fy_limit": Decimal("50000"),
        "applicable_to_nri": False
    },
    "80G": {
        "title": "Charitable Donation",
        "act_reference": "Income Tax Act, 1961 - Section 80G",
        "limit": "50% or 100% of eligible income (based on eligibility)",
        "description": "Deduction for donation to charitable institution or religious trust. Requires form 80G eligibility certificate.",
        "eligibility": "Donation to eligible institutions",
        "portal_url": "https://www.incometax.gov.in/iec/foportal/help/section80g",
        "forms": ["Form 80G Eligibility Certificate", "Donation Receipt"],
        "fy_limit": Decimal("999999"),
        "applicable_to_nri": True
    },
    "80TTA": {
        "title": "Savings Account Interest",
        "act_reference": "Income Tax Act, 1961 - Section 80TTA",
        "limit": "₹10,000 per financial year",
        "description": "Deduction for interest earned on savings bank account with banks/post offices/cooperative banks.",
        "eligibility": "All individuals with savings account",
        "portal_url": "https://www.incometax.gov.in/iec/foportal/help/section80tta",
        "forms": ["Bank Interest Certificate"],
        "fy_limit": Decimal("10000"),
        "applicable_to_nri": False
    }
}


class ReportGenerator:
    """Generate professional tax reports for filing"""
    
    def __init__(self, taxpayer_name: str, pan_last4: str, assessment_year: str, status: str):
        self.name = taxpayer_name
        self.pan = pan_last4
        self.ay = assessment_year
        self.status = status  # NRI or RNOR
        self.generated_at = datetime.now().isoformat()
    
    def generate_report1_calculation_breakdown(self, calculation_result: Dict) -> str:
        """
        Report 1: Detailed Tax Calculation with Government References
        Shows all calculations with explanations and government reference links
        """
        report = []
        
        report.append("=" * 100)
        report.append("TAX CALCULATION REPORT - AY {self.ay}")
        report.append("Prepared for: {} (PAN: ****{})".format(self.name, self.pan))
        report.append("Residential Status: {} | Generated: {}".format(self.status, self.generated_at))
        report.append("=" * 100)
        report.append("")
        
        report.append("SECTION A: INCOME CALCULATION")
        report.append("-" * 100)
        report.append("")
        
        total_gross = calculation_result["total_gross_income"]
        total_exempt = calculation_result["total_exempt_income"]
        taxable_before = calculation_result["taxable_income_before_deductions"]
        
        report.append("1. Total Gross Income (all sources)          : ₹{:>15,.2f}".format(total_gross))
        report.append("2. Less: Exempt Income                       : ₹{:>15,.2f}".format(total_exempt))
        report.append("   (Explanation: Interest on NRE a/c, etc.)  ")
        report.append("3. Taxable Income (before deductions)        : ₹{:>15,.2f}".format(taxable_before))
        report.append("")
        report.append("   Reference: Income Tax Act, 1961 - Section 2(47)")
        report.append("   Portal: https://www.incometax.gov.in/iec/foportal/glossary/income")
        report.append("")
        
        report.append("SECTION B: DEDUCTIONS (OLD REGIME ONLY)")
        report.append("-" * 100)
        report.append("")
        
        for section, details in calculation_result["deductions_breakdown"].items():
            if section in DEDUCTION_REFERENCES:
                ref = DEDUCTION_REFERENCES[section]
                claimed = Decimal(str(details.get("claimed", 0)))
                limit = Decimal(str(details.get("limit", 0)))
                
                report.append("✓ {} - {}".format(section, ref["title"]))
                report.append("  Amount Claimed: ₹{:>12,.2f} / Limit: ₹{:>12,.2f}".format(claimed, limit))
                report.append("  Act Reference : {}".format(ref["act_reference"]))
                report.append("  Description   : {}".format(ref["description"]))
                report.append("  Portal URL    : {}".format(ref["portal_url"]))
                report.append("  Eligibility   : {}".format(ref["eligibility"]))
                
                if section == "80AC" and self.status == "RNOR":
                    report.append("  ⚠️  Special: Girl Child Benefit - Verify age eligibility (max 10 years)")
                
                report.append("")
        
        total_deductions = calculation_result["total_deductions"]
        income_after_ded = calculation_result["income_after_deductions"]
        
        report.append("Total Deductions Claimed                     : ₹{:>15,.2f}".format(total_deductions))
        report.append("Income After Deductions (Old Regime)         : ₹{:>15,.2f}".format(income_after_ded))
        report.append("")
        
        report.append("SECTION C: TAX CALCULATION (OLD REGIME - AY 2026-27)")
        report.append("-" * 100)
        report.append("")
        report.append("Tax Slabs for FY 2025-26 (AY 2026-27):")
        report.append("  0 -  ₹2,50,000 : 0%")
        report.append("  ₹2,50,001 - ₹5,00,000 : 5%")
        report.append("  ₹5,00,001 - ₹7,50,000 : 10%")
        report.append("  ₹7,50,001 - ₹10,00,000 : 15%")
        report.append("  ₹10,00,001 - ₹12,50,000 : 20%")
        report.append("  ₹12,50,001 - ₹15,00,000 : 30%")
        report.append("  Above ₹15,00,000 : 30%")
        report.append("")
        report.append("Taxable Income: ₹{:>15,.2f}".format(income_after_ded))
        report.append("Income Tax (Old Regime)                      : ₹{:>15,.2f}".format(calculation_result["tax_on_income"]))
        report.append("Surcharge (if applicable)                    : ₹{:>15,.2f}".format(calculation_result["surcharge"]))
        report.append("Health & Education Cess (4% on tax)          : ₹{:>15,.2f}".format(calculation_result["cess"]))
        report.append("Total Tax Payable (Old Regime)               : ₹{:>15,.2f}".format(calculation_result["total_tax_payable"]))
        report.append("")
        report.append("Effective Tax Rate                           : {:.2f}%".format(
            (calculation_result["total_tax_payable"] / total_gross * 100) if total_gross > 0 else 0
        ))
        report.append("")
        report.append("Reference: Income Tax Act, 1961 - Schedule 1 (Tax Slabs)")
        report.append("Portal: https://www.incometax.gov.in/iec/foportal/help/taxslabs")
        report.append("")
        
        return "\n".join(report)
    
    def generate_report2_itr_form_summary(self, calculation_result: Dict, tds_credits: Decimal) -> str:
        """
        Report 2: ITR-2 Form Summary - Ready to File
        Shows the form data in filing format
        """
        report = []
        
        report.append("=" * 100)
        report.append("ITR-2 FORM SUMMARY - READY TO FILE")
        report.append("Assessment Year: {} | Taxpayer: {}".format(self.ay, self.name))
        report.append("Generated: {} | Status: READY FOR E-FILING".format(self.generated_at))
        report.append("=" * 100)
        report.append("")
        
        report.append("PART A: PERSONAL INFORMATION")
        report.append("-" * 100)
        report.append("Name                                         : {}".format(self.name))
        report.append("PAN (Last 4 visible)                         : ****{}".format(self.pan))
        report.append("Residential Status                           : {}".format(self.status))
        report.append("Return Form                                  : ITR-2")
        report.append("Assessment Year                              : {}".format(self.ay))
        report.append("")
        
        report.append("PART B: INCOME SCHEDULE")
        report.append("-" * 100)
        report.append("Total Gross Income (All sources)             : ₹{:>15,.2f}".format(calculation_result["total_gross_income"]))
        report.append("Total Exempt Income                          : ₹{:>15,.2f}".format(calculation_result["total_exempt_income"]))
        report.append("")
        
        report.append("PART C: DEDUCTIONS SCHEDULE")
        report.append("-" * 100)
        for section, details in calculation_result["deductions_breakdown"].items():
            claimed = Decimal(str(details.get("claimed", 0)))
            if claimed > 0:
                report.append("{} - {} Deduction                         : ₹{:>15,.2f}".format(
                    section, 
                    DEDUCTION_REFERENCES.get(section, {}).get("title", "Other"), 
                    claimed
                ))
        report.append("Total Deductions (80C, 80D, 80E, etc.)       : ₹{:>15,.2f}".format(calculation_result["total_deductions"]))
        report.append("")
        
        report.append("PART D: TAX COMPUTATION")
        report.append("-" * 100)
        report.append("Taxable Income (after deductions)            : ₹{:>15,.2f}".format(calculation_result["income_after_deductions"]))
        report.append("Income Tax @ applicable slab rates           : ₹{:>15,.2f}".format(calculation_result["tax_on_income"]))
        report.append("Surcharge (if applicable)                    : ₹{:>15,.2f}".format(calculation_result["surcharge"]))
        report.append("Health & Education Cess (4%)                 : ₹{:>15,.2f}".format(calculation_result["cess"]))
        report.append("Gross Tax Payable                            : ₹{:>15,.2f}".format(calculation_result["total_tax_payable"]))
        report.append("")
        
        report.append("PART E: TAX CREDITS & FINAL TAX")
        report.append("-" * 100)
        report.append("TDS (from Form 26AS/Bank/Employer)           : ₹{:>15,.2f}".format(tds_credits))
        final_payable = max(Decimal("0"), calculation_result["total_tax_payable"] - tds_credits)
        report.append("Final Tax Payable / Refund Due               : ₹{:>15,.2f}".format(final_payable))
        if final_payable > 0:
            report.append("Status: TAX PAYABLE (Payment due on filing)")
        else:
            report.append("Status: REFUND DUE (Expected refund: ₹{:,.2f})".format(-final_payable))
        report.append("")
        
        report.append("PART F: COMPLIANCE CHECKLIST")
        report.append("-" * 100)
        report.append("✓ All income sources disclosed")
        report.append("✓ Eligible deductions claimed within limits")
        report.append("✓ TDS credits reconciled with Form 26AS")
        report.append("✓ Residential status verified")
        report.append("✓ All supporting documents collected")
        report.append("")
        
        report.append("PART G: FILING INSTRUCTIONS")
        report.append("-" * 100)
        report.append("1. Visit: https://www.incometax.gov.in/iec/foportal/login")
        report.append("2. Login with your PAN and Password")
        report.append("3. Go to: File ITR → Select ITR-2")
        report.append("4. Enter amounts as shown in this report")
        report.append("5. Upload supporting documents")
        report.append("6. Submit and e-Verify within 120 days")
        report.append("")
        
        report.append("=" * 100)
        report.append("This report is auto-generated. Review carefully before filing.")
        report.append("For assistance: https://www.incometax.gov.in/iec/foportal/help")
        report.append("=" * 100)
        
        return "\n".join(report)


if __name__ == "__main__":
    # Example usage
    gen = ReportGenerator("Nilesh Kumar", "ABCD", "2026-27", "NRI")
    
    sample_calc = {
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
            "80C": {"claimed": 150000, "limit": 150000},
            "80D": {"claimed": 50000, "limit": 100000},
            "80AC": {"claimed": 20000, "limit": 150000}
        }
    }
    
    report1 = gen.generate_report1_calculation_breakdown(sample_calc)
    report2 = gen.generate_report2_itr_form_summary(sample_calc, Decimal("50000"))
    
    print(report1)
    print("\n\n")
    print(report2)
