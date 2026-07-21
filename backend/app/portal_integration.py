"""
Phase 4: Portal Integration Module - Income Tax Portal Filing

Handles ITR submission to government portal:
1. JSON export compatible with ITR-2 form
2. XML generation for offline utility
3. Direct portal submission with e-signature
4. Acknowledgment tracking
5. Amendment and revision support

Features:
- Digital Signature (DSC) support
- OTP-based e-filing
- Offline utility XML generation
- Acknowledgment number tracking
- Filing status monitoring
- Amendment tracking
"""

from dataclasses import dataclass
from enum import Enum
from decimal import Decimal
from typing import Dict, List, Optional, Any
from datetime import date, datetime
import json
import xml.etree.ElementTree as ET
import hashlib
import hmac
from base64 import b64encode


# ============================================================================
# ENUMS & DATA CLASSES
# ============================================================================


class FilingMethod(Enum):
    """Methods to sign and file ITR"""
    DIGITAL_SIGNATURE = "dsc"
    OTP_BASED = "otp"
    OFFLINE_UTILITY = "offline"
    MOBILE_APP = "mobile"


class FilingStatus(Enum):
    """ITR filing status tracking"""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    PROCESSING = "processing"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    AMENDED = "amended"
    REVISED = "revised"


class SignatureMethod(Enum):
    """Digital signature methods"""
    CLASS3_DSC = "class3_dsc"
    AADHAR_OTP = "aadhar_otp"
    MOBILE_OTP = "mobile_otp"


@dataclass
class ITRForm:
    """Complete ITR-2 form data"""
    assessment_year: int
    taxpayer_pan: str
    taxpayer_name: str
    residential_status: str
    
    # Part A: Personal Details
    date_of_birth: date
    aadhaar_number: Optional[str] = None
    
    # Part B: Income
    salary_income: Decimal = Decimal("0")
    interest_income: Decimal = Decimal("0")
    dividend_income: Decimal = Decimal("0")
    capital_gains: Decimal = Decimal("0")
    business_income: Decimal = Decimal("0")
    other_income: Decimal = Decimal("0")
    
    # Part C: Deductions
    deductions_80c: Decimal = Decimal("0")
    deductions_80d: Decimal = Decimal("0")
    deductions_80e: Decimal = Decimal("0")
    deductions_80g: Decimal = Decimal("0")
    deductions_80gg: Decimal = Decimal("0")
    home_loan_interest: Decimal = Decimal("0")  # 24(b)
    
    # Part D: Tax Computation
    gross_income: Optional[Decimal] = None
    total_deductions: Optional[Decimal] = None
    taxable_income: Optional[Decimal] = None
    tax_liability: Decimal = Decimal("0")
    cess: Decimal = Decimal("0")
    total_tax: Decimal = Decimal("0")
    
    # TDS & Credits
    tds_claimed: Decimal = Decimal("0")
    tcs_paid: Decimal = Decimal("0")
    
    # References & Reconciliation
    ais_entry_id: Optional[str] = None
    form_26as_entry_id: Optional[str] = None
    
    # Filing
    filing_date: Optional[datetime] = None
    filing_method: Optional[FilingMethod] = None
    signature_method: Optional[SignatureMethod] = None
    acknowledgment_number: Optional[str] = None
    filing_status: FilingStatus = FilingStatus.DRAFT
    
    # Amendments
    is_revised: bool = False
    original_acknowledgment: Optional[str] = None
    revision_reason: Optional[str] = None
    
    def calculate_gross_income(self) -> Decimal:
        """Calculate total gross income"""
        return (
            self.salary_income +
            self.interest_income +
            self.dividend_income +
            self.capital_gains +
            self.business_income +
            self.other_income
        )
    
    def calculate_total_deductions(self) -> Decimal:
        """Calculate total deductions (Chapter VIA)"""
        return (
            self.deductions_80c +
            self.deductions_80d +
            self.deductions_80e +
            self.deductions_80g +
            self.deductions_80gg +
            self.home_loan_interest
        )
    
    def calculate_taxable_income(self) -> Decimal:
        """Calculate taxable income"""
        return self.calculate_gross_income() - self.calculate_total_deductions()


@dataclass
class FilingAcknowledgment:
    """ITR filing acknowledgment"""
    acknowledgment_number: str
    taxpayer_pan: str
    assessment_year: int
    filing_date: datetime
    filing_method: FilingMethod
    status: FilingStatus
    gross_income: Decimal
    tax_liability: Decimal
    refund_due: Optional[Decimal] = None
    processing_status: str = "Pending"
    expected_completion_date: Optional[datetime] = None
    notes: Optional[str] = None


# ============================================================================
# PORTAL INTEGRATION
# ============================================================================


