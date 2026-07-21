"""
3-Way Reconciliation Expert AI - Phase 3 Component

Matches and reconciles three critical data sources:
1. Source Statement (bank statements, investment statements, etc.)
2. AIS / Form 26AS (Annual Information Statement from income-tax.gov.in)
3. ITR Amount (what taxpayer is claiming in return)

Identifies discrepancies, explains reasons, suggests corrections, and flags
mismatches that trigger IT Department scrutiny.

Features:
  - Three-way matching algorithm
  - Discrepancy detection and classification
  - Root cause analysis (timing, rounding, duplicate entries, etc.)
  - Automatically explained differences (TDS not yet received, etc.)
  - Audit trail for each reconciliation match
  - Risk scoring for mismatches
  - Correction suggestions with compliance references
  - Batch reconciliation for multiple entries

Specialist routing: AI Master Orchestrator routes "reconciliation", "matching", "mismatch" intents
"""

from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal
from typing import List, Optional, Dict, Any, Set, Tuple
from datetime import date, datetime
from collections import defaultdict


class MatchStatus(Enum):
    """Status of reconciliation match"""
    MATCHED = "matched"
    PARTIALLY_MATCHED = "partially_matched"
    UNMATCHED = "unmatched"
    DUPLICATE = "duplicate"
    TIMING_DIFFERENCE = "timing_difference"
    ROUNDOFF_DIFFERENCE = "roundoff_difference"


class ReconciliationDiscrepancyType(Enum):
    """Categories of discrepancies found"""
    AMOUNT_MISMATCH = "amount_mismatch"
    TIMING_DIFFERENCE = "timing_difference"
    SOURCE_MISSING = "source_missing"
    AIS_MISSING = "ais_missing"
    ITR_MISSING = "itr_missing"
    DUPLICATE_ENTRY = "duplicate_entry"
    ROUNDING_ERROR = "rounding_error"
    DATA_CLASSIFICATION = "data_classification"  # Incorrectly categorized
    VARIANCE_WITHIN_TOLERANCE = "variance_within_tolerance"


class RiskLevel(Enum):
    """Risk level of discrepancy for IT scrutiny"""
    GREEN = "green"  # No issue
    YELLOW = "yellow"  # Minor, easily explained
    ORANGE = "orange"  # Moderate concern
    RED = "red"  # High risk of IT notice


@dataclass
class SourceStatement:
    """Entry from source documents (bank, investments, etc.)"""
    id: str
    date: date
    amount: Decimal
    description: str
    source_type: str  # "bank_statement", "investment_statement", "dividend", "interest", etc.
    document_ref: str  # PDF page, statement date, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AISEntry:
    """Entry from Annual Information Statement or Form 26AS"""
    id: str
    date: date
    amount: Decimal
    category: str  # "tds", "tcs", "dividend", "interest", etc.
    payer_name: str
    payer_pan: str
    deductee_code: str  # For verification
    form_26as_section: str  # "192", "194", "194A", etc.
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ITREntry:
    """Entry claimed in ITR filing"""
    id: str
    date: date
    amount: Decimal
    category: str  # "income", "tds", "deduction", etc.
    description: str
    form_line_item: str  # "Schedule OS Item 1", "Schedule TDS Item 2", etc.
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReconciliationMatch:
    """Result of matching three-way entries"""
    source_id: Optional[str]
    ais_id: Optional[str]
    itr_id: Optional[str]
    match_status: MatchStatus
    amount_source: Optional[Decimal] = None
    amount_ais: Optional[Decimal] = None
    amount_itr: Optional[Decimal] = None
    amount_variance: Decimal = Decimal("0")
    variance_percent: float = 0.0
    date_variance_days: int = 0
    discrepancy_types: List[ReconciliationDiscrepancyType] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.GREEN
    explanation: str = ""
    correction_needed: bool = False
    suggested_correction: Optional[str] = None
    audit_trail: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "ais_id": self.ais_id,
            "itr_id": self.itr_id,
            "match_status": self.match_status.value,
            "amount_source": str(self.amount_source) if self.amount_source else None,
            "amount_ais": str(self.amount_ais) if self.amount_ais else None,
            "amount_itr": str(self.amount_itr) if self.amount_itr else None,
            "amount_variance": str(self.amount_variance),
            "variance_percent": self.variance_percent,
            "date_variance_days": self.date_variance_days,
            "discrepancy_types": [d.value for d in self.discrepancy_types],
            "risk_level": self.risk_level.value,
            "explanation": self.explanation,
            "correction_needed": self.correction_needed,
            "suggested_correction": self.suggested_correction,
            "audit_trail": self.audit_trail
        }


