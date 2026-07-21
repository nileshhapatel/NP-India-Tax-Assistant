"""
Deduction Rules for Indian Income Tax (Chapter VIA)

All deductions under Section 80C, 80CCC, 80CCD, 80D, 80DDB, 80E, 80G, etc.
Updated for FY 2025-26 (AY 2026-27)
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class ResidencyStatus(Enum):
    """Residency for deduction eligibility"""
    ROR = "ror"
    NRI = "nri"
    RNOR = "rnor"


@dataclass
class DeductionRule:
    """Definition of a deduction rule"""
    section: str
    description: str
    max_limit: Decimal
    applicable_to: List[ResidencyStatus]
    requires_proof: bool = True
    remarks: Optional[str] = None


class DeductionRules:
    """Central repository of all deduction rules for AY 2026-27"""

    RULES = {
        # Section 80C - Investment-based deductions
        "80C": DeductionRule(
            section="80C",
            description="Life insurance premium, PPF, ELSS, NSC, ULIPs, etc.",
            max_limit=Decimal(150000),
            applicable_to=[ResidencyStatus.ROR, ResidencyStatus.RNOR],
            requires_proof=True,
            remarks="Cumulative limit across all 80C, 80CCC, 80CCD(1)"
        ),

        # Section 80CCC - Pension Plan
        "80CCC": DeductionRule(
            section="80CCC",
            description="Contribution to approved pension plan",
            max_limit=Decimal(150000),  # Part of 80C limit
            applicable_to=[ResidencyStatus.ROR, ResidencyStatus.RNOR],
            requires_proof=True,
            remarks="Part of 80C composite limit"
        ),

        # Section 80CCD(1) - NPS
        "80CCD(1)": DeductionRule(
            section="80CCD(1)",
            description="National Pension Scheme contributions",
            max_limit=Decimal(150000),  # Part of 80C limit
            applicable_to=[ResidencyStatus.ROR, ResidencyStatus.RNOR, ResidencyStatus.NRI],
            requires_proof=True,
            remarks="10% of gross salary (max Rs. 1,50,000) for employees"
        ),

        # Section 80CCD(1B) - Additional NPS
        "80CCD(1B)": DeductionRule(
            section="80CCD(1B)",
            description="Additional NPS contribution by senior citizens",
            max_limit=Decimal(50000),
            applicable_to=[ResidencyStatus.ROR, ResidencyStatus.RNOR],
            requires_proof=True,
            remarks="Only for individuals aged 50 and above; over and above 80CCD(1)"
        ),

        # Section 80CCD(2) - Employer NPS
        "80CCD(2)": DeductionRule(
            section="80CCD(2)",
            description="Employer contribution to NPS (upto 14% of salary)",
            max_limit=Decimal(1050000),  # 14% of max salary
            applicable_to=[ResidencyStatus.ROR, ResidencyStatus.RNOR],
            requires_proof=True,
            remarks="Employer contribution; no personal deduction needed"
        ),

        # Section 80D - Medical Insurance Premium
        "80D": DeductionRule(
            section="80D",
            description="Health/medical insurance premium for self and dependents",
            max_limit=Decimal(100000),
            applicable_to=[ResidencyStatus.ROR, ResidencyStatus.RNOR, ResidencyStatus.NRI],
            requires_proof=True,
            remarks="Rs. 50,000 for individual below 60, Rs. 1,00,000 if 60+"
        ),

        # Section 80DDB - Medical Treatment
        "80DDB": DeductionRule(
            section="80DDB",
            description="Medical treatment expenses for specified diseases",
            max_limit=Decimal(100000),
            applicable_to=[ResidencyStatus.ROR, ResidencyStatus.RNOR],
            requires_proof=True,
            remarks="For treatment of cancer, heart condition, organ transplant, etc."
        ),

        # Section 80E - Education Loan Interest
        "80E": DeductionRule(
            section="80E",
            description="Interest on loan taken for higher education",
            max_limit=Decimal(999999),  # No limit
            applicable_to=[ResidencyStatus.ROR, ResidencyStatus.RNOR, ResidencyStatus.NRI],
            requires_proof=True,
            remarks="No upper limit; must be for self, spouse, or dependent"
        ),

        # Section 80EE - Home Loan Interest (First-time buyer)
        "80EE": DeductionRule(
            section="80EE",
            description="Additional deduction for home loan interest (first-time buyer)",
            max_limit=Decimal(150000),
            applicable_to=[ResidencyStatus.ROR, ResidencyStatus.RNOR],
            requires_proof=True,
            remarks="Rs. 1,50,000; applicable for first-time home buyers; AY 2024-25 onwards"
        ),

        # Section 80EEA - Affordable Housing
        "80EEA": DeductionRule(
            section="80EEA",
            description="Interest on home loan for affordable housing",
            max_limit=Decimal(200000),
            applicable_to=[ResidencyStatus.ROR, ResidencyStatus.RNOR],
            requires_proof=True,
            remarks="Rs. 2,00,000 for loans up to Rs. 45 lakhs"
        ),

        # Section 80EEB - Electric Vehicle Loan
        "80EEB": DeductionRule(
            section="80EEB",
            description="Interest on loan for electric vehicle",
            max_limit=Decimal(150000),
            applicable_to=[ResidencyStatus.ROR, ResidencyStatus.RNOR],
            requires_proof=True,
            remarks="Rs. 1,50,000; AY 2024-25 onwards"
        ),

        # Section 80G - Charitable Donations
        "80G": DeductionRule(
            section="80G",
            description="Donations to approved charitable institutions",
            max_limit=Decimal(999999),  # Variable by donation type
            applicable_to=[ResidencyStatus.ROR, ResidencyStatus.RNOR, ResidencyStatus.NRI],
            requires_proof=True,
            remarks="50% or 100% depending on nature of donation and institution"
        ),

        # Section 80GG - Rent Paid (Non-salaried)
        "80GG": DeductionRule(
            section="80GG",
            description="Rent paid by non-salaried individuals",
            max_limit=Decimal(240000),  # Rs. 24,000/month max
            applicable_to=[ResidencyStatus.ROR, ResidencyStatus.RNOR],
            requires_proof=True,
            remarks="40% of total income or Rs. 2,40,000, whichever is lower"
        ),

        # Section 80GGC - Rent Paid by Employees
        "80GGC": DeductionRule(
            section="80GGC",
            description="Rent paid by salaried employees/pension recipients",
            max_limit=Decimal(600000),
            applicable_to=[ResidencyStatus.ROR, ResidencyStatus.RNOR],
            requires_proof=True,
            remarks="60% of salary or Rs. 6,00,000, whichever is lower"
        ),

        # Section 80U - Disability Allowance
        "80U": DeductionRule(
            section="80U",
            description="Allowance for persons with severe disability",
            max_limit=Decimal(125000),
            applicable_to=[ResidencyStatus.ROR, ResidencyStatus.RNOR],
            requires_proof=True,
            remarks="Rs. 1,25,000 for severe disability, Rs. 75,000 for other disabilities"
        ),

        # Section 80AC - LIC Premium
        "80AC": DeductionRule(
            section="80AC",
            description="LIC Premium (now part of 80C)",
            max_limit=Decimal(150000),
            applicable_to=[ResidencyStatus.ROR, ResidencyStatus.RNOR],
            requires_proof=True,
            remarks="Subsumed under 80C; kept for reference"
        ),
    }

    @classmethod
    def get_deduction_rule(cls, section: str) -> Optional[DeductionRule]:
        """Get deduction rule for a specific section"""
        return cls.RULES.get(section)

    @classmethod
    def get_eligible_deductions(
        cls,
        residency_status: ResidencyStatus,
    ) -> List[DeductionRule]:
        """Get all deductions eligible for given residency status"""
        return [
            rule for rule in cls.RULES.values()
            if residency_status in rule.applicable_to
        ]

    @classmethod
    def validate_deduction(
        cls,
        section: str,
        amount: Decimal,
        residency_status: ResidencyStatus,
    ) -> Dict:
        """
        Validate a deduction claim.
        
        Returns dict with:
        - valid: bool
        - allowed_amount: Decimal
        - message: str
        - references: List of government rule references
        """
        rule = cls.get_deduction_rule(section)
        
        if not rule:
            return {
                "valid": False,
                "allowed_amount": Decimal(0),
                "message": f"Section {section} not recognized",
                "references": []
            }
        
        if residency_status not in rule.applicable_to:
            return {
                "valid": False,
                "allowed_amount": Decimal(0),
                "message": f"Section {section} not applicable for {residency_status.value} residents",
                "references": [f"https://www.incometax.gov.in/e-docs/{section}"]
            }
        
        allowed_amount = min(amount, rule.max_limit)
        
        if amount > rule.max_limit:
            return {
                "valid": True,
                "allowed_amount": allowed_amount,
                "message": f"Amount capped at {rule.max_limit} as per {section}",
                "references": [f"https://www.incometax.gov.in/e-docs/{section}"]
            }
        
        return {
            "valid": True,
            "allowed_amount": allowed_amount,
            "message": f"Deduction allowed under {section}",
            "references": [f"https://www.incometax.gov.in/e-docs/{section}"]
        }

    @classmethod
    def get_80c_eligibility(cls) -> Dict:
        """Get all items eligible under Section 80C composite limit"""
        return {
            "limit": float(Decimal(150000)),
            "items": [
                {"name": "Life Insurance Premium", "max": float(Decimal(999999))},
                {"name": "Public Provident Fund (PPF)", "max": float(Decimal(150000))},
                {"name": "Equity-Linked Saving Scheme (ELSS)", "max": float(Decimal(999999))},
                {"name": "National Savings Certificate (NSC)", "max": float(Decimal(999999))},
                {"name": "Unit-Linked Insurance Plans (ULIPs)", "max": float(Decimal(999999))},
                {"name": "Pension Plans (80CCC)", "max": float(Decimal(150000))},
                {"name": "NPS (80CCD(1))", "max": float(Decimal(150000))},
            ],
            "note": "Total deduction across all 80C items capped at Rs. 1,50,000"
        }


class SmartDeductionAdvisor:
    """Suggests optimal deductions based on income and profile"""

    @staticmethod
    def suggest_deductions(
        gross_income: Decimal,
        age: int,
        has_dependents: bool,
        has_home_loan: bool,
        residency_status: ResidencyStatus,
    ) -> List[Dict]:
        """
        Suggest applicable and beneficial deductions.
        
        Returns list of suggestions with estimated tax savings.
        """
        suggestions = []
        
        # Medical Insurance - almost always beneficial
        if age >= 40:
            suggestions.append({
                "section": "80D",
                "description": "Health Insurance Premium",
                "max_limit": 100000 if age >= 60 else 50000,
                "estimated_tax_saving": 50000 * 0.3,  # 30% tax bracket
                "priority": "HIGH",
                "reason": "Essential for health protection; immediate tax benefit"
            })
        
        # Home Loan Interest - if applicable
        if has_home_loan:
            suggestions.append({
                "section": "80EE",
                "description": "Home Loan Interest Deduction",
                "max_limit": 150000,
                "estimated_tax_saving": 150000 * 0.3,
                "priority": "HIGH",
                "reason": "Significant deduction for first-time home buyers"
            })
        
        # NPS Contribution - for long-term tax planning
        if residency_status in [ResidencyStatus.ROR, ResidencyStatus.RNOR]:
            suggestions.append({
                "section": "80CCD(1)",
                "description": "National Pension Scheme",
                "max_limit": min(gross_income * Decimal(0.1), Decimal(150000)),
                "estimated_tax_saving": 100000 * 0.3,
                "priority": "MEDIUM",
                "reason": "Tax-deferred growth + immediate deduction + post-retirement income"
            })
        
        # PPF - safe and reliable
        suggestions.append({
            "section": "80C",
            "description": "Public Provident Fund",
            "max_limit": 150000,
            "estimated_tax_saving": 45000 * 0.3,  # Average investment
            "priority": "MEDIUM",
            "reason": "Safe investment with guaranteed returns + tax benefits"
        })
        
        return suggestions
