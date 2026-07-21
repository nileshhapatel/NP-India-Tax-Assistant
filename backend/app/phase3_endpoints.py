"""
Phase 3: REST API Endpoints for Advanced AI Specialists

Integrates the four Phase 3 AI specialist components into FastAPI routes:
- Tax Savings Optimizer: /api/optimize/tax-savings
- Compliance Validator: /api/validate/compliance
- Reconciliation Expert: /api/reconcile/three-way
- Lifecycle Tracker: /api/track/lifecycle-event

Each endpoint accepts inputs from the frontend, routes to the appropriate specialist,
and returns structured analysis results.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import date, datetime
from enum import Enum

from .tax_savings_optimizer_ai import (
    TaxSavingsOptimizer,
    OptimizerInput,
    RiskProfile,
)
from .compliance_validator_ai import (
    ComplianceValidator,
    ComplianceCheckInput,
    ValidationSeverity
)
from .reconciliation_expert_ai import (
    ReconciliationExpert,
    SourceStatement,
    AISEntry,
    ITREntry,
    RiskLevel
)
from .lifecycle_tracker_ai import (
    LifecycleTracker,
    LifeEvent,
    LifeEventType,
    LifeEventCategory
)

# Create router for Phase 3 endpoints
router = APIRouter(prefix="/api/phase3", tags=["Phase 3 - AI Specialists"])

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class TaxSavingsRequest(BaseModel):
    """Request for tax savings optimization"""
    total_income: float
    current_deductions: float
    tax_paid: float
    residency_status: str  # "ROR", "NRI", "RNOR"
    current_regime: str  # "old", "new"
    age: int
    has_home_loan: bool = False
    has_dependents: bool = False
    num_dependents: int = 0
    investment_capacity: float = 0
    existing_insurance: List[str] = []
    life_events: List[str] = []
    filing_deadline_days_remaining: int = 30
    risk_profile: str = "moderate"  # "conservative", "moderate", "aggressive"


class ComplianceCheckRequest(BaseModel):
    """Request for compliance validation"""
    total_income: float
    residency_status: str
    deductions: Dict[str, float]
    tds_claimed: float = 0
    has_income_from_multiple_sources: bool = False
    documents_uploaded: List[str] = []
    ais_received: bool = False
    form_26as_received: bool = False
    assessment_year: int = 2027


class SourceStatementRequest(BaseModel):
    """Source document entry"""
    id: str
    date: str  # "YYYY-MM-DD"
    amount: float
    description: str
    source_type: str
    document_ref: str


class AISEntryRequest(BaseModel):
    """AIS entry from income tax portal"""
    id: str
    date: str  # "YYYY-MM-DD"
    amount: float
    category: str
    payer_name: str
    payer_pan: str
    deductee_code: str
    form_26as_section: str


class ITREntryRequest(BaseModel):
    """ITR claimed amount"""
    id: str
    date: str  # "YYYY-MM-DD"
    amount: float
    category: str
    description: str
    form_line_item: str


class ReconciliationRequest(BaseModel):
    """Request for three-way reconciliation"""
    source_statements: List[SourceStatementRequest]
    ais_entries: List[AISEntryRequest]
    itr_entries: List[ITREntryRequest]


class LifeEventRequest(BaseModel):
    """Request to track life event"""
    event_type: str  # "birth", "marriage", "home_purchase", etc.
    category: str  # "family", "property", "employment", etc.
    date_occurred: str  # "YYYY-MM-DD"
    description: str
    affected_person: str = "self"
    metadata: Dict[str, Any] = {}


# ============================================================================
# TAX SAVINGS OPTIMIZER ENDPOINT
# ============================================================================


@router.post("/optimize/tax-savings")
def optimize_tax_savings(request: TaxSavingsRequest):
    """
    Analyze current tax situation and recommend savings strategies.
    
    Returns:
    - List of actionable strategies with impact, effort, and timeline
    - Regime optimization comparison (old vs new)
    - Residency-specific strategies
    - Priority actions ranked by impact/effort ratio
    """
    try:
        optimizer = TaxSavingsOptimizer()
        
        # Convert request to OptimizerInput
        risk_profile = RiskProfile(request.risk_profile)
        current_regime = request.current_regime.lower()
        
        optimizer_input = OptimizerInput(
            total_income=Decimal(str(request.total_income)),
            current_deductions=Decimal(str(request.current_deductions)),
            tax_paid=Decimal(str(request.tax_paid)),
            residency_status=request.residency_status,
            current_regime=current_regime,
            age=request.age,
            has_home_loan=request.has_home_loan,
            has_dependents=request.has_dependents,
            num_dependents=request.num_dependents,
            investment_capacity=Decimal(str(request.investment_capacity)),
            existing_insurance=request.existing_insurance,
            life_events=request.life_events,
            filing_deadline_days_remaining=request.filing_deadline_days_remaining,
            risk_profile=risk_profile
        )
        
        # Run analysis
        output = optimizer.analyze_situation(optimizer_input)
        
        # Convert to JSON-serializable format
        return {
            "ok": True,
            "analysis": {
                "strategies": [
                    {
                        "id": s.id,
                        "category": s.category.value,
                        "title": s.title,
                        "description": s.description,
                        "estimated_saving": float(s.estimated_saving),
                        "confidence": s.confidence,
                        "timeline": s.timeline,
                        "effort": s.effort,
                        "documentation": s.documentation,
                        "section_references": s.section_references,
                    }
                    for s in output.strategies
                ],
                "implementation_timeline": {
                    k: [
                        {
                            "id": s.id,
                            "title": s.title,
                            "estimated_saving": float(s.estimated_saving)
                        }
                        for s in v
                    ]
                    for k, v in output.implementation_timeline.items()
                },
                "total_potential_saving": float(output.total_potential_saving),
                "priority_actions": output.priority_actions,
                "overall_confidence": output.overall_confidence,
                "regime_recommendation": output.regime_recommendation
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# COMPLIANCE VALIDATOR ENDPOINT
# ============================================================================


@router.post("/validate/compliance")
def validate_compliance(request: ComplianceCheckRequest):
    """
    Validate tax return against Income Tax Act compliance rules.
    
    Returns:
    - Compliance score (0-100)
    - Blocking issues (prevent filing)
    - Warnings and info items
    - Auto-fix suggestions
    - Documentation gaps
    """
    try:
        validator = ComplianceValidator()
        
        compliance_input = ComplianceCheckInput(
            total_income=Decimal(str(request.total_income)),
            residency_status=request.residency_status,
            deductions={k: Decimal(str(v)) for k, v in request.deductions.items()},
            tds_claimed=Decimal(str(request.tds_claimed)),
            has_income_from_multiple_sources=request.has_income_from_multiple_sources,
            documents_uploaded=request.documents_uploaded,
            ais_received=request.ais_received,
            form_26as_received=request.form_26as_received,
            assessment_year=request.assessment_year
        )
        
        # Run validation
        output = validator.validate(compliance_input)
        
        return {
            "ok": True,
            "compliance": {
                "compliance_score": output.compliance_score,
                "is_compliant": output.is_compliant,
                "violations": [
                    {
                        "id": v.id,
                        "rule": v.rule.value,
                        "severity": v.severity.value,
                        "section": v.section_reference,
                        "message": v.message,
                        "details": v.details,
                        "suggested_correction": v.suggested_correction,
                        "can_auto_fix": v.can_auto_fix,
                        "documentation_type": v.documentation_type
                    }
                    for v in output.violations
                ],
                "critical_issues": output.critical_issues,
                "blocking_issues": output.blocking_issues,
                "auto_fix_suggestions": output.auto_fix_suggestions,
                "documentation_gaps": output.documentation_gaps,
                "error_count": output.error_count,
                "warning_count": output.warning_count,
                "info_count": output.info_count,
                "estimated_resolution_time_hours": output.estimated_resolution_time_hours
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# RECONCILIATION EXPERT ENDPOINT
# ============================================================================


@router.post("/reconcile/three-way")
def reconcile_three_way(request: ReconciliationRequest):
    """
    Three-way reconciliation: Source Statement ↔ AIS/26AS ↔ ITR.
    
    Detects:
    - Exact matches (all three sources aligned)
    - Fuzzy matches (±₹50-100 tolerance, ±30 days timing)
    - Unmatched entries with risk classification
    - Discrepancies: timing, rounding, duplicates, missing entries
    
    Returns:
    - Match details with variance analysis
    - Risk rating (GREEN/YELLOW/ORANGE/RED)
    - Recommendations for missing entries
    - Reconciliation readiness assessment
    """
    try:
        reconciler = ReconciliationExpert()
        
        # Convert requests to domain objects
        source_statements = [
            SourceStatement(
                id=s.id,
                date=datetime.strptime(s.date, "%Y-%m-%d").date(),
                amount=Decimal(str(s.amount)),
                description=s.description,
                source_type=s.source_type,
                document_ref=s.document_ref
            )
            for s in request.source_statements
        ]
        
        ais_entries = [
            AISEntry(
                id=a.id,
                date=datetime.strptime(a.date, "%Y-%m-%d").date(),
                amount=Decimal(str(a.amount)),
                category=a.category,
                payer_name=a.payer_name,
                payer_pan=a.payer_pan,
                deductee_code=a.deductee_code,
                form_26as_section=a.form_26as_section
            )
            for a in request.ais_entries
        ]
        
        itr_entries = [
            ITREntry(
                id=i.id,
                date=datetime.strptime(i.date, "%Y-%m-%d").date(),
                amount=Decimal(str(i.amount)),
                category=i.category,
                description=i.description,
                form_line_item=i.form_line_item
            )
            for i in request.itr_entries
        ]
        
        # Run reconciliation
        summary = reconciler.reconcile(source_statements, ais_entries, itr_entries)
        
        return {
            "ok": True,
            "reconciliation": {
                "total_source": len(source_statements),
                "total_ais": len(ais_entries),
                "total_itr": len(itr_entries),
                "total_matched": summary.total_matched,
                "total_partially_matched": summary.total_partially_matched,
                "total_unmatched_source": summary.total_unmatched_source,
                "total_unmatched_ais": summary.total_unmatched_ais,
                "total_unmatched_itr": summary.total_unmatched_itr,
                "risk_rating": summary.risk_rating.value,
                "filing_readiness": summary.filing_readiness,
                "matches": [
                    {
                        "source_id": m.source_id,
                        "ais_id": m.ais_id,
                        "itr_id": m.itr_id,
                        "match_status": m.match_status.value,
                        "amount_variance": float(m.amount_variance),
                        "variance_percent": m.variance_percent,
                        "date_variance_days": m.date_variance_days,
                        "risk_level": m.risk_level.value,
                        "explanation": m.explanation
                    }
                    for m in summary.matches
                ],
                "recommendations": summary.recommendations,
                "high_risk_matches": summary.high_risk_matches
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# LIFECYCLE TRACKER ENDPOINT
# ============================================================================


@router.post("/track/lifecycle-event")
def track_lifecycle_event(request: LifeEventRequest):
    """
    Track life events and analyze tax/residency implications.
    
    Supported events:
    - Family: birth, marriage, death, adoption
    - Property: home_purchase, home_sale, rental_income_start
    - Residency: moved_to_india, left_india, visa_change
    - Employment: job_change, business_startup, retirement
    - Financial: inheritance, investment_windfall, loan_taken
    
    Returns:
    - Residency impact analysis
    - Deduction eligibility changes
    - Income recognition timing
    - Dependent count changes
    - Filing requirement changes
    - Documentation requirements
    - Action items and alerts
    - Tax planning opportunities
    """
    try:
        tracker = LifecycleTracker()
        
        # Convert request to domain object
        life_event = LifeEvent(
            id=datetime.now().isoformat(),
            event_type=LifeEventType(request.event_type),
            category=LifeEventCategory(request.category),
            date_occurred=datetime.strptime(request.date_occurred, "%Y-%m-%d").date(),
            description=request.description,
            affected_person=request.affected_person,
            metadata=request.metadata
        )
        
        # Track event
        analysis = tracker.track_event(life_event)
        
        return {
            "ok": True,
            "lifecycle_impact": {
                "event_id": analysis.event_id,
                "event_type": analysis.event_type.value,
                "residency_impact": analysis.residency_impact.value,
                "deduction_changes": analysis.deduction_changes,
                "income_recognition_changes": analysis.income_recognition_changes,
                "dependent_count_change": analysis.dependent_count_change,
                "filing_requirement_change": analysis.filing_requirement_change,
                "filing_deadline_change": analysis.filing_deadline_change,
                "documentation_required": analysis.documentation_required,
                "actions_needed": analysis.actions_needed,
                "compliance_alerts": analysis.compliance_alerts,
                "planning_opportunities": analysis.planning_opportunities,
                "high_priority": analysis.high_priority
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# BATCH ENDPOINTS
# ============================================================================


class BatchOptimizeRequest(BaseModel):
    """Optimize for multiple family members"""
    taxpayers: List[TaxSavingsRequest]


@router.post("/optimize/batch")
def batch_optimize(request: BatchOptimizeRequest):
    """
    Run tax optimization for multiple family members simultaneously.
    
    Used for household analysis before consolidated filing.
    """
    try:
        results = []
        for taxpayer_req in request.taxpayers:
            try:
                result = optimize_tax_savings(taxpayer_req)
                results.append({"ok": True, "data": result})
            except Exception as e:
                results.append({"ok": False, "error": str(e)})
        
        return {
            "ok": True,
            "total": len(request.taxpayers),
            "successful": sum(1 for r in results if r["ok"]),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# MASTER ORCHESTRATOR INTEGRATION
# ============================================================================


class ConversationRequest(BaseModel):
    """AI conversation routing request"""
    user_message: str
    case_id: Optional[str] = None
    session_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


@router.post("/chat/orchestrator")
def ai_chat_orchestrator(request: ConversationRequest):
    """
    Route user message to appropriate Phase 3 specialist via AI Master Orchestrator.
    
    The orchestrator analyzes intent and routes to:
    - Tax Savings Optimizer (tax strategy, optimization, savings)
    - Compliance Validator (compliance, validation, issues)
    - Reconciliation Expert (matching, reconciliation, discrepancies)
    - Lifecycle Tracker (life events, changes, planning)
    
    Returns specialist response with confidence and reasoning.
    """
    from .ai_orchestrator import AIMasterOrchestrator
    
    try:
        if not hasattr(ai_chat_orchestrator, "_orchestrator"):
            ai_chat_orchestrator._orchestrator = AIMasterOrchestrator()  # type: ignore[attr-defined]
        orchestrator = ai_chat_orchestrator._orchestrator  # type: ignore[attr-defined]

        session_id = request.session_id
        if not session_id or session_id not in orchestrator.sessions:
            session = orchestrator.start_session(
                household_id=str(request.case_id or "household"),
                member_ids=[str(request.case_id or "1")],
                assessment_year=2026,
            )
            session_id = session.session_id

        turn = orchestrator.process_user_message(
            session_id=session_id,
            user_message=request.user_message,
        )

        return {
            "ok": True,
            "session_id": session_id,
            "response": {
                "text": turn.assistant_response,
                "specialist": turn.specialist_routed_to.value,
                "confidence": turn.confidence_score,
                "follow_up_questions": turn.follow_up_questions,
                "reasoning": "Routed by intent classifier to specialist assistant.",
            },
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
