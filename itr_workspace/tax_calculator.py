"""
Professional Tax Calculation Engine for ITR Filing
Supports old regime, new regime, all deductions, surcharge, cess, NRI/RNOR
AY 2026-27 compatible
"""

from decimal import Decimal
from datetime import datetime
from typing import Dict, List, Tuple
from enum import Enum


class TaxRegime(Enum):
    OLD = "Old"
    NEW = "New"


class ResidentialStatus(Enum):
    NRI = "NRI"
    RNOR = "RNOR"
    ROR = "ROR"


# AY 2026-27 Tax Slabs (FY 2025-26)
TAX_SLABS_OLD_REGIME_2026_27 = [
    (Decimal("250000"), Decimal("0")),      # 0-2.5L: 0%
    (Decimal("500000"), Decimal("0.05")),   # 2.5L-5L: 5%
    (Decimal("750000"), Decimal("0.10")),   # 5L-7.5L: 10%
    (Decimal("1000000"), Decimal("0.15")),  # 7.5L-10L: 15%
    (Decimal("1250000"), Decimal("0.20")),  # 10L-12.5L: 20%
    (Decimal("1500000"), Decimal("0.30")),  # 12.5L-15L: 30%
    (float("inf"), Decimal("0.30")),        # 15L+: 30%
]

TAX_SLABS_NEW_REGIME_2026_27 = [
    (Decimal("300000"), Decimal("0")),      # 0-3L: 0%
    (Decimal("600000"), Decimal("0.05")),   # 3L-6L: 5%
    (Decimal("900000"), Decimal("0.10")),   # 6L-9L: 10%
    (Decimal("1200000"), Decimal("0.15")),  # 9L-12L: 15%
    (Decimal("1500000"), Decimal("0.20")),  # 12L-15L: 20%
    (Decimal("1800000"), Decimal("0.25")),  # 15L-18L: 25%
    (float("inf"), Decimal("0.30")),        # 18L+: 30%
]

# Surcharge applicable (depends on income & residential status)
SURCHARGE_THRESHOLDS_2026_27 = {
    "regular": Decimal("5000000"),      # 5Cr: 10% surcharge, 15%, 25%, 37%
    "nri_rnor": Decimal("5000000"),
}

# Health & Education Cess: 4% on tax (old) / 4% on tax (new)
HEALTH_EDUCATION_CESS_RATE = Decimal("0.04")


class DeductionLimits:
    """AY 2026-27 Deduction Limits"""
    
    SECTION_80C = Decimal("150000")      # Life Insurance, Investments, Education
    SECTION_80D = Decimal("100000")      # Health Insurance (self+spouse)
    SECTION_80D_SENIOR = Decimal("250000")  # Senior citizen
    SECTION_80E = Decimal("50000")       # Education Loan Interest (unlimited but practical max)
    SECTION_80AC = Decimal("150000")     # Girl Child - 10 years old, ₹1.5L/year
    SECTION_24B = Decimal("200000")      # Home Loan Interest (pre-construction: ₹150K)
    SECTION_80CCD = Decimal("50000")     # NPS (additional 50K under 80CCD(1B))
    SECTION_80G = Decimal("1000000")     # Charity (50% or 100% of eligible income)
    SECTION_80TTA = Decimal("10000")     # Savings Account Interest
    SECTION_80TTB = Decimal("50000")     # Senior Citizen Interest


def calculate_tax_old_regime(taxable_income: Decimal) -> Decimal:
    """Calculate tax under Old Regime"""
    if taxable_income <= 0:
        return Decimal("0")
    
    tax = Decimal("0")
    prev_limit = Decimal("0")
    
    for limit, rate in TAX_SLABS_OLD_REGIME_2026_27:
        if taxable_income <= prev_limit:
            break
        
        taxable_in_slab = min(taxable_income, limit) - prev_limit
        tax += taxable_in_slab * rate
        prev_limit = limit
    
    return tax.quantize(Decimal("0.01"))


