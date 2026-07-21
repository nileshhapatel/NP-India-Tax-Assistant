"""
Compliance Validator AI - Phase 3 Component

Real-time validation of taxpayer entries against latest Income Tax Act rules,
government circulars, rate limits, and cross-checks with government portals
(AIS, 26AS, TDS rates, etc.).

Features:
  - Rule-based validation against Income Tax Act
  - Limit enforcement (deduction caps, income thresholds)
  - Cross-validation with government data (AIS, 26AS, TDS)
  - Circular and amendment tracking
  - Real-time error/warning alerts
  - Compliance score generation
  - Documentation requirement checks
  - Audit trail for flagged items

Specialist routing: AI Master Orchestrator routes "compliance", "validation", "rule" intents
"""

from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from datetime import date, datetime


class ValidationSeverity(Enum):
    """Severity levels of validation findings"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ComplianceRule(Enum):
    """Categories of compliance rules"""
    DEDUCTION_LIMIT = "deduction_limit"
    INCOME_THRESHOLD = "income_threshold"
    FILING_REQUIREMENT = "filing_requirement"
    DOCUMENTATION = "documentation"
    RESIDENCY_RULE = "residency_rule"
    SECTION_ELIGIBILITY = "section_eligibility"
    RECONCILIATION = "reconciliation"
    GOVERNMENT_PORTAL = "government_portal"
    TDS_VERIFICATION = "tds_verification"


@dataclass
class ComplianceViolation:
    """Single compliance issue found during validation"""
    id: str
    rule: ComplianceRule
    severity: ValidationSeverity
    section_reference: str  # e.g., "80C", "10(1)"
    message: str
    details: str
    affected_field: str
    suggested_correction: Optional[str] = None
    government_reference: Optional[str] = None  # Link to Income Tax dept
    can_auto_fix: bool = False
    requires_documentation: bool = False
    documentation_type: Optional[str] = None
    detection_timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "rule": self.rule.value,
            "severity": self.severity.value,
            "section_reference": self.section_reference,
            "message": self.message,
            "details": self.details,
            "affected_field": self.affected_field,
            "suggested_correction": self.suggested_correction,
            "government_reference": self.government_reference,
            "can_auto_fix": self.can_auto_fix,
            "requires_documentation": self.requires_documentation,
            "documentation_type": self.documentation_type,
            "detection_timestamp": self.detection_timestamp.isoformat()
        }


@dataclass
class ComplianceCheckInput:
    """Input data for compliance validation"""
    total_income: Decimal
    residency_status: str  # "ROR", "RNOR", "NRI"
    deductions: Dict[str, Decimal]  # section -> amount
    tds_claimed: Decimal
    tds_from_ais: Decimal
    tds_from_26as: Decimal
    filing_status: str  # "first_time", "regular", "amended"
    age: int
    has_business_income: bool = False
    business_income: Decimal = Decimal(0)
    capital_gains: Decimal = Decimal(0)
    foreign_income: Decimal = Decimal(0)
    documents_uploaded: List[str] = field(default_factory=list)
    ais_received: bool = False
    form_26as_received: bool = False
    assessment_year: int = 2027
    filing_deadline: date = field(default_factory=lambda: date(2027, 7, 31))


@dataclass
class ComplianceCheckOutput:
    """Output from compliance validation"""
    violations: List[ComplianceViolation]
    compliance_score: float  # 0-100
    is_compliant: bool
    error_count: int
    warning_count: int
    info_count: int
    critical_issues: List[str]
    blocking_issues: List[str]  # Must be fixed before filing
    auto_fix_suggestions: List[Tuple[str, str]]  # (issue_id, suggested_fix)
    documentation_gaps: List[str]
    next_validation_date: Optional[date] = None
    estimated_resolution_time_hours: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "violations": [v.to_dict() for v in self.violations],
            "compliance_score": self.compliance_score,
            "is_compliant": self.is_compliant,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "critical_issues": self.critical_issues,
            "blocking_issues": self.blocking_issues,
            "auto_fix_suggestions": self.auto_fix_suggestions,
            "documentation_gaps": self.documentation_gaps,
            "next_validation_date": self.next_validation_date.isoformat() if self.next_validation_date else None,
            "estimated_resolution_time_hours": self.estimated_resolution_time_hours
        }


class ComplianceValidator:
    """
    Real-time compliance validation system that checks taxpayer data
    against Income Tax Act rules, government circulars, and portal data.
    """
    
    def __init__(self):
        """Initialize validator with current rules and limits"""
        self.deduction_limits = self._load_deduction_limits()
        self.income_thresholds = self._load_income_thresholds()
        self.rules = self._load_compliance_rules()
        self.circular_amendments = self._load_circulars()
    
    def _load_deduction_limits(self) -> Dict[str, Decimal]:
        """Load deduction cap limits (AY 2026-27)"""
        return {
            "80c": Decimal("150000"),
            "80ccc": Decimal("150000"),
            "80ccd_1": Decimal("50000"),
            "80ccd_2": Decimal("0"),  # Employer NPS
            "80d": Decimal("100000"),
            "80d_senior": Decimal("300000"),
            "80dd": Decimal("75000"),
            "80ddb": Decimal("100000"),
            "80e": None,  # No limit - full education loan interest
            "80g": None,  # No fixed limit - percentage of income
            "80gg": Decimal("60000"),
            "80ttt": Decimal("10000"),
            "80u": Decimal("75000"),
        }
    
    def _load_income_thresholds(self) -> Dict[str, Decimal]:
        """Load income threshold limits"""
        return {
            "sec_87a_rebate_limit": Decimal("500000"),  # Old regime only
            "new_regime_min": Decimal("0"),
            "filing_requirement_basic": Decimal("500000"),  # ROR
            "filing_requirement_nri": Decimal("0"),  # Any income
            "filing_requirement_business": Decimal("0"),  # If in business
        }
    
    def _load_compliance_rules(self) -> List[Dict[str, Any]]:
        """Load validation rules"""
        return [
            {
                "id": "rule_deduction_limit",
                "name": "Deduction Limit Exceeded",
                "category": ComplianceRule.DEDUCTION_LIMIT,
            },
            {
                "id": "rule_filing_required",
                "name": "Filing Requirement Check",
                "category": ComplianceRule.FILING_REQUIREMENT,
            },
            {
                "id": "rule_residency_deduction",
                "name": "Residency-Based Deduction Eligibility",
                "category": ComplianceRule.RESIDENCY_RULE,
            },
            {
                "id": "rule_tds_mismatch",
                "name": "TDS Amount Mismatch",
                "category": ComplianceRule.TDS_VERIFICATION,
            },
            {
                "id": "rule_documentation",
                "name": "Missing Documentation",
                "category": ComplianceRule.DOCUMENTATION,
            },
        ]
    
    def _load_circulars(self) -> List[Dict[str, Any]]:
        """Load latest income tax circulars and amendments"""
        return [
            {
                "circular_no": "2024/25-I",
                "date": "2024-04-01",
                "title": "AY 2024-25 New Tax Regime Changes",
                "impact": "Deduction structure modified"
            },
        ]
    
    def validate(self, input_data: ComplianceCheckInput) -> ComplianceCheckOutput:
        """
        Main validation function - checks all aspects of compliance
        """
        violations: List[ComplianceViolation] = []
        blocking_issues: List[str] = []
        
        # Validation 1: Filing Requirement
        filing_check = self._validate_filing_requirement(input_data)
        violations.extend(filing_check["violations"])
        blocking_issues.extend(filing_check["blocking"])
        
        # Validation 2: Deduction Limits
        deduction_check = self._validate_deduction_limits(input_data)
        violations.extend(deduction_check["violations"])
        blocking_issues.extend(deduction_check["blocking"])
        
        # Validation 3: Residency Rules
        residency_check = self._validate_residency_rules(input_data)
        violations.extend(residency_check["violations"])
        blocking_issues.extend(residency_check["blocking"])
        
        # Validation 4: TDS Verification
        tds_check = self._validate_tds(input_data)
        violations.extend(tds_check["violations"])
        blocking_issues.extend(tds_check["blocking"])
        
        # Validation 5: Government Portal Cross-Check
        portal_check = self._validate_government_portals(input_data)
        violations.extend(portal_check["violations"])
        
        # Validation 6: Documentation Requirements
        doc_check = self._validate_documentation(input_data)
        violations.extend(doc_check["violations"])
        blocking_issues.extend(doc_check["blocking"])
        
        # Validation 7: Income Reconciliation
        income_check = self._validate_income_reconciliation(input_data)
        violations.extend(income_check["violations"])
        blocking_issues.extend(income_check["blocking"])
        
        # Calculate compliance score
        error_count = len([v for v in violations if v.severity == ValidationSeverity.ERROR])
        warning_count = len([v for v in violations if v.severity == ValidationSeverity.WARNING])
        info_count = len([v for v in violations if v.severity == ValidationSeverity.INFO])
        critical_count = len([v for v in violations if v.severity == ValidationSeverity.CRITICAL])
        
        compliance_score = self._calculate_compliance_score(
            error_count, warning_count, info_count, critical_count, len(blocking_issues)
        )
        
        is_compliant = compliance_score >= 80.0 and len(blocking_issues) == 0
        
        # Generate auto-fix suggestions
        auto_fix_suggestions = self._generate_auto_fixes(violations)
        
        # Get documentation gaps
        doc_gaps = [v.documentation_type for v in violations 
                   if v.requires_documentation and v.documentation_type]
        
        # Calculate resolution time
        resolution_hours = self._estimate_resolution_time(violations, blocking_issues)
        
        return ComplianceCheckOutput(
            violations=violations,
            compliance_score=compliance_score,
            is_compliant=is_compliant,
            error_count=error_count,
            warning_count=warning_count,
            info_count=info_count,
            critical_issues=[v.message for v in violations if v.severity == ValidationSeverity.CRITICAL],
            blocking_issues=blocking_issues,
            auto_fix_suggestions=auto_fix_suggestions,
            documentation_gaps=doc_gaps,
            estimated_resolution_time_hours=resolution_hours
        )
    
    def _validate_filing_requirement(self, input_data: ComplianceCheckInput) -> Dict[str, Any]:
        """Check if taxpayer must file return"""
        violations: List[ComplianceViolation] = []
        blocking: List[str] = []
        
        filing_req = self.income_thresholds["filing_requirement_basic"]
        
        # NRI must file if ANY income in India
        if input_data.residency_status == "NRI":
            if input_data.total_income > Decimal("0"):
                if input_data.filing_status == "first_time":
                    violations.append(ComplianceViolation(
                        id="filing_req_nri",
                        rule=ComplianceRule.FILING_REQUIREMENT,
                        severity=ValidationSeverity.INFO,
                        section_reference="10(1)",
                        message="NRI with income in India must file return",
                        details="You have income in India and are NRI",
                        affected_field="residency_status",
                        government_reference="https://www.incometax.gov.in"
                    ))
        else:
            # ROR/RNOR filing requirement based on income
            if input_data.total_income > filing_req:
                if input_data.filing_status == "first_time":
                    violations.append(ComplianceViolation(
                        id="filing_req_income",
                        rule=ComplianceRule.FILING_REQUIREMENT,
                        severity=ValidationSeverity.ERROR,
                        section_reference="139(1)",
                        message=f"Income of ₹{input_data.total_income:,.0f} exceeds filing threshold of ₹{filing_req:,.0f}",
                        details="You must file ITR within due date",
                        affected_field="total_income",
                        government_reference="https://www.incometax.gov.in"
                    ))
                    blocking.append(f"Filing requirement: Income ₹{input_data.total_income:,.0f} > ₹{filing_req:,.0f}")
        
        return {"violations": violations, "blocking": blocking}
    
    def _validate_deduction_limits(self, input_data: ComplianceCheckInput) -> Dict[str, Any]:
        """Check deduction amounts against statutory limits"""
        violations: List[ComplianceViolation] = []
        blocking: List[str] = []
        
        for section, amount in input_data.deductions.items():
            limit = self.deduction_limits.get(section.lower())
            
            # Skip sections without fixed limits
            if limit is None:
                continue
            
            if amount > limit:
                violation = ComplianceViolation(
                    id=f"deduction_limit_{section}",
                    rule=ComplianceRule.DEDUCTION_LIMIT,
                    severity=ValidationSeverity.ERROR,
                    section_reference=section.upper(),
                    message=f"Section {section.upper()} deduction ₹{amount:,.0f} exceeds limit ₹{limit:,.0f}",
                    details=f"Allowed limit is ₹{limit:,.0f}. Excess of ₹{amount - limit:,.0f} cannot be claimed.",
                    affected_field=f"deductions.{section}",
                    suggested_correction=f"Reduce claim to ₹{limit:,.0f}",
                    can_auto_fix=True
                )
                violations.append(violation)
                blocking.append(f"Deduction {section} exceeds limit by ₹{amount - limit:,.0f}")
        
        return {"violations": violations, "blocking": blocking}
    
    def _validate_residency_rules(self, input_data: ComplianceCheckInput) -> Dict[str, Any]:
        """Validate residency-specific deduction eligibility"""
        violations: List[ComplianceViolation] = []
        blocking: List[str] = []
        
        # NRIs cannot claim Chapter VIA deductions (80C, 80D, 80G, etc.)
        if input_data.residency_status == "NRI":
            blocked_sections = ["80c", "80ccc", "80ccd_1", "80d", "80dd", "80e", "80g", "80gg", "80u"]
            
            for section in blocked_sections:
                if section in input_data.deductions and input_data.deductions[section] > Decimal("0"):
                    violation = ComplianceViolation(
                        id=f"residency_nri_{section}",
                        rule=ComplianceRule.RESIDENCY_RULE,
                        severity=ValidationSeverity.ERROR,
                        section_reference=section.upper(),
                        message=f"NRI cannot claim Section {section.upper()} deduction",
                        details="Chapter VIA deductions not available for NRIs",
                        affected_field=f"deductions.{section}",
                        suggested_correction="Remove this deduction claim",
                        can_auto_fix=True,
                        government_reference="Income Tax Act, Section 10(1)"
                    )
                    violations.append(violation)
                    blocking.append(f"NRI ineligible for Section {section.upper()} deduction")
        
        # RNOR restrictions
        elif input_data.residency_status == "RNOR":
            # RNOR can only claim section 80G (charitable) fully, others limited
            restricted_sections = ["80c", "80d", "80e"]
            for section in restricted_sections:
                if section in input_data.deductions and input_data.deductions[section] > Decimal("50000"):
                    violations.append(ComplianceViolation(
                        id=f"residency_rnor_{section}",
                        rule=ComplianceRule.RESIDENCY_RULE,
                        severity=ValidationSeverity.WARNING,
                        section_reference=section.upper(),
                        message=f"RNOR Section {section.upper()} deduction may be restricted",
                        details="RNORs have limited eligibility for certain deductions",
                        affected_field=f"deductions.{section}",
                        government_reference="Income Tax Act provisions"
                    ))
        
        return {"violations": violations, "blocking": blocking}
    
    def _validate_tds(self, input_data: ComplianceCheckInput) -> Dict[str, Any]:
        """Validate TDS claimed vs government records (AIS/26AS)"""
        violations: List[ComplianceViolation] = []
        blocking: List[str] = []
        
        # If AIS and 26AS available, cross-check
        tds_mismatch_threshold = Decimal("5000")  # Allow ±₹5k variance
        
        if input_data.ais_received and input_data.form_26as_received:
            # Compare claimed vs Form 26AS
            if abs(input_data.tds_claimed - input_data.tds_from_26as) > tds_mismatch_threshold:
                violation = ComplianceViolation(
                    id="tds_mismatch_26as",
                    rule=ComplianceRule.TDS_VERIFICATION,
                    severity=ValidationSeverity.WARNING,
                    section_reference="192/194",
                    message=f"TDS mismatch: Claimed ₹{input_data.tds_claimed:,.0f} vs Form 26AS ₹{input_data.tds_from_26as:,.0f}",
                    details=f"Difference of ₹{abs(input_data.tds_claimed - input_data.tds_from_26as):,.0f}",
                    affected_field="tds_claimed",
                    suggested_correction=f"Use Form 26AS value ₹{input_data.tds_from_26as:,.0f}",
                    government_reference="Form 26AS from income-tax.gov.in",
                    requires_documentation=True,
                    documentation_type="TDS certificate reconciliation"
                )
                violations.append(violation)
                blocking.append(f"TDS mismatch vs 26AS: ₹{abs(input_data.tds_claimed - input_data.tds_from_26as):,.0f}")
        
        # Check if TDS claimed exceeds income
        if input_data.tds_claimed > input_data.total_income:
            violation = ComplianceViolation(
                id="tds_exceeds_income",
                rule=ComplianceRule.TDS_VERIFICATION,
                severity=ValidationSeverity.ERROR,
                section_reference="192",
                message=f"TDS claimed (₹{input_data.tds_claimed:,.0f}) exceeds total income (₹{input_data.total_income:,.0f})",
                details="TDS cannot exceed the income on which it was deducted",
                affected_field="tds_claimed",
                suggested_correction=f"TDS cannot exceed ₹{input_data.total_income:,.0f}",
                can_auto_fix=True
            )
            violations.append(violation)
            blocking.append(f"TDS ₹{input_data.tds_claimed:,.0f} exceeds income ₹{input_data.total_income:,.0f}")
        
        return {"violations": violations, "blocking": blocking}
    
    def _validate_government_portals(self, input_data: ComplianceCheckInput) -> Dict[str, Any]:
        """Cross-validate data with government portals (AIS, 26AS)"""
        violations: List[ComplianceViolation] = []
        
        # Check if AIS has been received
        if not input_data.ais_received and input_data.total_income > Decimal("0"):
            violations.append(ComplianceViolation(
                id="ais_not_received",
                rule=ComplianceRule.GOVERNMENT_PORTAL,
                severity=ValidationSeverity.WARNING,
                section_reference="92E",
                message="Annual Information Statement (AIS) not received",
                details="AIS from income-tax.gov.in should be reviewed before filing",
                affected_field="documents_uploaded",
                requires_documentation=True,
                documentation_type="AIS from portal"
            ))
        
        # Check if Form 26AS has been received
        if not input_data.form_26as_received and input_data.tds_claimed > Decimal("0"):
            violations.append(ComplianceViolation(
                id="26as_not_received",
                rule=ComplianceRule.GOVERNMENT_PORTAL,
                severity=ValidationSeverity.WARNING,
                section_reference="204A",
                message="Form 26AS (TDS Statement) not received",
                details="Form 26AS should be verified from income-tax.gov.in",
                affected_field="documents_uploaded",
                requires_documentation=True,
                documentation_type="Form 26AS from portal"
            ))
        
        return {"violations": violations}
    
    def _validate_documentation(self, input_data: ComplianceCheckInput) -> Dict[str, Any]:
        """Check documentation requirements for claimed items"""
        violations: List[ComplianceViolation] = []
        blocking: List[str] = []
        
        required_docs = {
            "80c": "Investment proof (receipts, statements)",
            "80d": "Health insurance policy + premium receipts",
            "80e": "Education loan agreement + interest certificate",
            "80g": "Receipt from eligible charity + PAN of donee",
            "80gg": "Rental agreement + rent receipts",
            "80dd": "Medical disability certificate",
            "80ddb": "Medical treatment bills + doctor certificate",
        }
        
        for section, doc_type in required_docs.items():
            if section in input_data.deductions and input_data.deductions[section] > Decimal("0"):
                # Check if documentation was uploaded
                doc_keyword = section.replace("80", "").lower()
                if doc_keyword not in " ".join(input_data.documents_uploaded).lower():
                    violation = ComplianceViolation(
                        id=f"doc_missing_{section}",
                        rule=ComplianceRule.DOCUMENTATION,
                        severity=ValidationSeverity.WARNING,
                        section_reference=section.upper(),
                        message=f"Documentation missing for Section {section.upper()} deduction claim",
                        details=f"Required: {doc_type}",
                        affected_field="documents_uploaded",
                        requires_documentation=True,
                        documentation_type=doc_type
                    )
                    violations.append(violation)
                    blocking.append(f"Missing {section.upper()} documentation")
        
        return {"violations": violations, "blocking": blocking}
    
    def _validate_income_reconciliation(self, input_data: ComplianceCheckInput) -> Dict[str, Any]:
        """Validate income is reconciled across sources"""
        violations: List[ComplianceViolation] = []
        blocking: List[str] = []
        
        # Business income consistency
        if input_data.has_business_income and input_data.business_income > Decimal("0"):
            if not any("business" in doc.lower() or "profit" in doc.lower() 
                      for doc in input_data.documents_uploaded):
                violations.append(ComplianceViolation(
                    id="business_income_docs",
                    rule=ComplianceRule.RECONCILIATION,
                    severity=ValidationSeverity.WARNING,
                    section_reference="44",
                    message="Business income documentation not found",
                    details="Books of accounts, Profit & Loss statement required",
                    affected_field="business_income",
                    requires_documentation=True,
                    documentation_type="Business books & P&L"
                ))
        
        # Capital gains documentation
        if input_data.capital_gains > Decimal("0"):
            if not any("capital" in doc.lower() or "securities" in doc.lower() 
                      for doc in input_data.documents_uploaded):
                violations.append(ComplianceViolation(
                    id="capital_gains_docs",
                    rule=ComplianceRule.RECONCILIATION,
                    severity=ValidationSeverity.INFO,
                    section_reference="111A/112",
                    message="Capital gains sale documentation recommended",
                    details="Sale documents, cost basis documentation",
                    affected_field="capital_gains",
                    requires_documentation=True,
                    documentation_type="Capital gains documentation"
                ))
        
        return {"violations": violations, "blocking": blocking}
    
    def _calculate_compliance_score(self, errors: int, warnings: int, info: int, 
                                   critical: int, blocking_count: int) -> float:
        """Calculate overall compliance score 0-100"""
        # Base score
        score = 100.0
        
        # Deductions for violations
        score -= critical * 50.0  # Critical: -50 each
        score -= errors * 20.0    # Error: -20 each
        score -= warnings * 5.0   # Warning: -5 each
        score -= blocking_count * 30.0  # Blocking: -30 each
        
        # Floor at 0
        return max(0.0, min(100.0, score))
    
    def _generate_auto_fixes(self, violations: List[ComplianceViolation]) -> List[Tuple[str, str]]:
        """Generate automatic fix suggestions for auto-fixable violations"""
        auto_fixes: List[Tuple[str, str]] = []
        
        for violation in violations:
            if violation.can_auto_fix and violation.suggested_correction:
                auto_fixes.append((violation.id, violation.suggested_correction))
        
        return auto_fixes
    
    def _estimate_resolution_time(self, violations: List[ComplianceViolation], 
                                 blocking_issues: List[str]) -> float:
        """Estimate hours needed to resolve all violations"""
        base_hours = 0.0
        
        # Blocking issues take longer
        base_hours += len(blocking_issues) * 2.0
        
        # Errors take 1 hour each
        base_hours += len([v for v in violations if v.severity == ValidationSeverity.ERROR]) * 1.0
        
        # Warnings take 0.5 hours each
        base_hours += len([v for v in violations if v.severity == ValidationSeverity.WARNING]) * 0.5
        
        return base_hours
    
    def get_ai_specialist_prompt(self) -> str:
        """Get system prompt for LLM specialist integration"""
        return """You are a Compliance Validator AI - an expert in Income Tax compliance and rule enforcement 
