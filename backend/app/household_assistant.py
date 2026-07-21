"""
Household Assistant - Family Data Management

Manages:
- Family member profiles
- Relationships and dependencies
- Residency status and life events
- Household consolidated dashboard
- Auto-suggestion of filing tasks
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from decimal import Decimal
import uuid


class ResidencyStatus(Enum):
    """Residency status per Income Tax Act"""
    ROR = "ror"  # Resident of India
    NRI = "nri"  # Non-Resident Individual
    RNOR = "rnor"  # Resident but Not Ordinarily Resident


class Relationship(Enum):
    """Family relationships"""
    SELF = "self"
    SPOUSE = "spouse"
    CHILD = "child"
    PARENT = "parent"
    SIBLING = "sibling"
    DEPENDENT = "dependent"
    OTHER = "other"


class LifeEventType(Enum):
    """Types of life events that affect tax filing"""
    BIRTH = "birth"
    DEATH = "death"
    MARRIAGE = "marriage"
    DIVORCE = "divorce"
    ADOPTION = "adoption"
    OCI_OBTAINED = "oci_obtained"
    CITIZENSHIP_CHANGE = "citizenship_change"
    EMPLOYMENT_CHANGE = "employment_change"
    RELOCATION = "relocation"
    HOME_PURCHASE = "home_purchase"
    HOME_SALE = "home_sale"
    BUSINESS_START = "business_start"
    BUSINESS_END = "business_end"
    INVESTMENT = "investment"
    RETIREMENT = "retirement"


@dataclass
class LifeEvent:
    """Record of a significant life event"""
    event_type: LifeEventType
    date: date
    description: str
    impact_on_residency: bool
    impact_on_deductions: bool
    documentation_required: List[str]
    status: str = "pending"  # pending, documented, validated
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "date": self.date.isoformat(),
            "description": self.description,
            "impact_on_residency": self.impact_on_residency,
            "impact_on_deductions": self.impact_on_deductions,
            "documentation_required": self.documentation_required,
            "status": self.status,
        }


@dataclass
class FamilyMember:
    """Individual family member profile"""
    name: str
    pan: str  # Last 4 digits stored for privacy
    date_of_birth: date
    relationship_to_primary: Relationship
    residency_status: ResidencyStatus
    assessment_year: int
    
    # Optional fields
    employment_status: Optional[str] = None
    annual_income: Optional[Decimal] = None
    deductions_claimed: Optional[Decimal] = None
    filing_status: str = "not_started"  # not_started, in_progress, completed, reviewed
    
    # Metadata
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    life_events: List[LifeEvent] = field(default_factory=list)
    documents_uploaded: List[str] = field(default_factory=list)

    def age_at_assessment(self) -> int:
        """Calculate age as on March 31 of assessment year"""
        assessment_date = date(self.assessment_year - 1, 3, 31)
        return (assessment_date - self.date_of_birth).days // 365

    def is_senior_citizen(self) -> bool:
        """Check if 60+ years old during the financial year"""
        return self.age_at_assessment() >= 60

    def requires_filing(self) -> bool:
        """Check if member needs to file ITR"""
        if self.annual_income is None:
            return False
        # Basic: file if income > threshold (varies by age/residency)
        threshold = Decimal(250000)
        if self.is_senior_citizen():
            threshold = Decimal(500000)
        return self.annual_income > threshold

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "pan_last_4": self.pan,
            "date_of_birth": self.date_of_birth.isoformat(),
            "age_at_assessment": self.age_at_assessment(),
            "relationship": self.relationship_to_primary.value,
            "residency_status": self.residency_status.value,
            "employment_status": self.employment_status,
            "annual_income": float(self.annual_income) if self.annual_income else None,
            "filing_required": self.requires_filing(),
            "filing_status": self.filing_status,
            "documents_uploaded": len(self.documents_uploaded),
            "life_events": [event.to_dict() for event in self.life_events],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class HouseholdProfile:
    """Complete household profile with family members"""
    primary_member_id: str
    assessment_year: int
    household_name: Optional[str] = None
    
    # Family members
    members: Dict[str, FamilyMember] = field(default_factory=dict)
    
    # Consolidated info
    total_household_income: Decimal = Decimal(0)
    total_deductions: Decimal = Decimal(0)
    members_requiring_filing: int = 0
    
    # Metadata
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def add_member(self, member: FamilyMember) -> bool:
        """Add family member to household"""
        if member.id in self.members:
            return False
        self.members[member.id] = member
        self._update_consolidated_data()
        return True

    def update_member(self, member_id: str, updates: Dict) -> bool:
        """Update family member information"""
        if member_id not in self.members:
            return False
        
        member = self.members[member_id]
        for key, value in updates.items():
            if hasattr(member, key):
                setattr(member, key, value)
        
        member.updated_at = datetime.now()
        self._update_consolidated_data()
        return True

    def add_life_event(self, member_id: str, event: LifeEvent) -> bool:
        """Add life event for family member"""
        if member_id not in self.members:
            return False
        
        self.members[member_id].life_events.append(event)
        self.members[member_id].updated_at = datetime.now()
        return True

    def _update_consolidated_data(self):
        """Recalculate consolidated household data"""
        self.total_household_income = sum(
            member.annual_income or Decimal(0)
            for member in self.members.values()
        )
        self.total_deductions = sum(
            member.deductions_claimed or Decimal(0)
            for member in self.members.values()
        )
        self.members_requiring_filing = sum(
            1 for member in self.members.values()
            if member.requires_filing()
        )
        self.updated_at = datetime.now()

    def get_filing_checklist(self) -> Dict:
        """Generate filing checklist for household"""
        checklist = {}
        
        for member_id, member in self.members.items():
            if member.requires_filing():
                checklist[member.name] = {
                    "filing_required": True,
                    "current_status": member.filing_status,
                    "income": float(member.annual_income) if member.annual_income else 0,
                    "tasks": self._generate_member_tasks(member),
                }
        
        return checklist

    def _generate_member_tasks(self, member: FamilyMember) -> List[Dict]:
        """Generate filing tasks for individual member"""
        tasks = [
            {"task": "Upload Profile Information", "status": "pending"},
            {"task": "Enter Income Details", "status": "pending"},
            {"task": "Upload Income Proof Documents", "status": "pending"},
        ]
        
        if member.annual_income and member.annual_income > Decimal(0):
            tasks.append({"task": "Upload Form 26AS / AIS", "status": "pending"})
            tasks.append({"task": "Validate TDS Credit", "status": "pending"})
        
        if member.relationship_to_primary == Relationship.SPOUSE:
            tasks.append({"task": "Provide Spouse Consent", "status": "pending"})
        
        if member.life_events:
            tasks.append({"task": "Document Life Events", "status": "pending"})
        
        return tasks

    def get_household_dashboard(self) -> Dict:
        """Generate consolidated household dashboard"""
        return {
            "household": {
                "id": self.id,
                "name": self.household_name or "Primary Household",
                "assessment_year": self.assessment_year,
                "total_members": len(self.members),
            },
            "filing_summary": {
                "members_requiring_filing": self.members_requiring_filing,
                "members_completed": sum(
                    1 for m in self.members.values()
                    if m.filing_status == "completed"
                ),
                "members_in_progress": sum(
                    1 for m in self.members.values()
                    if m.filing_status == "in_progress"
                ),
            },
            "income_summary": {
                "total_household_income": float(self.total_household_income),
                "total_deductions": float(self.total_deductions),
                "net_taxable_income": float(self.total_household_income - self.total_deductions),
            },
            "members": [
                member.to_dict() for member in self.members.values()
            ],
            "filing_checklist": self.get_filing_checklist(),
            "last_updated": self.updated_at.isoformat(),
        }


class HouseholdAssistant:
    """Main household assistant interface"""

    def __init__(self, assessment_year: int = 2026):
        self.assessment_year = assessment_year
        self.households: Dict[str, HouseholdProfile] = {}

    def create_household(
        self,
        primary_member: FamilyMember,
        household_name: Optional[str] = None,
    ) -> HouseholdProfile:
        """Create new household with primary member"""
        household = HouseholdProfile(
            primary_member_id=primary_member.id,
            assessment_year=self.assessment_year,
            household_name=household_name,
        )
        household.add_member(primary_member)
        self.households[household.id] = household
        return household

    def suggest_actions_for_member(self, member: FamilyMember) -> List[str]:
        """Suggest filing actions based on member profile"""
        suggestions = []

        # Life event prompts
        if member.life_events:
            recent_events = [e for e in member.life_events if not e.status == "validated"]
            if recent_events:
                suggestions.append(f"⚠️ {len(recent_events)} undocumented life event(s) - please update")

        # Age-based suggestions
        if member.is_senior_citizen():
            suggestions.append("💡 You are 60+ - consider higher deduction limits for health insurance")

        # Income-based suggestions
        if member.annual_income and member.annual_income > Decimal(500000):
            suggestions.append("📊 Consider tax-saving deductions under Section 80C, 80D, 80E")

        # Residency-based suggestions
        if member.residency_status == ResidencyStatus.NRI:
            suggestions.append("🌍 As NRI - ensure proper foreign income documentation")

        if member.residency_status == ResidencyStatus.RNOR:
            suggestions.append("📝 As RNOR - verify residency timeline is properly documented")

        return suggestions

    def suggest_family_structure(self) -> Dict:
        """Suggest optimal family structure for tax planning"""
        return {
            "spouse_income_splitting": "Consider spouse's income for optimization",
            "dependent_support": "Track dependent expenses for deductions",
            "life_insurance_planning": "Align life insurance with family security needs",
            "retirement_planning": "Set up NPS for all working family members",
        }

    def generate_life_event_prompt(self) -> str:
        """Generate prompt asking about family life events"""
        return """
🏠 HOUSEHOLD ASSISTANT - Family Life Events
=============================================

Have any of the following occurred recently?
- Birth or Adoption
- Marriage or Divorce
- Death or Loss of Income
- Relocation or Citizenship Change
- New Employment or Business Start
- Major Purchase (Home, Business)
- Investment or Retirement

Please update these events to ensure proper tax compliance.
        """.strip()

    def get_filing_timeline_recommendations(self) -> Dict:
        """Get recommended timeline for household filing"""
        return {
            "immediate": [
                "Gather all income documents (salary slips, 1099, etc.)",
                "Collect Form 26AS and AIS from Income Tax portal",
                "Organize bank statements and investment documents",
            ],
            "week_1": [
                "Enter income for all family members",
                "Upload documents to system",
                "Validate income against AIS/26AS",
            ],
            "week_2": [
                "Review and reconcile TDS credits",
                "Complete deduction entries",
                "Get spouse/dependent consents if needed",
            ],
            "week_3": [
                "Generate preliminary tax reports",
                "Review calculations and validate",
                "Make any necessary corrections",
            ],
            "final": [
                "Generate final reports",
                "Sign and verify digitally",
                "Submit through Income Tax portal",
            ]
        }