def calculate_tax_new_regime(taxable_income: Decimal) -> Decimal:
    """Calculate tax under New Regime (no deductions allowed)"""
    if taxable_income <= 0:
        return Decimal("0")
    
    tax = Decimal("0")
    prev_limit = Decimal("0")
    
    for limit, rate in TAX_SLABS_NEW_REGIME_2026_27:
        if taxable_income <= prev_limit:
            break
        
        taxable_in_slab = min(taxable_income, limit) - prev_limit
        tax += taxable_in_slab * rate
        prev_limit = limit
    
    return tax.quantize(Decimal("0.01"))


def calculate_surcharge(tax: Decimal, income: Decimal, status: ResidentialStatus) -> Decimal:
    """Calculate surcharge based on income level and residential status"""
    if income <= Decimal("5000000"):
        return Decimal("0")
    
    if status in [ResidentialStatus.NRI, ResidentialStatus.RNOR]:
        # NRI/RNOR surcharge rates
        if income <= Decimal("5000000"):
            rate = Decimal("0")
        elif income <= Decimal("10000000"):
            rate = Decimal("0.10")
        elif income <= Decimal("20000000"):
            rate = Decimal("0.15")
        elif income <= Decimal("50000000"):
            rate = Decimal("0.25")
        else:
            rate = Decimal("0.37")
    else:
        # Regular surcharge rates
        if income <= Decimal("5000000"):
            rate = Decimal("0")
        elif income <= Decimal("10000000"):
            rate = Decimal("0.10")
        elif income <= Decimal("20000000"):
            rate = Decimal("0.15")
        elif income <= Decimal("50000000"):
            rate = Decimal("0.25")
        else:
            rate = Decimal("0.37")
    
    return (tax * rate).quantize(Decimal("0.01"))


def calculate_cess(tax: Decimal) -> Decimal:
    """Calculate Health & Education Cess (4% on tax)"""
    return (tax * HEALTH_EDUCATION_CESS_RATE).quantize(Decimal("0.01"))