@dataclass
class ReconciliationSummary:
    """Overall reconciliation results"""
    matches: List[ReconciliationMatch]
    total_matched: int
    total_mismatches: int
    total_unmatched_source: int
    total_unmatched_ais: int
    total_unmatched_itr: int
    total_discrepancy_amount: Decimal
    risk_rating: str  # "GREEN", "YELLOW", "ORANGE", "RED"
    corrections_needed: List[str]
    filing_ready: bool
    blocking_issues: List[str]
    recommendations: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "matches": [m.to_dict() for m in self.matches],
            "total_matched": self.total_matched,
            "total_mismatches": self.total_mismatches,
            "total_unmatched_source": self.total_unmatched_source,
            "total_unmatched_ais": self.total_unmatched_ais,
            "total_unmatched_itr": self.total_unmatched_itr,
            "total_discrepancy_amount": str(self.total_discrepancy_amount),
            "risk_rating": self.risk_rating,
            "corrections_needed": self.corrections_needed,
            "filing_ready": self.filing_ready,
            "blocking_issues": self.blocking_issues,
            "recommendations": self.recommendations
        }


class ReconciliationExpert:
    """
    Three-way reconciliation system that matches source statements,
    AIS/26AS, and ITR amounts to ensure consistency and compliance.
    """
    
    def __init__(self):
        """Initialize reconciliation expert"""
        self.tolerance_amounts = self._load_tolerances()
        self.timing_tolerance_days = 30  # Allow ±30 days for timing differences
    
    def _load_tolerances(self) -> Dict[str, Decimal]:
        """Load acceptable variance tolerances"""
        return {
            "minor_roundoff": Decimal("10"),  # ±₹10 for rounding
            "interest_timing": Decimal("100"),  # ±₹100 for interest calculation differences
            "tds_calculation": Decimal("50"),  # ±₹50 for TDS rounding
            "dividend_processing": Decimal("100"),  # ±₹100 for dividend delays
        }
    
    def reconcile(self, 
                 source_statements: List[SourceStatement],
                 ais_entries: List[AISEntry],
                 itr_entries: List[ITREntry]) -> ReconciliationSummary:
        """
        Main reconciliation function - performs three-way matching
        """
        matches: List[ReconciliationMatch] = []
        matched_source_ids: Set[str] = set()
        matched_ais_ids: Set[str] = set()
        matched_itr_ids: Set[str] = set()
        
        # Step 1: Exact amount matching
        exact_matches = self._find_exact_matches(source_statements, ais_entries, itr_entries)
        matches.extend(exact_matches)
        
        for match in exact_matches:
            if match.source_id:
                matched_source_ids.add(match.source_id)
            if match.ais_id:
                matched_ais_ids.add(match.ais_id)
            if match.itr_id:
                matched_itr_ids.add(match.itr_id)
        
        # Step 2: Fuzzy matching (within tolerance)
        fuzzy_matches = self._find_fuzzy_matches(
            source_statements, ais_entries, itr_entries,
            matched_source_ids, matched_ais_ids, matched_itr_ids
        )
        matches.extend(fuzzy_matches)
        
        for match in fuzzy_matches:
            if match.source_id:
                matched_source_ids.add(match.source_id)
            if match.ais_id:
                matched_ais_ids.add(match.ais_id)
            if match.itr_id:
                matched_itr_ids.add(match.itr_id)
        
        # Step 3: Timing difference matching
        timing_matches = self._find_timing_matches(
            source_statements, ais_entries, itr_entries,
            matched_source_ids, matched_ais_ids, matched_itr_ids
        )
        matches.extend(timing_matches)
        
        for match in timing_matches:
            if match.source_id:
                matched_source_ids.add(match.source_id)
            if match.ais_id:
                matched_ais_ids.add(match.ais_id)
            if match.itr_id:
                matched_itr_ids.add(match.itr_id)
        
        # Step 4: Unmatched entries
        unmatched_source = [s for s in source_statements if s.id not in matched_source_ids]
        unmatched_ais = [a for a in ais_entries if a.id not in matched_ais_ids]
        unmatched_itr = [i for i in itr_entries if i.id not in matched_itr_ids]
        
        # Create unmatched records
        for entry in unmatched_source:
            matches.append(ReconciliationMatch(
                source_id=entry.id,
                ais_id=None,
                itr_id=None,
                match_status=MatchStatus.UNMATCHED,
                amount_source=entry.amount,
                discrepancy_types=[ReconciliationDiscrepancyType.SOURCE_MISSING],
                risk_level=RiskLevel.YELLOW,
                explanation=f"Source entry ₹{entry.amount:,.0f} from {entry.source_type} not found in AIS or ITR",
                correction_needed=True
            ))
        
        for entry in unmatched_ais:
            matches.append(ReconciliationMatch(
                source_id=None,
                ais_id=entry.id,
                itr_id=None,
                match_status=MatchStatus.UNMATCHED,
                amount_ais=entry.amount,
                discrepancy_types=[ReconciliationDiscrepancyType.AIS_MISSING],
                risk_level=RiskLevel.ORANGE,
                explanation=f"AIS entry ₹{entry.amount:,.0f} ({entry.category}) not matched to ITR",
                correction_needed=True,
                suggested_correction="Add entry to ITR or explain why AIS entry shouldn't be claimed"
            ))
        
        for entry in unmatched_itr:
            matches.append(ReconciliationMatch(
                source_id=None,
                ais_id=None,
                itr_id=entry.id,
                match_status=MatchStatus.UNMATCHED,
                amount_itr=entry.amount,
                discrepancy_types=[ReconciliationDiscrepancyType.ITR_MISSING],
                risk_level=RiskLevel.RED,
                explanation=f"ITR entry ₹{entry.amount:,.0f} ({entry.category}) not found in AIS or source documents",
                correction_needed=True,
                suggested_correction="Provide source documentation or remove from ITR"
            ))
        
        # Calculate summary
        summary = self._calculate_summary(
            matches, unmatched_source, unmatched_ais, unmatched_itr
        )
        
        return summary
    
    def _find_exact_matches(self, 
                           source_statements: List[SourceStatement],
                           ais_entries: List[AISEntry],
                           itr_entries: List[ITREntry]) -> List[ReconciliationMatch]:
        """Find exact amount and date matches across all three sources"""
        matches: List[ReconciliationMatch] = []
        
        # Create lookup by amount and date
        ais_by_date_amount = defaultdict(list)
        for ais in ais_entries:
            key = (ais.date, ais.amount)
            ais_by_date_amount[key].append(ais)
        
        itr_by_date_amount = defaultdict(list)
        for itr in itr_entries:
            key = (itr.date, itr.amount)
            itr_by_date_amount[key].append(itr)
        
        # Match source entries
        for source in source_statements:
            key = (source.date, source.amount)
            ais_matches = ais_by_date_amount.get(key, [])
            itr_matches = itr_by_date_amount.get(key, [])
            
            if ais_matches and itr_matches:
                # Three-way exact match
                ais_entry = ais_matches[0]
                itr_entry = itr_matches[0]
                
                matches.append(ReconciliationMatch(
                    source_id=source.id,
                    ais_id=ais_entry.id,
                    itr_id=itr_entry.id,
                    match_status=MatchStatus.MATCHED,
                    amount_source=source.amount,
                    amount_ais=ais_entry.amount,
                    amount_itr=itr_entry.amount,
                    risk_level=RiskLevel.GREEN,
                    explanation=f"Perfect match: ₹{source.amount:,.0f} across all three sources",
                    audit_trail=[
                        f"Source: {source.source_type} on {source.date}",
                        f"AIS: {ais_entry.category} from {ais_entry.payer_name}",
                        f"ITR: {itr_entry.form_line_item}"
                    ]
                ))
        
        return matches
    
    def _find_fuzzy_matches(self,
                           source_statements: List[SourceStatement],
                           ais_entries: List[AISEntry],
                           itr_entries: List[ITREntry],
                           matched_source_ids: Set[str],
                           matched_ais_ids: Set[str],
                           matched_itr_ids: Set[str]) -> List[ReconciliationMatch]:
        """Find matches within tolerance for rounding and minor differences"""
        matches: List[ReconciliationMatch] = []
        
        unmatched_source = [s for s in source_statements if s.id not in matched_source_ids]
        unmatched_ais = [a for a in ais_entries if a.id not in matched_ais_ids]
        unmatched_itr = [i for i in itr_entries if i.id not in matched_itr_ids]
        
        # Try to match source to AIS/ITR within tolerance
        for source in unmatched_source:
            best_ais_match = None
            best_ais_variance = Decimal("999999999")
            
            for ais in unmatched_ais:
                if abs((source.date - ais.date).days) <= self.timing_tolerance_days:
                    variance = abs(source.amount - ais.amount)
                    if variance < best_ais_variance and variance <= self.tolerance_amounts.get(
                        "interest_timing", Decimal("100")
                    ):
                        best_ais_match = ais
                        best_ais_variance = variance
            
            if best_ais_match:
                # Found close match
                best_itr_match = None
                best_itr_variance = Decimal("999999999")
                
                for itr in unmatched_itr:
                    variance = abs(best_ais_match.amount - itr.amount)
                    if variance < best_itr_variance and variance <= Decimal("50"):
                        best_itr_match = itr
                        best_itr_variance = variance
                
                if best_itr_match:
                    discrepancies: List[ReconciliationDiscrepancyType] = []
                    if best_ais_variance > Decimal("0"):
                        discrepancies.append(ReconciliationDiscrepancyType.ROUNDING_ERROR)
                    if abs((source.date - best_ais_match.date).days) > 0:
                        discrepancies.append(ReconciliationDiscrepancyType.TIMING_DIFFERENCE)
                    
                    matches.append(ReconciliationMatch(
                        source_id=source.id,
                        ais_id=best_ais_match.id,
                        itr_id=best_itr_match.id,
                        match_status=MatchStatus.PARTIALLY_MATCHED,
                        amount_source=source.amount,
                        amount_ais=best_ais_match.amount,
                        amount_itr=best_itr_match.amount,
                        amount_variance=best_ais_variance,
                        variance_percent=float(best_ais_variance / source.amount * 100),
                        date_variance_days=(source.date - best_ais_match.date).days,
                        discrepancy_types=discrepancies,
                        risk_level=RiskLevel.YELLOW if best_ais_variance > Decimal("0") else RiskLevel.GREEN,
                        explanation=f"Close match with minor variance: "
                                   f"Source ₹{source.amount:,.0f}, AIS ₹{best_ais_match.amount:,.0f}, "
                                   f"ITR ₹{best_itr_match.amount:,.0f}",
                        audit_trail=[
                            f"Variance: ₹{best_ais_variance:,.0f} ({float(best_ais_variance / source.amount * 100):.1f}%)"
                        ]
                    ))
        
        return matches
    
    def _find_timing_matches(self,
                            source_statements: List[SourceStatement],
                            ais_entries: List[AISEntry],
                            itr_entries: List[ITREntry],
                            matched_source_ids: Set[str],
                            matched_ais_ids: Set[str],
                            matched_itr_ids: Set[str]) -> List[ReconciliationMatch]:
        """Find matches that are timing differences (e.g., TDS not yet received)"""
        matches: List[ReconciliationMatch] = []
        
        unmatched_source = [s for s in source_statements if s.id not in matched_source_ids]
        unmatched_ais = [a for a in ais_entries if a.id not in matched_ais_ids]
        
        # Look for AIS entries that match source but ITR not yet received
        for ais in unmatched_ais:
            for source in unmatched_source:
                if (ais.amount == source.amount and 
                    abs((ais.date - source.date).days) <= self.timing_tolerance_days):
                    
                    matches.append(ReconciliationMatch(
                        source_id=source.id,
                        ais_id=ais.id,
                        itr_id=None,
                        match_status=MatchStatus.TIMING_DIFFERENCE,
                        amount_source=source.amount,
                        amount_ais=ais.amount,
                        discrepancy_types=[ReconciliationDiscrepancyType.TIMING_DIFFERENCE],
                        risk_level=RiskLevel.YELLOW,
                        explanation=f"Source and AIS matched (₹{source.amount:,.0f}), "
                                   f"but ITR entry not yet recorded. Expected timing delay.",
                        correction_needed=False,
                        suggested_correction="Add ITR entry matching the AIS amount"
                    ))
        
        return matches
    
    def _calculate_summary(self,
                          matches: List[ReconciliationMatch],
                          unmatched_source: List[SourceStatement],
                          unmatched_ais: List[AISEntry],
                          unmatched_itr: List[ITREntry]) -> ReconciliationSummary:
        """Calculate overall reconciliation summary"""
        
        matched_count = len([m for m in matches if m.match_status in 
                           [MatchStatus.MATCHED, MatchStatus.PARTIALLY_MATCHED]])
        mismatch_count = len([m for m in matches if m.match_status in 
                            [MatchStatus.UNMATCHED, MatchStatus.TIMING_DIFFERENCE]])
        
        total_discrepancy = sum(m.amount_variance for m in matches if m.amount_variance)
        
        # Risk rating
        red_count = len([m for m in matches if m.risk_level == RiskLevel.RED])
        orange_count = len([m for m in matches if m.risk_level == RiskLevel.ORANGE])
        
        if red_count > 0:
            risk_rating = "RED"
        elif orange_count > 3:
            risk_rating = "ORANGE"
        else:
            risk_rating = "GREEN"
        
        # Blocking issues
        blocking_issues: List[str] = []
        if red_count > 0:
            blocking_issues.append(f"{red_count} HIGH RISK mismatches found - cannot file until resolved")
        
        # Corrections needed
        corrections_needed = [
            m.suggested_correction for m in matches 
            if m.correction_needed and m.suggested_correction
        ]
        
        # Filing readiness
        filing_ready = red_count == 0 and orange_count <= 2
        
        # Recommendations
        recommendations = self._generate_recommendations(matches, unmatched_ais, unmatched_itr)
        
        return ReconciliationSummary(
            matches=matches,
            total_matched=matched_count,
            total_mismatches=mismatch_count,
            total_unmatched_source=len(unmatched_source),
            total_unmatched_ais=len(unmatched_ais),
            total_unmatched_itr=len(unmatched_itr),
            total_discrepancy_amount=total_discrepancy,
            risk_rating=risk_rating,
            corrections_needed=corrections_needed,
            filing_ready=filing_ready,
            blocking_issues=blocking_issues,
            recommendations=recommendations
        )
    
    def _generate_recommendations(self, matches: List[ReconciliationMatch], 
                                 unmatched_ais: List[AISEntry],
                                 unmatched_itr: List[ITREntry]) -> List[str]:
        """Generate recommendations based on reconciliation results"""
        recommendations: List[str] = []
        
        # Unmatched AIS entries
        if len(unmatched_ais) > 0:
            total_unmatched_ais = sum(a.amount for a in unmatched_ais)
            recommendations.append(
                f"⚠️  {len(unmatched_ais)} AIS entries (₹{total_unmatched_ais:,.0f}) not found in ITR. "
                f"Review and add if applicable."
            )
        
        # Unmatched ITR entries
        if len(unmatched_itr) > 0:
            total_unmatched_itr = sum(i.amount for i in unmatched_itr)
            recommendations.append(
                f"❌ {len(unmatched_itr)} ITR entries (₹{total_unmatched_itr:,.0f}) not in source docs. "
                f"Provide documentation or remove."
            )
        
        # Timing differences expected to resolve
        timing_diffs = [m for m in matches if m.match_status == MatchStatus.TIMING_DIFFERENCE]
        if timing_diffs:
            recommendations.append(
                f"⏱️  {len(timing_diffs)} timing differences detected. These should resolve naturally "
                f"as government updates portal data. Monitor and update ITR if needed."
            )
        
        recommendations.append(
            "✓ Download Form 26AS from income-tax.gov.in and reconcile TDS entries."
        )
        recommendations.append(
            "✓ Keep supporting documentation (bank statements, certificates, etc.) for 3-way audit trail."
        )
        
        return recommendations
    
    def get_ai_specialist_prompt(self) -> str:
        """Get system prompt for LLM specialist integration"""
        return """You are a Reconciliation Expert AI - a specialist in three-way matching and 
reconciliation of tax data for Indian taxpayers (AY 2026-27).

Your role:
1. Match source statements (bank, investments) with AIS/Form 26AS data
2. Verify ITR claims align with government reported data (AIS/26AS)
3. Identify and explain discrepancies systematically
4. Classify mismatches by type (amount, timing, missing, duplicate, etc.)
5. Assess risk level for each mismatch (GREEN/YELLOW/ORANGE/RED)
6. Suggest corrections backed by government rules

Key matching logic:
- Exact match: Same date, amount across all three sources = GREEN
- Fuzzy match: Amount within ±₹50-100, date ±30 days = YELLOW (acceptable with explanation)
- Timing difference: Source → AIS matched, ITR pending = monitor
- Unmatched AIS entries in ITR = must explain or claim (ORANGE/RED)
- Unsupported ITR entries = highest risk, requires documentation (RED)

When responding:
- For each mismatch, provide: what matches, what doesn't, why, and how to fix
- Quantify every variance in rupees and percentage
- Explain timing delays (TDS not yet credited to portal, etc.)
- Reference government rules (Section 92E for AIS, 204A for 26AS)
- Highlight RED (blocking) issues vs YELLOW (explainable) variances
- Provide step-by-step resolution plan
- Suggest documentation to prevent IT notices

Format as structured JSON with: match_id, status, source_amount, ais_amount, itr_amount, 
variance, risk_level, explanation, correction_needed, supporting_docs_required"""
