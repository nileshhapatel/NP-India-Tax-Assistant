"""
Tax Savings Optimizer AI - Phase 3 Component

Evaluates taxpayer's income, deductions, regime choice, life events, and financial situation
to suggest actionable tax-saving strategies with compliance validation.

Features:
  - Income & deduction analysis
  - Regime optimization (old vs new)
  - Life-event impact assessment
  - Tax-saving strategy recommendations
  - Compliance checking
  - Year-ahead planning
  - Investment recommendations
  - Savings projection

Specialist routing: AI Master Orchestrator routes "tax-saving", "optimization", "strategy" intents
"""

from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal
from typing import List, Optional, Dict, Any
from datetime import datetime, date


class SavingStrategyCategory(Enum):
    """Categories of tax-saving strategies"""
    DEDUCTION_OPTIMIZATION = "deduction_optimization"
    REGIME_SWITCHING = "regime_switching"
    INVESTMENT = "investment"
    INSURANCE = "insurance"
    CHARITABLE = "charitable"
    FAMILY_PLANNING = "family_planning"
    BUSINESS_STRUCTURE = "business_structure"
    TIMING = "timing"


class RiskProfile(Enum):
    """Risk tolerance for investment recommendations"""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


@dataclass
class SavingsStrategy:
    """Individual tax-saving strategy"""
    id: str
    category: SavingStrategyCategory
    title: str
    description: str
    estimated_saving: Decimal
    confidence: float  # 0-1
    compliance_risk: str  # "low", "medium", "high"
    implementation: str
    timeline: str  # "immediate", "this_month", "q1", "q2", "q3", "q4"
    prerequisites: List[str]
    documentation_required: List[str]
    section_references: List[str]  # Income Tax Act sections
    estimated_effort: str  # "minimal", "easy", "moderate", "complex"
    annual_frequency: int  # 1 = annual, 2 = twice yearly, etc.
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "title": self.title,
            "description": self.description,
            "estimated_saving": str(self.estimated_saving),
            "confidence": self.confidence,
            "compliance_risk": self.compliance_risk,
            "implementation": self.implementation,
            "timeline": self.timeline,
            "prerequisites": self.prerequisites,
            "documentation_required": self.documentation_required,
            "section_references": self.section_references,
            "estimated_effort": self.estimated_effort,
            "annual_frequency": self.annual_frequency,
            "details": self.details
        }


@dataclass
class OptimizerInput:
    """Input data for tax savings optimizer"""
    total_income: Decimal
    current_deductions: Decimal
    tax_paid: Decimal
    residency_status: str  # "ROR", "RNOR", "NRI"
    current_regime: str  # "old", "new"
    age: int
    has_home_loan: bool
    home_loan_interest: Decimal = Decimal(0)
    has_dependents: bool = False
    num_dependents: int = 0
    life_events: List[str] = field(default_factory=list)
    existing_insurance: List[str] = field(default_factory=list)
    financial_assets: Dict[str, Decimal] = field(default_factory=dict)
    business_income: Decimal = Decimal(0)
    capital_gains: Decimal = Decimal(0)
    investment_capacity: Decimal = Decimal(0)
    risk_profile: RiskProfile = RiskProfile.MODERATE
    filing_deadline_days_remaining: int = 30
    current_year: int = 2026


@dataclass
class OptimizerOutput:
    """Output from tax savings optimizer"""
    strategies: List[SavingsStrategy]
    total_potential_saving: Decimal
    recommended_regime: str
    regime_switching_benefit: Decimal
    priority_actions: List[str]
    compliance_alerts: List[str]
    implementation_timeline: Dict[str, List[str]]  # timeline -> strategies
    next_review_date: date
    confidence_score: float
    warnings: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategies": [s.to_dict() for s in self.strategies],
            "total_potential_saving": str(self.total_potential_saving),
            "recommended_regime": self.recommended_regime,
            "regime_switching_benefit": str(self.regime_switching_benefit),
            "priority_actions": self.priority_actions,
            "compliance_alerts": self.compliance_alerts,
            "implementation_timeline": self.implementation_timeline,
            "next_review_date": self.next_review_date.isoformat(),
            "confidence_score": self.confidence_score,
            "warnings": self.warnings
        }