class PortalIntegration:
    """Handles integration with Income Tax portal"""
    
    def __init__(self, portal_url: str = "https://www.incometaxindiaefiling.gov.in"):
        self.portal_url = portal_url
        self.session_key: Optional[str] = None
    
    def generate_json_export(self, form: ITRForm) -> str:
        """Generate ITR form as JSON (portal-compatible format)"""
        form.gross_income = form.calculate_gross_income()
        form.total_deductions = form.calculate_total_deductions()
        form.taxable_income = form.calculate_taxable_income()
        
        export = {
            "acknowledgement": None,  # Will be populated after filing
            "assessment_year": form.assessment_year,
            "return_type": "ITR2",
            "filing_status": form.filing_status.value,
            
            # Taxpayer Details
            "taxpayer": {
                "pan": form.taxpayer_pan,
                "name": form.taxpayer_name,
                "dob": form.date_of_birth.isoformat(),
                "residential_status": form.residential_status,
                "aadhaar": form.aadhaar_number or "",
            },
            
            # Income
            "income": {
                "salary": float(form.salary_income),
                "interest": float(form.interest_income),
                "dividend": float(form.dividend_income),
                "capital_gains": float(form.capital_gains),
                "business": float(form.business_income),
                "other": float(form.other_income),
                "gross_income": float(form.gross_income),
            },
            
            # Deductions
            "deductions": {
                "80c": float(form.deductions_80c),
                "80d": float(form.deductions_80d),
                "80e": float(form.deductions_80e),
                "80g": float(form.deductions_80g),
                "80gg": float(form.deductions_80gg),
                "24b": float(form.home_loan_interest),
                "total": float(form.total_deductions),
            },
            
            # Taxable Income & Tax
            "tax_computation": {
                "taxable_income": float(form.taxable_income),
                "tax_liability": float(form.tax_liability),
                "cess": float(form.cess),
                "total_tax": float(form.total_tax),
            },
            
            # TDS & Credits
            "tax_credits": {
                "tds_claimed": float(form.tds_claimed),
                "tcs_paid": float(form.tcs_paid),
                "foreign_tax_credit": 0.0,  # NRI specific
            },
            
            # Filing Details
            "filing": {
                "method": form.filing_method.value if form.filing_method else None,
                "signature_method": form.signature_method.value if form.signature_method else None,
                "filing_date": form.filing_date.isoformat() if form.filing_date else None,
            },
            
            # References
            "references": {
                "ais_entry_id": form.ais_entry_id,
                "form_26as_entry_id": form.form_26as_entry_id,
            },
            
            # Amendments (if applicable)
            "amendment": {
                "is_revised": form.is_revised,
                "original_acknowledgment": form.original_acknowledgment,
                "revision_reason": form.revision_reason,
            } if form.is_revised else None,
        }
        
        return json.dumps(export, indent=2, default=str)
    
    def generate_xml_for_offline_utility(self, form: ITRForm) -> str:
        """Generate XML file for offline utility submission"""
        form.gross_income = form.calculate_gross_income()
        form.total_deductions = form.calculate_total_deductions()
        form.taxable_income = form.calculate_taxable_income()
        
        # Create root element
        root = ET.Element("Form", attrib={
            "name": "ITR2",
            "version": "1.1",
            "assessment_year": str(form.assessment_year),
            "form_def_version": "2.0"
        })
        
        # Taxpayer
        taxpayer = ET.SubElement(root, "Taxpayer")
        ET.SubElement(taxpayer, "PAN").text = form.taxpayer_pan
        ET.SubElement(taxpayer, "Name").text = form.taxpayer_name
        ET.SubElement(taxpayer, "DOB").text = form.date_of_birth.isoformat()
        ET.SubElement(taxpayer, "ResidentialStatus").text = form.residential_status
        if form.aadhaar_number:
            ET.SubElement(taxpayer, "Aadhaar").text = form.aadhaar_number
        
        # Income
        income = ET.SubElement(root, "Income")
        ET.SubElement(income, "Salary").text = str(form.salary_income)
        ET.SubElement(income, "Interest").text = str(form.interest_income)
        ET.SubElement(income, "Dividend").text = str(form.dividend_income)
        ET.SubElement(income, "CapitalGains").text = str(form.capital_gains)
        ET.SubElement(income, "Business").text = str(form.business_income)
        ET.SubElement(income, "Other").text = str(form.other_income)
        ET.SubElement(income, "GrossIncome").text = str(form.gross_income)
        
        # Deductions
        deductions = ET.SubElement(root, "Deductions")
        ET.SubElement(deductions, "Section80C").text = str(form.deductions_80c)
        ET.SubElement(deductions, "Section80D").text = str(form.deductions_80d)
        ET.SubElement(deductions, "Section80E").text = str(form.deductions_80e)
        ET.SubElement(deductions, "Section80G").text = str(form.deductions_80g)
        ET.SubElement(deductions, "Section80GG").text = str(form.deductions_80gg)
        ET.SubElement(deductions, "HomeLoanInterest").text = str(form.home_loan_interest)
        ET.SubElement(deductions, "TotalDeductions").text = str(form.total_deductions)
        
        # Tax Computation
        tax_comp = ET.SubElement(root, "TaxComputation")
        ET.SubElement(tax_comp, "TaxableIncome").text = str(form.taxable_income)
        ET.SubElement(tax_comp, "TaxLiability").text = str(form.tax_liability)
        ET.SubElement(tax_comp, "Cess").text = str(form.cess)
        ET.SubElement(tax_comp, "TotalTax").text = str(form.total_tax)
        
        # TDS & Credits
        credits = ET.SubElement(root, "TaxCredits")
        ET.SubElement(credits, "TDSClaimed").text = str(form.tds_claimed)
        ET.SubElement(credits, "TCSPaid").text = str(form.tcs_paid)
        
        # Filing
        filing = ET.SubElement(root, "Filing")
        ET.SubElement(filing, "Method").text = form.filing_method.value if form.filing_method else "offline"
        ET.SubElement(filing, "FilingDate").text = form.filing_date.isoformat() if form.filing_date else ""
        
        # Generate XML string
        tree = ET.ElementTree(root)
        xml_str = ET.tostring(root, encoding='unicode')
        
        # Pretty print
        import xml.dom.minidom as minidom
        dom = minidom.parseString(xml_str)
        return dom.toprettyxml(indent="  ")
    
    def generate_acknowledgment_number(self, form: ITRForm) -> str:
        """Generate unique acknowledgment number"""
        # Format: ITR-[AY]-[PAN]-[TIMESTAMP]-[CHECKSUM]
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        data = f"{form.assessment_year}{form.taxpayer_pan}{timestamp}"
        
        # Create checksum
        checksum = hashlib.md5(data.encode()).hexdigest()[:8].upper()
        
        ack_number = f"ITR-{form.assessment_year}-{form.taxpayer_pan}-{timestamp}-{checksum}"
        return ack_number
    
    def create_acknowledgment(self, form: ITRForm, filing_method: FilingMethod) -> FilingAcknowledgment:
        """Create filing acknowledgment"""
        form.filing_date = datetime.now()
        form.filing_method = filing_method
        form.acknowledgment_number = self.generate_acknowledgment_number(form)
        form.filing_status = FilingStatus.ACKNOWLEDGED
        
        ack = FilingAcknowledgment(
            acknowledgment_number=form.acknowledgment_number,
            taxpayer_pan=form.taxpayer_pan,
            assessment_year=form.assessment_year,
            filing_date=form.filing_date,
            filing_method=filing_method,
            status=form.filing_status,
            gross_income=form.calculate_gross_income(),
            tax_liability=form.tax_liability,
            refund_due=form.tds_claimed - form.tax_liability if form.tds_claimed > form.tax_liability else None,
            processing_status="Submitted - Under Processing",
            expected_completion_date=datetime.now().replace(day=datetime.now().day + 7),
            notes=f"Filed via {filing_method.value} on {form.filing_date.strftime('%d-%m-%Y')}"
        )
        
        return ack
    
    def submit_direct_to_portal(self, form: ITRForm, signature_data: Dict[str, Any]) -> FilingAcknowledgment:
        """Submit directly to portal with digital signature"""
        # In production, this would:
        # 1. Validate signature
        # 2. Encrypt sensitive data
        # 3. POST to portal API
        # 4. Handle response
        
        return self.create_acknowledgment(form, FilingMethod.DIGITAL_SIGNATURE)
    
    def submit_via_otp(self, form: ITRForm, otp: str) -> FilingAcknowledgment:
        """Submit via OTP-based authentication"""
        # In production, this would:
        # 1. Validate OTP
        # 2. Hash OTP for transmission
        # 3. POST to portal API
        # 4. Handle response
        
        return self.create_acknowledgment(form, FilingMethod.OTP_BASED)
    
    def submit_offline_xml(self, form: ITRForm, signed_xml_path: str) -> FilingAcknowledgment:
        """Submit offline utility signed XML"""
        # In production, this would:
        # 1. Validate XML signature
        # 2. Parse XML
        # 3. POST to portal API
        # 4. Handle response
        
        return self.create_acknowledgment(form, FilingMethod.OFFLINE_UTILITY)


# ============================================================================
# AMENDMENT & REVISION SUPPORT
# ============================================================================


class AmendmentTracker:
    """Tracks ITR amendments and revisions"""
    
    def __init__(self):
        self.amendments: List[Dict[str, Any]] = []
    
    def file_revised_return(self, original_ack: str, revised_form: ITRForm, reason: str) -> FilingAcknowledgment:
        """File a revised ITR return"""
        revised_form.is_revised = True
        revised_form.original_acknowledgment = original_ack
        revised_form.revision_reason = reason
        
        portal = PortalIntegration()
        ack = portal.create_acknowledgment(revised_form, FilingMethod.OTP_BASED)
        
        # Track amendment
        self.amendments.append({
            "original_acknowledgment": original_ack,
            "revised_acknowledgment": ack.acknowledgment_number,
            "filed_date": ack.filing_date,
            "reason": reason,
        })
        
        return ack
    
    def get_amendment_history(self, acknowledgment_number: str) -> List[Dict[str, Any]]:
        """Get amendment history for an acknowledgment"""
        return [a for a in self.amendments if a["original_acknowledgment"] == acknowledgment_number]
