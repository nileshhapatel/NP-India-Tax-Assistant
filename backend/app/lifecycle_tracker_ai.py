"""
Lifecycle & Family Event Tracker AI - Phase 3 Component

Prompts taxpayer for life events, records them, and evaluates their impact on:
- Residency status and tax filing requirements
- Deduction eligibility and limits
- Family structure and dependent claims
- Income recognition and timing
- Tax planning opportunities

Life Events Tracked:
  - Marriage / Divorce
  - Birth / Adoption of children
  - Death of dependents or income earners
  - OCI status change
  - Move to/from India (residency change)
  - New employment or job change
  - Business startup / closure
  - Home purchase or sale
  - Loan origination or repayment
  - Investment or divestment
  - Inheritance or gift
  - Emigration / Immigration

Features:
  - Life event classification and timeline
  - Impact analysis on tax situation
  - Residency status recalculation
  - Deduction re-evaluation
  - Documentation requirements
  - Year-ahead planning recommendations
  - Family structure consolidation

Specialist routing: AI Master Orchestrator routes "lifecycle", "event", "family", "planning" intents
"""

from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from datetime import date, datetime, timedelta


class LifeEventCategory(Enum):
    """Categories of life events"""
    FAMILY = "family"
    RESIDENCY = "residency"
    EMPLOYMENT = "employment"
    FINANCIAL = "financial"
    PROPERTY = "property"
    HEALTH = "health"
    LEGAL = "legal"


class LifeEventType(Enum):
    """Specific types of life events"""
    # Family events
    MARRIAGE = "marriage"
    DIVORCE = "divorce"
    BIRTH = "birth"
    ADOPTION = "adoption"
    DEATH = "death"
    
    # Residency events
    OCI_OBTAINED = "oci_obtained"
    OCI_REVOKED = "oci_revoked"
    MOVED_TO_INDIA = "moved_to_india"
    MOVED_FROM_INDIA = "moved_from_india"
    
    # Employment events
    NEW_JOB = "new_job"
    JOB_CHANGE = "job_change"
    JOB_LOSS = "job_loss"
    BUSINESS_STARTUP = "business_startup"
    BUSINESS_CLOSURE = "business_closure"
    
    # Financial events
    HOME_PURCHASE = "home_purchase"
    HOME_SALE = "home_sale"
    LOAN_OBTAINED = "loan_obtained"
    LOAN_REPAID = "loan_repaid"
    INHERITANCE = "inheritance"
    GIFT_RECEIVED = "gift_received"
    
    # Investment events
    MAJOR_INVESTMENT = "major_investment"
    INVESTMENT_SOLD = "investment_sold"
    DIVIDEND_INCOME = "dividend_income"


class ResidencyImpact(Enum):
    """Impact on residency status"""
    NO_CHANGE = "no_change"
    BECOMES_ROR = "becomes_ror"
    BECOMES_RNOR = "becomes_rnor"
    BECOMES_NRI = "becomes_nri"
    RESIDENCY_PENDING = "residency_pending"


@dataclass
class LifeEvent:
    """Single life event entry"""
    id: str
    event_type: LifeEventType
    category: LifeEventCategory
    date_occurred: date
    date_reported: datetime = field(default_factory=datetime.now)
    description: str = ""
    affected_person: str = ""  # Name or "self"
    priority: str = "medium"  # "low", "medium", "high"
    tax_relevant: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    documentation: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "category": self.category.value,
            "date_occurred": self.date_occurred.isoformat(),
            "date_reported": self.date_reported.isoformat(),
            "description": self.description,
            "affected_person": self.affected_person,
            "priority": self.priority,
            "tax_relevant": self.tax_relevant,
            "metadata": self.metadata,
            "documentation": self.documentation
        }