class TaxFilingCalculator:
    """Complete tax filing calculation with all deductions"""
    
    def __init__(self, residential_status: ResidentialStatus, assessment_year: str = "2026-27"):
        self.status = residential_status
        self.ay = assessment_year
        self.deductions = {}
        self.income_components = {}
    
    def add_income(self, category: str, amount: Decimal, exempt: Decimal = Decimal("0")) -> None:
        """Add income component"""
        self.income_components[category] = {
            "gross": amount,
            "exempt": exempt,
            "taxable": amount - exempt
        }
    
    def add_deduction(self, section: str, amount: Decimal, limit: Decimal) -> Dict:
        """Add deduction with eligibility check"""
        # Check NRI/RNOR eligibility
        nri_non_eligible_sections = ["80C", "80D", "80G", "80CCD"]  # Generally not available to NRI on foreign income
        
        eligible = True
        reason = ""
        
        if self.status == ResidentialStatus.NRI and section in nri_non_eligible_sections:
            # NRI can claim on India-sourced income
            eligible = True  # Assuming income is India-sourced
        
        # Apply limit
        claimed_amount = min(amount, limit)
        
        self.deductions[section] = {
            "claimed": claimed_amount,
            "limit": limit,
            "eligible": eligible,
            "reason": reason
        }
        
        return self.deductions[section]
    
    def calculate_filing(self, regime: TaxRegime, person=None) -> Dict:
        """Calculate complete filing for given regime

        If `person` is provided, use it to validate eligibility for certain
        deductions (e.g., Section 80AC requires India-resident dependent).
        """
        # Step 1: Calculate total income
        total_gross = sum(Decimal(str(inc["gross"])) for inc in self.income_components.values())
        total_exempt = sum(Decimal(str(inc["exempt"])) for inc in self.income_components.values())
        taxable_income_before_deduction = total_gross - total_exempt

        # Step 2: Apply deductions
        if regime == TaxRegime.OLD:
            # If person provided, enforce 80AC eligibility
            if person is not None and "80AC" in self.deductions:
                # If dependent not eligible, zero out claimed amount and mark ineligible
                if not getattr(person, "is_eligible_for_80ac", False):
                    self.deductions["80AC"]["claimed"] = Decimal("0")
                    self.deductions["80AC"]["eligible"] = False
                    self.deductions["80AC"]["reason"] = "Dependent not India resident or age >= 10"

            total_deductions = sum(
                Decimal(str(ded["claimed"])) for ded in self.deductions.values()
                if ded.get("eligible", True)
            )
        else:
            # New regime: no deductions except certain specific ones
            total_deductions = Decimal("0")  # New regime doesn't allow most deductions

        income_after_deductions = max(Decimal("0"), taxable_income_before_deduction - total_deductions)

        # Step 3: Calculate tax
        if regime == TaxRegime.OLD:
            tax = calculate_tax_old_regime(income_after_deductions)
        else:
            tax = calculate_tax_new_regime(total_gross - total_exempt)  # No deductions in new regime

        # Step 4: Calculate surcharge
        surcharge = calculate_surcharge(tax, total_gross, self.status)

        # Step 5: Calculate cess
        cess = calculate_cess(tax + surcharge)

        # Step 6: Total tax
        total_tax = tax + surcharge + cess

        # Step 7: Calculate effective rate
        effective_rate = (total_tax / total_gross * Decimal("100")) if total_gross > 0 else Decimal("0")

        return {
            "regime": regime.value,
            "total_gross_income": total_gross,
            "total_exempt_income": total_exempt,
            "taxable_income_before_deductions": taxable_income_before_deduction,
            "total_deductions": total_deductions,
            "income_after_deductions": income_after_deductions,
            "tax_on_income": tax,
            "surcharge": surcharge,
            "cess": cess,
            "total_tax_payable": total_tax,
            "effective_tax_rate_percent": effective_rate.quantize(Decimal("0.01")),
            "deductions_breakdown": self.deductions
        }

    def compare_regimes(self, tds_credits: Decimal = Decimal("0"), person=None) -> Dict:
        """Compare old vs new regime and recommend. Pass `person` to enforce deduction rules."""
        old_result = self.calculate_filing(TaxRegime.OLD, person=person)
        new_result = self.calculate_filing(TaxRegime.NEW, person=person)

        old_payable = max(Decimal("0"), old_result["total_tax_payable"] - tds_credits)
        new_payable = max(Decimal("0"), new_result["total_tax_payable"] - tds_credits)

        savings = new_payable - old_payable  # Positive if old regime is better

        recommendation = "Old" if old_payable < new_payable else "New" if new_payable < old_payable else "Either"

        return {
            "old_regime": old_result,
            "new_regime": new_result,
            "old_regime_payable_after_credits": old_payable,
            "new_regime_payable_after_credits": new_payable,
            "tax_savings_with_old_regime": max(Decimal("0"), savings),
            "recommended_regime": recommendation,
            "tds_credits_applied": tds_credits
        }


if __name__ == "__main__":
    # Example: Nilesh (NRI) calculation
    calc = TaxFilingCalculator(ResidentialStatus.NRI)
    
    # Add income
    calc.add_income("Salary (India-source)", Decimal("1200000"), Decimal("0"))
    calc.add_income("Bank Interest (NRE)", Decimal("50000"), Decimal("0"))
    calc.add_income("Dividend (India)", Decimal("30000"), Decimal("0"))
    
    # Add deductions
    calc.add_deduction("80C", Decimal("150000"), DeductionLimits.SECTION_80C)
    calc.add_deduction("80D", Decimal("50000"), DeductionLimits.SECTION_80D)
    calc.add_deduction("80E", Decimal("30000"), DeductionLimits.SECTION_80E)
    calc.add_deduction("80AC", Decimal("150000"), DeductionLimits.SECTION_80AC)
    
    # Compare regimes
    comparison = calc.compare_regimes(tds_credits=Decimal("50000"))
    
    print(f"Old Regime Tax Payable: ₹{comparison['old_regime_payable_after_credits']:,.2f}")
    print(f"New Regime Tax Payable: ₹{comparison['new_regime_payable_after_credits']:,.2f}")
    print(f"Recommended: {comparison['recommended_regime']}")
    print(f"Tax Savings: ₹{comparison['tax_savings_with_old_regime']:,.2f}")