for Indian taxpayers (AY 2026-27).

Your role:
1. Validate taxpayer entries against latest Income Tax Act, Rules, and government circulars
2. Check deduction claims against statutory limits
3. Verify residency-based eligibility (NRI/RNOR/ROR differences)
4. Cross-validate with government portals (AIS, Form 26AS, TDS data)
5. Enforce documentation requirements for claimed deductions
6. Alert on blocking issues that must be fixed before filing
7. Provide correction suggestions with references

Key validation areas:
- Deduction limits: 80C (₹1.5L), 80D (₹1L/₹3L senior), 80CCD (₹50K), etc.
- Income thresholds: Filing requirement ₹5L for ROR, any income for NRI
- Residency rules: NRIs blocked from Chapter VIA deductions
- TDS verification: Cross-check against Form 26AS from portal
- Documentation: Required proofs for each deduction claimed
- Reconciliation: Income sources must match portal data (AIS)

When responding:
- Categorize findings: CRITICAL (blocks filing), ERROR (must fix), WARNING (should fix), INFO
- Quantify discrepancies in rupees
- Provide Income Tax Act section references
- Link to government portal data when available
- Suggest corrective actions with deadlines
- Estimate resolution effort (hours needed)
- Track audit trail for compliance

Format as structured JSON with: violation_id, severity, section_reference, 
message, suggested_correction, government_reference, documentation_required"""