@dataclass
class EventImpactAnalysis:
    """Analysis of life event's tax impact"""
    event_id: str
    event_type: LifeEventType
    residency_impact: ResidencyImpact
    deduction_changes: Dict[str, str]  # section -> impact
    income_recognition_changes: List[str]
    dependent_count_change: int
    filing_requirement_change: bool
    filing_deadline_change: Optional[date] = None
    documentation_required: List[str] = field(default_factory=list)
    actions_needed: List[str] = field(default_factory=list)
    compliance_alerts: List[str] = field(default_factory=list)
    planning_opportunities: List[str] = field(default_factory=list)
    estimated_tax_impact: Optional[Decimal] = None
    high_priority: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "residency_impact": self.residency_impact.value,
            "deduction_changes": self.deduction_changes,
            "income_recognition_changes": self.income_recognition_changes,
            "dependent_count_change": self.dependent_count_change,
            "filing_requirement_change": self.filing_requirement_change,
            "filing_deadline_change": self.filing_deadline_change.isoformat() if self.filing_deadline_change else None,
            "documentation_required": self.documentation_required,
            "actions_needed": self.actions_needed,
            "compliance_alerts": self.compliance_alerts,
            "planning_opportunities": self.planning_opportunities,
            "estimated_tax_impact": str(self.estimated_tax_impact) if self.estimated_tax_impact else None,
            "high_priority": self.high_priority
        }


@dataclass
class LifecycleSummary:
    """Overall lifecycle and family planning summary"""
    events: List[LifeEvent]
    total_events: int
    critical_events: int
    current_family_size: int
    dependents_count: int
    current_residency: str
    residency_change_pending: bool
    impact_analyses: List[EventImpactAnalysis]
    consolidated_actions: List[str]
    consolidated_alerts: List[str]
    planning_recommendations: List[str]
    estimated_tax_impact: Decimal
    next_review_date: date
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "events": [e.to_dict() for e in self.events],
            "total_events": self.total_events,
            "critical_events": self.critical_events,
            "current_family_size": self.current_family_size,
            "dependents_count": self.dependents_count,
            "current_residency": self.current_residency,
            "residency_change_pending": self.residency_change_pending,
            "impact_analyses": [a.to_dict() for a in self.impact_analyses],
            "consolidated_actions": self.consolidated_actions,
            "consolidated_alerts": self.consolidated_alerts,
            "planning_recommendations": self.planning_recommendations,
            "estimated_tax_impact": str(self.estimated_tax_impact),
            "next_review_date": self.next_review_date.isoformat()
        }