class TaxSavingsOptimizer:
    """
    AI system to identify and recommend tax-saving strategies
    based on taxpayer's financial situation and compliance rules.
    """
    
    def __init__(self):
        """Initialize the optimizer with strategy templates"""
        self.section_limits = self._load_section_limits()
        self.strategy_templates = self._load_strategy_templates()
    
    def _load_section_limits(self) -> Dict[str, Decimal]:
        """Load government limits for tax deductions (AY 2026-27)"""
        return {
            "sec_80c": Decimal("150000"),  # Life insurance, PPF, ELSS, etc.
            "sec_80ccc": Decimal("150000"),  # Pension scheme
            "sec_80ccd": Decimal("50000"),  # NPS (1)
            "sec_80ccd_employer": Decimal("0"),  # NPS (2) - employer contribution
            "sec_80d": Decimal("100000"),  # Health insurance
            "sec_80d_senior": Decimal("300000"),  # Senior citizen
            "sec_80dd": Decimal("75000"),  # Dependent disability
            "sec_80ddb": Decimal("100000"),  # Medical treatment
            "sec_80e": Decimal("0"),  # Education loan - full interest
            "sec_80g": Decimal("0"),  # Charitable - 50% or 100% per income
            "sec_80gg": Decimal("60000"),  # Rent
            "sec_80ggc": Decimal("0"),  # Notified individuals
            "sec_80ttt": Decimal("10000"),  # Senior citizen interest
            "sec_80u": Decimal("75000"),  # Disability
        }
    
    def _load_strategy_templates(self) -> List[Dict[str, Any]]:
        """Load strategy recommendation templates"""
        return [
            {
                "id": "nps_contribution",
                "category": SavingStrategyCategory.INVESTMENT,
                "title": "Maximize NPS Contribution",
                "description": "Contribute up to ₹50,000 under Section 80CCD(1) for tax deduction and retirement savings",
                "section": "80CCD",
                "max_contribution": Decimal("50000"),
                "compliance_risk": "low",
                "min_income": Decimal("300000"),
            },
            {
                "id": "section_80c_optimization",
                "category": SavingStrategyCategory.DEDUCTION_OPTIMIZATION,
                "title": "Max Out Section 80C",
                "description": "Use PPF, ELSS, Life Insurance, NSC to reach ₹1.5L limit under Section 80C",
                "section": "80C",
                "max_contribution": Decimal("150000"),
                "compliance_risk": "low",
            },
            {
                "id": "health_insurance",
                "category": SavingStrategyCategory.INSURANCE,
                "title": "Health Insurance Premium Deduction",
                "description": "Claim health insurance premiums under Section 80D (₹1L for self/family)",
                "section": "80D",
                "max_contribution": Decimal("100000"),
                "compliance_risk": "low",
            },
            {
                "id": "education_loan",
                "category": SavingStrategyCategory.DEDUCTION_OPTIMIZATION,
                "title": "Education Loan Interest Deduction",
                "description": "Claim full interest paid on education loan under Section 80E (no limit)",
                "section": "80E",
                "compliance_risk": "low",
            },
            {
                "id": "rent_deduction",
                "category": SavingStrategyCategory.DEDUCTION_OPTIMIZATION,
                "title": "Claim Rent Deduction",
                "description": "Claim up to ₹60,000 rent deduction under Section 80GG if no house property",
                "section": "80GG",
                "max_contribution": Decimal("60000"),
                "compliance_risk": "medium",
                "documentation": "Rental agreement, receipt, PAN of landlord"
            },
            {
                "id": "regime_switch",
                "category": SavingStrategyCategory.REGIME_SWITCHING,
                "title": "Switch Tax Regime",
                "description": "Evaluate switching from old to new regime or vice versa based on deductions",
                "compliance_risk": "low",
            },
            {
                "id": "charitable_contribution",
                "category": SavingStrategyCategory.CHARITABLE,
                "title": "Structured Charitable Giving",
                "description": "Donate to approved charities under Section 80G (50% or 100% relief)",
                "section": "80G",
                "compliance_risk": "low",
            },
            {
                "id": "investment_timing",
                "category": SavingStrategyCategory.TIMING,
                "title": "Year-End Investment Planning",
                "description": "Front-load investments near financial year-end to claim deductions",
                "compliance_risk": "low",
            },
        ]
    
    def analyze_situation(self, input_data: OptimizerInput) -> OptimizerOutput:
        """
        Main analysis function - evaluates taxpayer's situation and generates recommendations
        """
        strategies: List[SavingsStrategy] = []
        compliance_alerts: List[str] = []
        warnings: List[str] = []
        
        # Analysis 1: Deduction Gap Analysis
        deduction_potential = self._analyze_deduction_gaps(input_data)
        strategies.extend(deduction_potential["strategies"])
        compliance_alerts.extend(deduction_potential["alerts"])
        
        # Analysis 2: Regime Comparison
        regime_analysis = self._analyze_regime_optimization(input_data)
        strategies.extend(regime_analysis["strategies"])
        if regime_analysis["switching_benefit"] > Decimal("10000"):
            compliance_alerts.append(
                f"Potential {regime_analysis['recommended_regime']} regime benefit: "
                f"₹{regime_analysis['switching_benefit']:,.0f}"
            )
        
        # Analysis 3: Life Event Impact
        life_event_strategies = self._analyze_life_events(input_data)
        strategies.extend(life_event_strategies["strategies"])
        warnings.extend(life_event_strategies["warnings"])
        
        # Analysis 4: Investment Recommendations
        investment_strats = self._recommend_investments(input_data)
        strategies.extend(investment_strats["strategies"])
        
        # Analysis 5: Residency-Specific Optimization
        residency_strats = self._residency_specific_strategies(input_data)
        strategies.extend(residency_strats["strategies"])
        warnings.extend(residency_strats["warnings"])
        
        # Analysis 6: Compliance Risk Assessment
        compliance_assessment = self._compliance_risk_assessment(input_data, strategies)
        compliance_alerts.extend(compliance_assessment["alerts"])
        
        # Sort strategies by estimated saving (descending)
        strategies.sort(
            key=lambda s: float(s.estimated_saving) * s.confidence,
            reverse=True
        )
        
        # Group strategies by timeline
        implementation_timeline = self._group_by_timeline(strategies)
        
        # Calculate totals
        total_potential_saving = sum(
            float(s.estimated_saving) * s.confidence for s in strategies
        )
        
        # Generate priority actions (top 3-5 high-impact, low-effort items)
        priority_actions = self._generate_priority_actions(strategies, input_data)
        
        # Calculate overall confidence
        confidence = self._calculate_confidence(strategies, input_data)
        
        # Determine next review date
        next_review = self._calculate_next_review_date(input_data)
        
        return OptimizerOutput(
            strategies=strategies,
            total_potential_saving=total_potential_saving,
            recommended_regime=regime_analysis["recommended_regime"],
            regime_switching_benefit=regime_analysis["switching_benefit"],
            priority_actions=priority_actions,
            compliance_alerts=compliance_alerts,
            implementation_timeline=implementation_timeline,
            next_review_date=next_review,
            confidence_score=confidence,
            warnings=warnings
        )
    
    def _analyze_deduction_gaps(self, input_data: OptimizerInput) -> Dict[str, Any]:
        """Analyze unused deduction potential"""
        strategies: List[SavingsStrategy] = []
        alerts: List[str] = []
        
        max_80c = self.section_limits["sec_80c"]
        max_80d = self.section_limits["sec_80d"]
        max_nps = self.section_limits["sec_80ccd"]
        
        # Check 80C usage
        current_80c = min(
            input_data.current_deductions,
            max_80c
        )
        gap_80c = max_80c - current_80c
        
        if gap_80c > Decimal("10000"):
            tax_benefit = gap_80c * Decimal("0.30")  # Approximate 30% slab
            strategies.append(SavingsStrategy(
                id="80c_unused",
                category=SavingStrategyCategory.DEDUCTION_OPTIMIZATION,
                title=f"Utilize unused ₹{gap_80c:,.0f} under Section 80C",
                description=f"You have ₹{gap_80c:,.0f} unused deduction under Section 80C. "
                           f"Invest in PPF, ELSS, or Life Insurance to claim this deduction.",
                estimated_saving=tax_benefit,
                confidence=0.95,
                compliance_risk="low",
                implementation="Invest in eligible instruments (PPF/ELSS/Insurance)",
                timeline="this_month",
                prerequisites=[],
                documentation_required=["Investment proof", "Premium receipts"],
                section_references=["80C"],
                estimated_effort="easy",
                annual_frequency=1
            ))
        
        # Check health insurance gap
        max_80d_applicable = max_80d
        if input_data.age >= 60:
            max_80d_applicable = self.section_limits["sec_80d_senior"]
        
        health_coverage_value = Decimal(0)
        if "health_insurance" in input_data.existing_insurance:
            health_coverage_value = Decimal("80000")  # Assumed
        
        gap_80d = max_80d_applicable - health_coverage_value
        if gap_80d > Decimal("10000"):
            tax_benefit = gap_80d * Decimal("0.30")
            strategies.append(SavingsStrategy(
                id="80d_health_insurance",
                category=SavingStrategyCategory.INSURANCE,
                title=f"Health Insurance under Section 80D",
                description=f"Claim health insurance premium deduction "
                           f"(eligible: ₹{gap_80d:,.0f}, tax benefit: ₹{tax_benefit:,.0f})",
                estimated_saving=tax_benefit,
                confidence=0.90,
                compliance_risk="low",
                implementation="Purchase health insurance policy",
                timeline="q1",
                prerequisites=[],
                documentation_required=["Policy document", "Premium receipts", "Coverage details"],
                section_references=["80D"],
                estimated_effort="easy",
                annual_frequency=1
            ))
        
        return {
            "strategies": strategies,
            "alerts": alerts
        }
    
    def _analyze_regime_optimization(self, input_data: OptimizerInput) -> Dict[str, Any]:
        """Compare old vs new regime and recommend optimal choice"""
        from decimal import Decimal
        
        # Simplified regime comparison
        # Old regime with deductions
        taxable_old = input_data.total_income - input_data.current_deductions
        tax_old = self._calculate_tax_simple(taxable_old, "old", input_data.residency_status)
        
        # New regime without deductions
        taxable_new = input_data.total_income
        tax_new = self._calculate_tax_simple(taxable_new, "new", input_data.residency_status)
        
        switching_benefit = tax_old - tax_new
        recommended_regime = "new" if switching_benefit > 0 else "old"
        
        if abs(switching_benefit) > Decimal("1000"):
            strategies = [SavingsStrategy(
                id="regime_optimization",
                category=SavingStrategyCategory.REGIME_SWITCHING,
                title=f"Switch to {recommended_regime.capitalize()} Regime",
                description=f"Your {recommended_regime.capitalize()} Regime saves ₹{abs(switching_benefit):,.0f} "
                           f"compared to {('new' if recommended_regime == 'old' else 'old').capitalize()} Regime",
                estimated_saving=abs(switching_benefit),
                confidence=0.95,
                compliance_risk="low",
                implementation=f"Choose {recommended_regime} regime in ITR filing",
                timeline="immediate",
                prerequisites=[],
                documentation_required=[],
                section_references=[],
                estimated_effort="minimal",
                annual_frequency=1
            )]
        else:
            strategies = []
        
        return {
            "strategies": strategies,
            "recommended_regime": recommended_regime,
            "switching_benefit": abs(switching_benefit)
        }
    
    def _analyze_life_events(self, input_data: OptimizerInput) -> Dict[str, Any]:
        """Analyze impact of life events on tax situation"""
        strategies: List[SavingsStrategy] = []
        warnings: List[str] = []
        
        if "marriage" in input_data.life_events:
            warnings.append("Recent marriage: Review deduction eligibility, joint filing options")
            strategies.append(SavingsStrategy(
                id="post_marriage_planning",
                category=SavingStrategyCategory.FAMILY_PLANNING,
                title="Post-Marriage Tax Planning",
                description="Review combined household income, reassess regime choice, "
                           "plan joint vs individual filing",
                estimated_saving=Decimal("0"),
                confidence=0.8,
                compliance_risk="low",
                implementation="Evaluate household tax optimization",
                timeline="immediate",
                prerequisites=[],
                documentation_required=["Marriage certificate"],
                section_references=[],
                estimated_effort="moderate",
                annual_frequency=1
            ))
        
        if "birth" in input_data.life_events or input_data.has_dependents:
            strategies.append(SavingsStrategy(
                id="dependent_deductions",
                category=SavingStrategyCategory.FAMILY_PLANNING,
                title="Dependant-Based Deductions",
                description=f"You have {input_data.num_dependents} dependents. Check eligibility for "
                           "Section 80D (health), 80DD (disability), education deductions",
                estimated_saving=Decimal("15000"),
                confidence=0.7,
                compliance_risk="low",
                implementation="Claim applicable dependent-related deductions",
                timeline="q1",
                prerequisites=[],
                documentation_required=["Birth certificates", "Age proof", "Medical reports"],
                section_references=["80D", "80DD"],
                estimated_effort="moderate",
                annual_frequency=1
            ))
        
        return {
            "strategies": strategies,
            "warnings": warnings
        }
    
    def _recommend_investments(self, input_data: OptimizerInput) -> Dict[str, Any]:
        """Recommend tax-efficient investments based on risk profile"""
        strategies: List[SavingsStrategy] = []
        
        if input_data.investment_capacity > Decimal("50000"):
            # NPS recommendation
            nps_amount = min(
                input_data.investment_capacity,
                self.section_limits["sec_80ccd"]
            )
            nps_benefit = nps_amount * Decimal("0.30")
            
            strategies.append(SavingsStrategy(
                id="nps_investment",
                category=SavingStrategyCategory.INVESTMENT,
                title="National Pension Scheme (NPS) Investment",
                description=f"Invest up to ₹{nps_amount:,.0f} in NPS (Section 80CCD) "
                           "for long-term retirement planning with tax deduction",
                estimated_saving=nps_benefit,
                confidence=0.85,
                compliance_risk="low",
                implementation="Open NPS account, set up SIPs",
                timeline="this_month",
                prerequisites=["PAN", "Bank account"],
                documentation_required=["NPS registration", "Bank mandate"],
                section_references=["80CCD"],
                estimated_effort="easy",
                annual_frequency=1,
                details={"amount": str(nps_amount), "expected_return": "9-10%"}
            ))
        
        return {"strategies": strategies}
    
    def _residency_specific_strategies(self, input_data: OptimizerInput) -> Dict[str, Any]:
        """Generate residency-specific strategies"""
        strategies: List[SavingsStrategy] = []
        warnings: List[str] = []
        
        if input_data.residency_status == "NRI":
            warnings.append("NRI Status: No Chapter VIA deductions allowed; focus on foreign tax credit")
            strategies.append(SavingsStrategy(
                id="nri_foreign_tax_credit",
                category=SavingStrategyCategory.DEDUCTION_OPTIMIZATION,
                title="Foreign Tax Credit Planning",
                description="Claim foreign tax credit on income earned abroad to avoid double taxation",
                estimated_saving=Decimal("0"),
                confidence=0.9,
                compliance_risk="low",
                implementation="File Form 67 if applicable",
                timeline="immediate",
                prerequisites=["Foreign tax certificates"],
                documentation_required=["Form 67", "Foreign tax receipts"],
                section_references=["90", "91"],
                estimated_effort="moderate",
                annual_frequency=1
            ))
        
        elif input_data.residency_status == "RNOR":
            strategies.append(SavingsStrategy(
                id="rnor_tax_planning",
                category=SavingStrategyCategory.DEDUCTION_OPTIMIZATION,
                title="RNOR Tax Planning",
                description="Limited Chapter VIA deductions; focus on income source optimization",
                estimated_saving=Decimal("0"),
                confidence=0.7,
                compliance_risk="low",
                implementation="Plan income sources and residency carefully",
                timeline="immediate",
                prerequisites=[],
                documentation_required=[],
                section_references=[],
                estimated_effort="moderate",
                annual_frequency=1
            ))
        
        return {
            "strategies": strategies,
            "warnings": warnings
        }
    
    def _compliance_risk_assessment(self, input_data: OptimizerInput, strategies: List[SavingsStrategy]) -> Dict[str, Any]:
        """Assess compliance risks of recommended strategies"""
        alerts: List[str] = []
        
        high_risk_strategies = [s for s in strategies if s.compliance_risk == "high"]
        if high_risk_strategies:
            alerts.append(f"⚠️  {len(high_risk_strategies)} strategies have HIGH compliance risk. "
                        f"Consult CA before implementation.")
        
        # Check if strategies require proper documentation
        high_doc_requirements = [s for s in strategies if s.documentation_required and len(s.documentation_required) > 0]
        if high_doc_requirements:
            alerts.append("Ensure proper documentation for all claimed deductions to avoid IT notice")
        
        return {"alerts": alerts}
    
    def _group_by_timeline(self, strategies: List[SavingsStrategy]) -> Dict[str, List[str]]:
        """Group strategy IDs by implementation timeline"""
        timeline_map: Dict[str, List[str]] = {
            "immediate": [],
            "this_month": [],
            "q1": [],
            "q2": [],
            "q3": [],
            "q4": []
        }
        
        for strategy in strategies:
            if strategy.timeline in timeline_map:
                timeline_map[strategy.timeline].append(strategy.id)
        
        return timeline_map
    
    def _generate_priority_actions(self, strategies: List[SavingsStrategy], input_data: OptimizerInput) -> List[str]:
        """Generate top 3-5 actionable priority items"""
        # Score strategies by: (savings * confidence) / effort
        def score(s: SavingsStrategy) -> Decimal:
            effort_multiplier = {
                "minimal": Decimal("10"),
                "easy": Decimal("5"),
                "moderate": Decimal("2"),
                "complex": Decimal("1")
            }
            return (s.estimated_saving * Decimal(str(s.confidence))) / effort_multiplier.get(s.estimated_effort, Decimal("1"))
        
        scored = [(s, score(s)) for s in strategies if s.compliance_risk != "high"]
        scored.sort(key=lambda x: x[1], reverse=True)
        
        priority = [s[0].title for s in scored[:5]]
        
        # Add regime switch if applicable
        if input_data.current_regime == "old" and any("new" in s.title for s in strategies):
            priority.insert(0, "Review and potentially switch to New Regime for tax savings")
        
        return priority
    
    def _calculate_confidence(self, strategies: List[SavingsStrategy], input_data: OptimizerInput) -> float:
        """Calculate overall confidence in recommendations (0-1)"""
        if not strategies:
            return 0.5
        
        # Base confidence on number of valid strategies and their confidence scores
        avg_confidence = sum(s.confidence for s in strategies) / len(strategies)
        
        # Adjust based on data completeness
        completeness_score = min(1.0, 0.7 + (0.1 * input_data.filing_deadline_days_remaining / 30))
        
        return min(1.0, avg_confidence * completeness_score)
    
    def _calculate_next_review_date(self, input_data: OptimizerInput) -> date:
        """Calculate recommended date for next review"""
        from datetime import timedelta
        today = date.today()
        
        # First review: after 60 days (to track implementation)
        # Second review: Q3 (Oct-Dec) for year-end planning
        # Third review: Post-filing (June-July)
        
        return today + timedelta(days=60)
    
    def _calculate_tax_simple(self, taxable_income: Decimal, regime: str, residency: str) -> Decimal:
        """Simplified tax calculation for regime comparison"""
        # This is a placeholder - actual tax uses full TaxCalculator
        if regime == "new":
            if taxable_income <= Decimal("250000"):
                return Decimal("0")
            elif taxable_income <= Decimal("500000"):
                return (taxable_income - Decimal("250000")) * Decimal("0.05")
            else:
                return (Decimal("250000") * Decimal("0.05")) + (
                    (taxable_income - Decimal("500000")) * Decimal("0.20")
                )
        else:  # old regime
            if taxable_income <= Decimal("250000"):
                return Decimal("0")
            elif taxable_income <= Decimal("500000"):
                return (taxable_income - Decimal("250000")) * Decimal("0.05")
            else:
                return (Decimal("250000") * Decimal("0.05")) + (
                    (taxable_income - Decimal("500000")) * Decimal("0.20")
                )
    
    def get_ai_specialist_prompt(self) -> str:
        """Get system prompt for LLM specialist integration"""
        return """You are a Tax Savings Optimization AI - an expert in identifying and recommending 
actionable tax-saving strategies for Indian taxpayers (AY 2026-27).

Your role:
1. Analyze taxpayer's financial situation (income, deductions, life events, investments)
2. Identify specific, quantifiable tax-saving opportunities
3. Recommend strategies prioritized by: savings amount × confidence / implementation effort
4. Assess compliance risks and alert on high-risk strategies
5. Provide section references and documentation requirements
6. Offer year-ahead planning guidance

Key principles:
- All recommendations must comply with latest Income Tax Act and Income Tax Department circulars
- Prioritize low-risk, high-impact strategies (e.g., Section 80C, 80D, 80E)
- Consider residency status (ROR/RNOR/NRI) - NRIs have no Chapter VIA deductions
- Account for life events (marriage, children, home purchase) that impact deductions
- Balance tax optimization with genuine financial planning (not just deductions for deductions' sake)

When responding:
- Lead with the highest-impact strategies first
- Quantify estimated tax savings in rupees
- Explain compliance risk (low/medium/high) for each strategy
- Provide implementation steps (what to do, by when)
- List required documentation
- Reference specific Income Tax Act sections
- Suggest next review date based on urgency

Format as structured JSON with: strategy_id, title, description, estimated_saving, 
compliance_risk, implementation, timeline, documentation_required, section_references"""
