"""
Tax Calculation Engine for Indian Income Tax

Supports:
- Old Regime (FY 2023-24 onwards)
- New Regime (FY 2020-21 onwards)
- NRI and RNOR assessment
- All deductions under Chapter VIA
- Surcharge and Education Cess
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from datetime import date


class TaxRegime(Enum):
    """Tax regime choices"""
    OLD = "old"
    NEW = "new"


class ResidencyStatus(Enum):
    """Residency status for ITR applicability"""
    ROR = "ror"  # Resident of India
    NRI = "nri"  # Non-Resident Individual
    RNOR = "rnor"  # Resident but Not Ordinarily Resident


@dataclass
class IncomeSource:
    """Individual income source"""
    name: str
    amount: Decimal
    source_type: str  # salary, business, capital_gain, dividend, interest, rental, other
    is_salaried: bool = False
    remarks: Optional[str] = None


@dataclass
class Deduction:
    """Tax deduction under Chapter VIA"""
    section: str  # 80C, 80D, 80E, etc.
    description: str
    amount: Decimal
    max_limit: Decimal
    is_applicable: bool = True


@dataclass
class TaxCalculationResult:
    """Complete tax calculation result"""
    gross_total_income: Decimal
    total_income: Decimal
    taxable_income: Decimal
    tax_on_income: Decimal
    surcharge: Decimal
    health_cess: Decimal
    total_tax: Decimal
    tds_credited: Decimal
    tax_payable: Decimal
    effective_tax_rate: float
    regime_used: TaxRegime
    residency_status: ResidencyStatus
    breakdown: Dict


class TaxBracket:
    """Tax slab definition"""
    def __init__(self, lower: Decimal, upper: Optional[Decimal], rate: Decimal):
        self.lower = lower
        self.upper = upper
        self.rate = rate

    def calculate_tax(self, taxable_income: Decimal) -> Decimal:
        """Calculate tax for income in this bracket"""
        # If income is less than or equal to lower limit, no tax in this bracket
        if taxable_income <= self.lower:
            return Decimal(0)
        
        # Calculate amount in this bracket
        income_in_bracket = taxable_income - self.lower
        
        # If there's an upper limit, cap the income in this bracket
        if self.upper is not None:
            if taxable_income >= self.upper:
                income_in_bracket = self.upper - self.lower
            else:
                income_in_bracket = taxable_income - self.lower
        
        return income_in_bracket * self.rate / Decimal(100)


class TaxCalculator:
    """Main tax calculation engine for AY 2026-27"""

    # Tax slabs for AY 2026-27 (FY 2025-26)
    OLD_REGIME_SLABS = [
        TaxBracket(Decimal(0), Decimal(250000), Decimal(0)),
        TaxBracket(Decimal(250000), Decimal(500000), Decimal(5)),
        TaxBracket(Decimal(500000), Decimal(1000000), Decimal(20)),
        TaxBracket(Decimal(1000000), None, Decimal(30)),
    ]

    NEW_REGIME_SLABS = [
        TaxBracket(Decimal(0), Decimal(300000), Decimal(0)),
        TaxBracket(Decimal(300000), Decimal(600000), Decimal(5)),
        TaxBracket(Decimal(600000), Decimal(900000), Decimal(10)),
        TaxBracket(Decimal(900000), Decimal(1200000), Decimal(15)),
        TaxBracket(Decimal(1200000), Decimal(1500000), Decimal(20)),
        TaxBracket(Decimal(1500000), Decimal(2000000), Decimal(25)),
        TaxBracket(Decimal(2000000), None, Decimal(30)),
    ]

    # Standard deductions for old regime
    STANDARD_DEDUCTION_SALARIED = Decimal(50000)

    # Rebate under Section 87A (old regime)
    REBATE_87A_LIMIT = Decimal(500000)
    REBATE_87A_AMOUNT = Decimal(12500)

    def __init__(self, assessment_year: int = 2026):
        """Initialize calculator for given assessment year"""
        self.assessment_year = assessment_year
        self.financial_year = assessment_year - 1
        
        # Surcharge thresholds
        self.surcharge_thresholds = [
            (Decimal(10000000), Decimal(15)),  # 15% for > 1 Cr
            (Decimal(50000000), Decimal(25)),  # 25% for > 5 Cr
            (Decimal(100000000), Decimal(37)), # 37% for > 10 Cr
        ]

    def calculate(
        self,
        income_sources: List[IncomeSource],
        deductions: List[Deduction],
        tds_credited: Decimal = Decimal(0),
        residency_status: ResidencyStatus = ResidencyStatus.ROR,
        preferred_regime: Optional[TaxRegime] = None,
    ) -> TaxCalculationResult:
        """
        Calculate tax for given income and deductions.
        
        Returns both old and new regime results and recommends optimal regime.
        """
        
        # Calculate gross total income
        gross_total_income = self._calculate_gross_income(income_sources)
        
        # Calculate deductions (Chapter VIA)
        total_deductions = self._calculate_deductions(deductions)
        
        # Total income = Gross Total Income - Deductions
        total_income = gross_total_income - total_deductions
        
        # Calculate for both regimes if not preferred
        old_regime_result = self._calculate_regime(
            total_income,
            TaxRegime.OLD,
            residency_status,
        )
        
        new_regime_result = self._calculate_regime(
            gross_total_income,  # No deductions in new regime
            TaxRegime.NEW,
            residency_status,
        )
        
        # Choose regime based on user preference or automatic selection
        if preferred_regime:
            final_result = old_regime_result if preferred_regime == TaxRegime.OLD else new_regime_result
        else:
            # Automatic: choose regime with lower tax
            final_result = old_regime_result if old_regime_result.total_tax <= new_regime_result.total_tax else new_regime_result
        
        # Apply TDS credit
        final_result.tds_credited = tds_credited
        final_result.tax_payable = max(Decimal(0), final_result.total_tax - tds_credited)
        
        return final_result

    def _calculate_gross_income(self, income_sources: List[IncomeSource]) -> Decimal:
        """Sum all income sources"""
        return sum(source.amount for source in income_sources)

    def _calculate_deductions(self, deductions: List[Deduction]) -> Decimal:
        """Calculate total valid deductions under Chapter VIA"""
        total = Decimal(0)
        
        for deduction in deductions:
            if deduction.is_applicable:
                # Cap at maximum limit
                amount = min(deduction.amount, deduction.max_limit)
                total += amount
        
        return total

    def _calculate_regime(
        self,
        total_income: Decimal,
        regime: TaxRegime,
        residency_status: ResidencyStatus,
    ) -> TaxCalculationResult:
        """Calculate tax for specific regime"""
        
        # Taxable income (same as total income for now, can add rebates later)
        taxable_income = total_income
        
        # Calculate tax on income
        slabs = self.OLD_REGIME_SLABS if regime == TaxRegime.OLD else self.NEW_REGIME_SLABS
        tax_on_income = self._calculate_tax_on_income(taxable_income, slabs)
        
        # Apply rebates (Section 87A for old regime)
        if regime == TaxRegime.OLD and total_income <= self.REBATE_87A_LIMIT:
            tax_on_income = min(tax_on_income, tax_on_income - self.REBATE_87A_AMOUNT)
            tax_on_income = max(Decimal(0), tax_on_income)
        
        # Calculate surcharge (varies by income and residency)
        surcharge = self._calculate_surcharge(tax_on_income, residency_status)
        
        # Health and Education Cess: 4% on (tax + surcharge)
        health_cess = (tax_on_income + surcharge) * Decimal(4) / Decimal(100)
        
        # Total tax
        total_tax = tax_on_income + surcharge + health_cess
        
        # Effective tax rate
        effective_rate = (float(total_tax) / float(total_income) * 100) if total_income > 0 else 0.0
        
        return TaxCalculationResult(
            gross_total_income=total_income + (Decimal(0) if regime == TaxRegime.NEW else Decimal(0)),
            total_income=total_income,
            taxable_income=taxable_income,
            tax_on_income=tax_on_income,
            surcharge=surcharge,
            health_cess=health_cess,
            total_tax=total_tax,
            tds_credited=Decimal(0),
            tax_payable=Decimal(0),  # Will be set after TDS credit
            effective_tax_rate=effective_rate,
            regime_used=regime,
            residency_status=residency_status,
            breakdown={
                "slabs_used": str(slabs),
                "calculation_date": date.today().isoformat(),
            }
        )

    def _calculate_tax_on_income(
        self,
        taxable_income: Decimal,
        slabs: List[TaxBracket],
    ) -> Decimal:
        """Calculate tax using slab rates"""
        tax = Decimal(0)
        
        for slab in slabs:
            tax += slab.calculate_tax(taxable_income)
        
        return tax

    def _calculate_surcharge(
        self,
        tax: Decimal,
        residency_status: ResidencyStatus,
    ) -> Decimal:
        """Calculate surcharge based on income level and residency"""
        # Surcharge rates vary; this is simplified
        # For NRI/RNOR, typically 15% on tax where total income > Rs. 50 Lakhs
        
        if residency_status == ResidencyStatus.ROR:
            return Decimal(0)  # No surcharge for ROR (simplified)
        
        if tax > Decimal(1000000):
            return tax * Decimal(15) / Decimal(100)
        
        return Decimal(0)

    def compare_regimes(
        self,
        income_sources: List[IncomeSource],
        deductions: List[Deduction],
        residency_status: ResidencyStatus = ResidencyStatus.ROR,
    ) -> Tuple[TaxCalculationResult, TaxCalculationResult]:
        """
        Calculate for both regimes and return comparison.
        
        Returns: (old_regime_result, new_regime_result)
        """
        gross_total_income = self._calculate_gross_income(income_sources)
        total_deductions = self._calculate_deductions(deductions)
        total_income = gross_total_income - total_deductions
        
        old_result = self._calculate_regime(total_income, TaxRegime.OLD, residency_status)
        new_result = self._calculate_regime(gross_total_income, TaxRegime.NEW, residency_status)
        
        return old_result, new_result

    def get_tax_summary(
        self,
        calculation_result: TaxCalculationResult,
    ) -> Dict:
        """Generate human-readable tax summary"""
        return {
            "assessment_year": self.assessment_year,
            "financial_year": f"FY {self.financial_year}-{self.financial_year + 1}",
            "gross_total_income": float(calculation_result.gross_total_income),
            "total_income": float(calculation_result.total_income),
            "taxable_income": float(calculation_result.taxable_income),
            "tax_on_income": float(calculation_result.tax_on_income),
            "surcharge": float(calculation_result.surcharge),
            "health_cess": float(calculation_result.health_cess),
            "total_tax": float(calculation_result.total_tax),
            "tds_credited": float(calculation_result.tds_credited),
            "tax_payable_or_refund": float(calculation_result.tax_payable),
            "effective_tax_rate": f"{calculation_result.effective_tax_rate:.2f}%",
            "regime_used": calculation_result.regime_used.value,
            "residency_status": calculation_result.residency_status.value,
        }