class LifecycleTracker:
    """
    Tracks life events and analyzes their tax implications,
    providing guidance on residency, deductions, and family planning.
    """
    
    def __init__(self):
        """Initialize lifecycle tracker"""
        self.event_impacts = self._load_event_impacts()
    
    def _load_event_impacts(self) -> Dict[LifeEventType, Dict[str, Any]]:
        """Load predefined impacts for each event type"""
        return {
            LifeEventType.MARRIAGE: {
                "category": LifeEventCategory.FAMILY,
                "residency_impact": ResidencyImpact.NO_CHANGE,
                "deduction_changes": {
                    "dependent": "+eligible if spouse income < ₹500K"
                },
                "dependent_impact": 0,
                "filing_impact": "Review combined household planning",
                "priority": "medium"
            },
            LifeEventType.BIRTH: {
                "category": LifeEventCategory.FAMILY,
                "residency_impact": ResidencyImpact.NO_CHANGE,
                "deduction_changes": {
                    "80d_dependent": "+eligible",
                    "80dd_dependent": "+eligible if disability",
                    "education": "+eligible for future"
                },
                "dependent_impact": 1,
                "filing_impact": "Add dependent claim from birth date",
                "priority": "high"
            },
            LifeEventType.MOVED_FROM_INDIA: {
                "category": LifeEventCategory.RESIDENCY,
                "residency_impact": ResidencyImpact.BECOMES_NRI,
                "deduction_changes": {
                    "80c": "-NRI ineligible",
                    "80d": "-NRI ineligible",
                    "80g": "-NRI ineligible",
                },
                "filing_impact": "Filing requirement from date of departure",
                "priority": "high"
            },
            LifeEventType.MOVED_TO_INDIA: {
                "category": LifeEventCategory.RESIDENCY,
                "residency_impact": ResidencyImpact.BECOMES_ROR,
                "deduction_changes": {
                    "80c": "+Eligible from date of arrival",
                    "80d": "+Eligible from date of arrival",
                    "80g": "+Eligible from date of arrival",
                },
                "filing_impact": "New filing obligation from arrival date",
                "priority": "high"
            },
            LifeEventType.HOME_PURCHASE: {
                "category": LifeEventCategory.PROPERTY,
                "residency_impact": ResidencyImpact.NO_CHANGE,
                "deduction_changes": {
                    "home_loan_interest": "+Eligible up to ₹200K",
                    "home_loan_principal": "+₹1.5L under 80C"
                },
                "filing_impact": "Claim home loan deductions from next AY",
                "priority": "high"
            },
            LifeEventType.BUSINESS_STARTUP: {
                "category": LifeEventCategory.EMPLOYMENT,
                "residency_impact": ResidencyImpact.NO_CHANGE,
                "deduction_changes": {
                    "business_expense": "+All eligible expenses",
                    "80c_investment": "+Eligible"
                },
                "filing_impact": "File ITR-3 (business); may require Audit",
                "priority": "high"
            },
            LifeEventType.INHERITANCE: {
                "category": LifeEventCategory.FINANCIAL,
                "residency_impact": ResidencyImpact.NO_CHANGE,
                "deduction_changes": {},  # No deduction, but taxable if income generating
                "filing_impact": "No income tax on inheritance itself; tax on generated income",
                "priority": "medium"
            },
            LifeEventType.DEATH: {
                "category": LifeEventCategory.FAMILY,
                "residency_impact": ResidencyImpact.NO_CHANGE,
                "deduction_changes": {},
                "dependent_impact": -1,
                "filing_impact": "Final return required for deceased",
                "priority": "high"
            },
        }
    
    def track_event(self, event: LifeEvent) -> EventImpactAnalysis:
        """Record and analyze a single life event"""
        impact_template = self.event_impacts.get(event.event_type, {})
        
        impact = EventImpactAnalysis(
            event_id=event.id,
            event_type=event.event_type,
            residency_impact=impact_template.get("residency_impact", ResidencyImpact.NO_CHANGE),
            deduction_changes=impact_template.get("deduction_changes", {}),
            income_recognition_changes=[impact_template.get("filing_impact", "")],
            dependent_count_change=impact_template.get("dependent_impact", 0),
            filing_requirement_change=event.event_type in [
                LifeEventType.MOVED_FROM_INDIA,
                LifeEventType.MOVED_TO_INDIA,
                LifeEventType.BUSINESS_STARTUP,
            ],
            high_priority=impact_template.get("priority", "medium") == "high"
        )
        
        # Generate actions and alerts based on event type
        impact.actions_needed = self._generate_actions(event)
        impact.compliance_alerts = self._generate_alerts(event)
        impact.documentation_required = self._get_documentation_required(event)
        impact.planning_opportunities = self._get_planning_opportunities(event)
        
        return impact
    
    def _generate_actions(self, event: LifeEvent) -> List[str]:
        """Generate action items for the event"""
        actions: List[str] = []
        
        if event.event_type == LifeEventType.MARRIAGE:
            actions = [
                "1. Collect spouse's PAN, Aadhaar, income proof",
                "2. Evaluate joint vs individual filing benefit",
                "3. Review combined household deduction eligibility",
                "4. Update nominee/beneficiary documents"
            ]
        elif event.event_type == LifeEventType.BIRTH:
            actions = [
                "1. Register birth and obtain birth certificate",
                "2. Apply for child's PAN (if income-earning)",
                "3. Update health insurance to include child",
                "4. Plan for education deductions (80C ELSS)",
                "5. Claim dependent health insurance from birth date"
            ]
        elif event.event_type == LifeEventType.MOVED_FROM_INDIA:
            actions = [
                "1. Update residency status to NRI in Income Tax portal",
                "2. Report foreign address",
                "3. File ITR from departure date onwards",
                "4. Stop claiming Chapter VIA deductions",
                "5. Track worldwide income and foreign tax credits",
                "6. Keep departure documentation (visa, passport stamps)"
            ]
        elif event.event_type == LifeEventType.HOME_PURCHASE:
            actions = [
                "1. Collect home loan agreement, sanction letter",
                "2. Get interest certificate from bank (Form 16A)",
                "3. Collect property documents, purchase agreement",
                "4. Calculate eligible home loan principal for 80C",
                "5. Claim home loan interest deduction from next FY"
            ]
        elif event.event_type == LifeEventType.BUSINESS_STARTUP:
            actions = [
                "1. Register business (GST, PAN, TAN if applicable)",
                "2. Maintain books of accounts from Day 1",
                "3. File ITR-3 (profit/loss from business)",
                "4. Check if business audit required (turnover > ₹1Cr)",
                "5. Claim all eligible business deductions",
                "6. Track capital investments for depreciation"
            ]
        
        return actions
    
    def _generate_alerts(self, event: LifeEvent) -> List[str]:
        """Generate compliance alerts for the event"""
        alerts: List[str] = []
        
        if event.event_type == LifeEventType.MOVED_FROM_INDIA:
            alerts = [
                "⚠️  Residency change to NRI: Chapter VIA deductions NO LONGER AVAILABLE",
                "⚠️  Foreign tax credit rules now applicable",
                "⚠️  Worldwide income must be reported"
            ]
        elif event.event_type == LifeEventType.BUSINESS_STARTUP:
            alerts = [
                "⚠️  Business income is self-employment income - maintain detailed records",
                "⚠️  TDS may be applicable if B2B transactions",
                "⚠️  Consider GST registration and compliance"
            ]
        elif event.event_type == LifeEventType.MOVED_TO_INDIA:
            alerts = [
                "⚠️  Residency change to ROR: All Chapter VIA deductions available",
                "⚠️  Residency determination year is critical - check 182-day rule",
                "⚠️  Ensure ITR-2 filing from arrival year onwards"
            ]
        
        return alerts
    
    def _get_documentation_required(self, event: LifeEvent) -> List[str]:
        """Get list of documentation needed for this event"""
        docs: List[str] = []
        
        if event.event_type == LifeEventType.MARRIAGE:
            docs = ["Marriage certificate", "Spouse PAN/Aadhaar", "Spouse income proof"]
        elif event.event_type == LifeEventType.BIRTH:
            docs = ["Birth certificate", "Hospital documents"]
        elif event.event_type == LifeEventType.MOVED_FROM_INDIA:
            docs = ["Passport with exit stamp", "Visa/residency proof", "Address proof abroad"]
        elif event.event_type == LifeEventType.HOME_PURCHASE:
            docs = [
                "Property purchase agreement",
                "Home loan agreement",
                "Bank interest certificate (Form 16A)",
                "Property tax receipts"
            ]
        elif event.event_type == LifeEventType.BUSINESS_STARTUP:
            docs = [
                "Business registration certificate",
                "GST registration (if applicable)",
                "Opening bank statement",
                "Books of accounts"
            ]
        
        return docs
    
    def _get_planning_opportunities(self, event: LifeEvent) -> List[str]:
        """Get tax planning opportunities triggered by event"""
        opportunities: List[str] = []
        
        if event.event_type == LifeEventType.MARRIAGE:
            opportunities = [
                "💡 Spouse can claim independent deductions (₹1.5L 80C, ₹1L 80D, etc.)",
                "💡 Can split income and optimize tax brackets",
                "💡 Each spouse can file separately for optimal results"
            ]
        elif event.event_type == LifeEventType.BIRTH:
            opportunities = [
                "💡 Start ELSS/NSC now for child education (20+ years)",
                "💡 Claim health insurance deduction for child",
                "💡 Plan 80C investments for dependent education"
            ]
        elif event.event_type == LifeEventType.HOME_PURCHASE:
            opportunities = [
                "💡 Claim up to ₹200K home loan interest deduction",
                "💡 Claim ₹1.5L principal under 80C over 15-year loan tenure",
                "💡 Total estimated tax savings: ₹50-100K over loan period"
            ]
        elif event.event_type == LifeEventType.BUSINESS_STARTUP:
            opportunities = [
                "💡 All business expenses are deductible",
                "💡 Consider section 80C investments for business income",
                "💡 Explore presumptive income scheme if turnover < ₹1 Cr (44AE)"
            ]
        
        return opportunities
    
    def summarize_lifecycle(self, events: List[LifeEvent], current_state: Dict[str, Any]) -> LifecycleSummary:
        """Generate comprehensive lifecycle summary"""
        
        impact_analyses: List[EventImpactAnalysis] = []
        critical_events_count = 0
        dependent_count = current_state.get("dependents", 0)
        current_residency = current_state.get("residency", "ROR")
        residency_pending = False
        consolidated_alerts: List[str] = []
        consolidated_actions: List[str] = []
        total_tax_impact = Decimal("0")
        
        for event in events:
            analysis = self.track_event(event)
            impact_analyses.append(analysis)
            
            # Update state
            dependent_count += analysis.dependent_count_change
            if analysis.high_priority:
                critical_events_count += 1
            
            # Track residency changes
            if analysis.residency_impact != ResidencyImpact.NO_CHANGE:
                current_residency = analysis.residency_impact.value.replace("becomes_", "").upper()
                if analysis.residency_impact == ResidencyImpact.RESIDENCY_PENDING:
                    residency_pending = True
            
            # Collect alerts and actions
            consolidated_alerts.extend(analysis.compliance_alerts)
            consolidated_actions.extend(analysis.actions_needed)
            
            # Sum tax impacts
            if analysis.estimated_tax_impact:
                total_tax_impact += analysis.estimated_tax_impact
        
        # Generate planning recommendations
        planning_recs = self._generate_planning_recommendations(
            events, current_residency, dependent_count
        )
        
        # Calculate next review date
        next_review = date.today() + timedelta(days=90)
        
        return LifecycleSummary(
            events=events,
            total_events=len(events),
            critical_events=critical_events_count,
            current_family_size=current_state.get("family_size", 1) + dependent_count,
            dependents_count=dependent_count,
            current_residency=current_residency,
            residency_change_pending=residency_pending,
            impact_analyses=impact_analyses,
            consolidated_actions=consolidated_actions,
            consolidated_alerts=consolidated_alerts,
            planning_recommendations=planning_recs,
            estimated_tax_impact=total_tax_impact,
            next_review_date=next_review
        )
    
    def _generate_planning_recommendations(self, events: List[LifeEventType], 
                                         residency: str, dependents: int) -> List[str]:
        """Generate forward-looking planning recommendations"""
        recs: List[str] = []
        
        recs.append("📅 Review tax plan annually after life events")
        recs.append("🔄 Update residency status if any moves planned")
        recs.append(f"👨‍👩‍👧‍👦 Current household has {dependents} dependents - claim all eligible deductions")
        
        if residency == "ROR":
            recs.append("✓ All Chapter VIA deductions available - maximize 80C, 80D coverage")
        elif residency == "NRI":
            recs.append("⚠️  NRI status: Focus on foreign income, foreign tax credits; no Chapter VIA deductions")
        
        recs.append("📋 Keep all event documentation for 7 years (tax audit statute of limitations)")
        
        return recs
    
    def get_ai_specialist_prompt(self) -> str:
        """Get system prompt for LLM specialist integration"""
        return """You are a Lifecycle & Family Event Tracker AI - an expert in analyzing how life events 
impact Indian tax situations (AY 2026-27).

Your role:
1. Record and classify life events (marriage, birth, moves, job changes, etc.)
2. Analyze tax impact of each event on: residency, deductions, filing requirements, dependents
3. Alert on critical compliance changes (NRI status → no deductions, moves → residency re-determination)
4. Generate action items and documentation requirements
5. Identify tax planning opportunities triggered by events
6. Consolidate multi-event impacts into coherent family tax plan
7. Track residency status changes and re-determination timelines

Key event impact areas:
- Residency: MOVED_FROM_INDIA (NRI), MOVED_TO_INDIA (ROR), residency determination by 182-day rule
- Dependents: BIRTH (+), DEATH (-), ADOPTION (+), triggers deduction claims
- Deductions: HOME_PURCHASE (80C principal + interest), BUSINESS_STARTUP (business deductions)
- Filing: New events may trigger new filing requirements or change ITR form type
- Timing: Deductions effective from event date, not full year

When responding:
- Categorize event: FAMILY / RESIDENCY / EMPLOYMENT / FINANCIAL / PROPERTY
- Analyze impact: What changes? From when? What's required?
- Generate actions: Ordered by urgency, with specific documents needed
- Alert on compliance: Missed steps that could trigger IT notices
- Opportunity: Tax savings available from this event
- Timeline: When to claim deductions, file returns, report changes

Format as structured JSON with: event_id, event_type, residency_impact, dependent_change, 
deduction_changes, actions_needed, documentation_required, compliance_alerts, planning_opportunities"""
