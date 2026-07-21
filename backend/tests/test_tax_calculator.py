"""
Unit tests for Tax Calculator Engine
"""

import pytest
from decimal import Decimal
from backend.app.tax_calculator import (
    TaxCalculator,
    TaxRegime,
    ResidencyStatus,
    IncomeSource,
    Deduction,
)
from backend.app.deduction_rules import DeductionRules
from backend.app.deduction_rules import ResidencyStatus as DSResidencyStatus


class TestTaxCalculator:
    """Tests for TaxCalculator class"""

    @pytest.fixture
    def calculator(self):
        """Initialize calculator for AY 2026-27"""
        return TaxCalculator(assessment_year=2026)

    def test_calculator_initialization(self, calculator):
        """Test calculator initializes correctly"""
        assert calculator.assessment_year == 2026
        assert calculator.financial_year == 2025

    def test_simple_salary_income_old_regime(self, calculator):
        """Test basic salary income calculation in old regime"""
        income_sources = [
            IncomeSource(
                name="Salary",
                amount=Decimal(900000),
                source_type="salary",
                is_salaried=True,
            )
        ]
        
        deductions = [
            Deduction(
                section="80C",
                description="PPF Contribution",
                amount=Decimal(100000),
                max_limit=Decimal(150000),
                is_applicable=True,
            )
        ]
        
        result = calculator.calculate(
            income_sources=income_sources,
            deductions=deductions,
            residency_status=ResidencyStatus.ROR,
            preferred_regime=TaxRegime.OLD,
        )
        
        assert result.regime_used == TaxRegime.OLD
        assert result.total_income == Decimal(800000)  # 900000 - 100000
        # 800000 income: 250000 tax-free, 250000 at 5% = 12500, 300000 at 20% = 60000
        # Total tax = 72500 + 4% cess (2900) = 75400
        assert result.total_tax >= Decimal(75000)
        assert result.total_tax <= Decimal(76000)

    def test_nri_income_calculation(self, calculator):
        """Test NRI income without deductions"""
        income_sources = [
            IncomeSource(
                name="Salary (Abroad)",
                amount=Decimal(2000000),
                source_type="salary",
            ),
            IncomeSource(
                name="Interest (NRE)",
                amount=Decimal(500000),
                source_type="interest",
            ),
        ]
        
        result = calculator.calculate(
            income_sources=income_sources,
            deductions=[],
            residency_status=ResidencyStatus.NRI,
        )
        
        assert result.total_income == Decimal(2500000)
        assert result.residency_status == ResidencyStatus.NRI

    def test_regime_comparison(self, calculator):
        """Test comparison between old and new regime"""
        income_sources = [
            IncomeSource(
                name="Salary",
                amount=Decimal(1500000),
                source_type="salary",
            )
        ]
        
        deductions = [
            Deduction(
                section="80C",
                description="PPF",
                amount=Decimal(150000),
                max_limit=Decimal(150000),
                is_applicable=True,
            ),
            Deduction(
                section="80D",
                description="Health Insurance",
                amount=Decimal(50000),
                max_limit=Decimal(100000),
                is_applicable=True,
            ),
        ]
        
        old_result, new_result = calculator.compare_regimes(
            income_sources=income_sources,
            deductions=deductions,
            residency_status=ResidencyStatus.ROR,
        )
        
        assert old_result.regime_used == TaxRegime.OLD
        assert new_result.regime_used == TaxRegime.NEW

    def test_tds_credit_application(self, calculator):
        """Test TDS credit reduces tax payable"""
        income_sources = [
            IncomeSource(
                name="Salary",
                amount=Decimal(1000000),
                source_type="salary",
            )
        ]
        
        result = calculator.calculate(
            income_sources=income_sources,
            deductions=[],
            tds_credited=Decimal(100000),
            residency_status=ResidencyStatus.ROR,
        )
        
        assert result.tds_credited == Decimal(100000)

    def test_multiple_income_sources(self, calculator):
        """Test calculation with multiple income sources"""
        income_sources = [
            IncomeSource(
                name="Salary",
                amount=Decimal(1200000),
                source_type="salary",
            ),
            IncomeSource(
                name="Dividend",
                amount=Decimal(300000),
                source_type="dividend",
            ),
            IncomeSource(
                name="Rental Income",
                amount=Decimal(200000),
                source_type="rental",
            ),
            IncomeSource(
                name="Interest",
                amount=Decimal(100000),
                source_type="interest",
            ),
        ]
        
        result = calculator.calculate(
            income_sources=income_sources,
            deductions=[],
            residency_status=ResidencyStatus.ROR,
        )
        
        assert result.total_income == Decimal(1800000)

    def test_rnor_residency_status(self, calculator):
        """Test RNOR (Resident but Not Ordinarily Resident) status"""
        income_sources = [
            IncomeSource(
                name="Salary",
                amount=Decimal(2000000),
                source_type="salary",
            )
        ]
        
        result = calculator.calculate(
            income_sources=income_sources,
            deductions=[],
            residency_status=ResidencyStatus.RNOR,
        )
        
        assert result.residency_status == ResidencyStatus.RNOR

    def test_tax_summary_generation(self, calculator):
        """Test tax summary generation"""
        income_sources = [
            IncomeSource(
                name="Salary",
                amount=Decimal(1000000),
                source_type="salary",
            )
        ]
        
        result = calculator.calculate(
            income_sources=income_sources,
            deductions=[],
            residency_status=ResidencyStatus.ROR,
        )
        
        summary = calculator.get_tax_summary(result)
        
        assert summary["assessment_year"] == 2026
        assert "total_tax" in summary

    def test_zero_income(self, calculator):
        """Test calculation with zero income"""
        result = calculator.calculate(
            income_sources=[],
            deductions=[],
            residency_status=ResidencyStatus.ROR,
        )
        
        assert result.total_income == Decimal(0)
        assert result.total_tax == Decimal(0)


class TestDeductionRules:
    """Tests for DeductionRules class"""

    def test_get_deduction_rule(self):
        """Test retrieving deduction rule"""
        rule = DeductionRules.get_deduction_rule("80C")
        
        assert rule is not None
        assert rule.section == "80C"
        assert rule.max_limit == Decimal(150000)

    def test_validate_deduction_success(self):
        """Test successful deduction validation"""
        result = DeductionRules.validate_deduction(
            section="80C",
            amount=Decimal(100000),
            residency_status=DSResidencyStatus.ROR,
        )
        
        assert result["valid"] is True
        assert result["allowed_amount"] == Decimal(100000)

    def test_validate_deduction_exceeds_limit(self):
        """Test deduction exceeding limit is capped"""
        result = DeductionRules.validate_deduction(
            section="80C",
            amount=Decimal(250000),
            residency_status=DSResidencyStatus.ROR,
        )
        
        assert result["valid"] is True
        assert result["allowed_amount"] == Decimal(150000)

    def test_get_80c_eligibility(self):
        """Test 80C composite limit info"""
        info = DeductionRules.get_80c_eligibility()
        
        assert info["limit"] == 150000.0
        assert len(info["items"]) > 0
