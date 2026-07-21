"""
Phase 4: Portal Integration REST Endpoints

Endpoints for ITR filing submission to government portal:
- Export form as JSON/XML
- Submit with digital signature
- Submit via OTP
- Track filing status
- File amendments and revisions
"""

from fastapi import APIRouter, HTTPException, File, UploadFile
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import date, datetime
from decimal import Decimal

from .portal_integration import (
    PortalIntegration,
    ITRForm,
    FilingMethod,
    FilingStatus,
    SignatureMethod,
    FilingAcknowledgment,
    AmendmentTracker
)

router = APIRouter(prefix="/api/phase4", tags=["Phase 4 - Portal Integration"])

# ============================================================================
# REQUEST MODELS
# ============================================================================


class ITRFormRequest(BaseModel):
    """Complete ITR form data"""
    assessment_year: int
    taxpayer_pan: str
    taxpayer_name: str
    residential_status: str
    date_of_birth: str  # "YYYY-MM-DD"
    aadhaar_number: Optional[str] = None
    
    # Income
    salary_income: float = 0
    interest_income: float = 0
    dividend_income: float = 0
    capital_gains: float = 0
    business_income: float = 0
    other_income: float = 0
    
    # Deductions
    deductions_80c: float = 0
    deductions_80d: float = 0
    deductions_80e: float = 0
    deductions_80g: float = 0
    deductions_80gg: float = 0
    home_loan_interest: float = 0
    
    # Tax
    tax_liability: float = 0
    cess: float = 0
    tds_claimed: float = 0
    tcs_paid: float = 0
    
    # References
    ais_entry_id: Optional[str] = None
    form_26as_entry_id: Optional[str] = None


class SubmitWithSignatureRequest(BaseModel):
    """Submit ITR with digital signature"""
    form_data: ITRFormRequest
    signature_method: str  # "dsc", "aadhar_otp", "mobile_otp"
    signature_value: str  # Base64 encoded signature


class SubmitWithOTPRequest(BaseModel):
    """Submit ITR via OTP"""
    form_data: ITRFormRequest
    mobile_number: str
    otp: str


class AmendmentRequest(BaseModel):
    """File amended ITR"""
    original_acknowledgment: str
    revised_form_data: ITRFormRequest
    amendment_reason: str


# ============================================================================
# GLOBAL STATE
# ============================================================================

portal = PortalIntegration()
amendment_tracker = AmendmentTracker()


# ============================================================================
# EXPORT ENDPOINTS
# ============================================================================


@router.post("/export/json")
def export_as_json(form_request: ITRFormRequest):
    """Export ITR form as JSON (portal-compatible)"""
    try:
        form = ITRForm(
            assessment_year=form_request.assessment_year,
            taxpayer_pan=form_request.taxpayer_pan,
            taxpayer_name=form_request.taxpayer_name,
            residential_status=form_request.residential_status,
            date_of_birth=datetime.strptime(form_request.date_of_birth, "%Y-%m-%d").date(),
            aadhaar_number=form_request.aadhaar_number,
            salary_income=Decimal(str(form_request.salary_income)),
            interest_income=Decimal(str(form_request.interest_income)),
            dividend_income=Decimal(str(form_request.dividend_income)),
            capital_gains=Decimal(str(form_request.capital_gains)),
            business_income=Decimal(str(form_request.business_income)),
            other_income=Decimal(str(form_request.other_income)),
            deductions_80c=Decimal(str(form_request.deductions_80c)),
            deductions_80d=Decimal(str(form_request.deductions_80d)),
            deductions_80e=Decimal(str(form_request.deductions_80e)),
            deductions_80g=Decimal(str(form_request.deductions_80g)),
            deductions_80gg=Decimal(str(form_request.deductions_80gg)),
            home_loan_interest=Decimal(str(form_request.home_loan_interest)),
            tax_liability=Decimal(str(form_request.tax_liability)),
            cess=Decimal(str(form_request.cess)),
            tds_claimed=Decimal(str(form_request.tds_claimed)),
            tcs_paid=Decimal(str(form_request.tcs_paid)),
            ais_entry_id=form_request.ais_entry_id,
            form_26as_entry_id=form_request.form_26as_entry_id,
        )
        
        json_export = portal.generate_json_export(form)
        
        return {
            "ok": True,
            "format": "json",
            "data": json_export,
            "filename": f"ITR-{form_request.taxpayer_pan}-AY{form_request.assessment_year}.json"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/export/xml")
def export_as_xml(form_request: ITRFormRequest):
    """Export ITR form as XML for offline utility"""
    try:
        form = ITRForm(
            assessment_year=form_request.assessment_year,
            taxpayer_pan=form_request.taxpayer_pan,
            taxpayer_name=form_request.taxpayer_name,
            residential_status=form_request.residential_status,
            date_of_birth=datetime.strptime(form_request.date_of_birth, "%Y-%m-%d").date(),
            aadhaar_number=form_request.aadhaar_number,
            salary_income=Decimal(str(form_request.salary_income)),
            interest_income=Decimal(str(form_request.interest_income)),
            dividend_income=Decimal(str(form_request.dividend_income)),
            capital_gains=Decimal(str(form_request.capital_gains)),
            business_income=Decimal(str(form_request.business_income)),
            other_income=Decimal(str(form_request.other_income)),
            deductions_80c=Decimal(str(form_request.deductions_80c)),
            deductions_80d=Decimal(str(form_request.deductions_80d)),
            deductions_80e=Decimal(str(form_request.deductions_80e)),
            deductions_80g=Decimal(str(form_request.deductions_80g)),
            deductions_80gg=Decimal(str(form_request.deductions_80gg)),
            home_loan_interest=Decimal(str(form_request.home_loan_interest)),
            tax_liability=Decimal(str(form_request.tax_liability)),
            cess=Decimal(str(form_request.cess)),
            tds_claimed=Decimal(str(form_request.tds_claimed)),
            tcs_paid=Decimal(str(form_request.tcs_paid)),
            ais_entry_id=form_request.ais_entry_id,
            form_26as_entry_id=form_request.form_26as_entry_id,
        )
        
        xml_export = portal.generate_xml_for_offline_utility(form)
        
        return {
            "ok": True,
            "format": "xml",
            "data": xml_export,
            "filename": f"ITR-{form_request.taxpayer_pan}-AY{form_request.assessment_year}.xml",
            "instructions": "Download this XML file and sign using the Income Tax Offline Utility before uploading to portal"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# SUBMISSION ENDPOINTS
# ============================================================================


@router.post("/submit/digital-signature")
def submit_with_digital_signature(request: SubmitWithSignatureRequest):
    """Submit ITR with Digital Signature (DSC)"""
    try:
        form = ITRForm(
            assessment_year=request.form_data.assessment_year,
            taxpayer_pan=request.form_data.taxpayer_pan,
            taxpayer_name=request.form_data.taxpayer_name,
            residential_status=request.form_data.residential_status,
            date_of_birth=datetime.strptime(request.form_data.date_of_birth, "%Y-%m-%d").date(),
            aadhaar_number=request.form_data.aadhaar_number,
            salary_income=Decimal(str(request.form_data.salary_income)),
            interest_income=Decimal(str(request.form_data.interest_income)),
            dividend_income=Decimal(str(request.form_data.dividend_income)),
            capital_gains=Decimal(str(request.form_data.capital_gains)),
            business_income=Decimal(str(request.form_data.business_income)),
            other_income=Decimal(str(request.form_data.other_income)),
            deductions_80c=Decimal(str(request.form_data.deductions_80c)),
            deductions_80d=Decimal(str(request.form_data.deductions_80d)),
            deductions_80e=Decimal(str(request.form_data.deductions_80e)),
            deductions_80g=Decimal(str(request.form_data.deductions_80g)),
            deductions_80gg=Decimal(str(request.form_data.deductions_80gg)),
            home_loan_interest=Decimal(str(request.form_data.home_loan_interest)),
            tax_liability=Decimal(str(request.form_data.tax_liability)),
            cess=Decimal(str(request.form_data.cess)),
            tds_claimed=Decimal(str(request.form_data.tds_claimed)),
            tcs_paid=Decimal(str(request.form_data.tcs_paid)),
            ais_entry_id=request.form_data.ais_entry_id,
            form_26as_entry_id=request.form_data.form_26as_entry_id,
        )
        
        signature_data = {"signature": request.signature_value}
        ack = portal.submit_direct_to_portal(form, signature_data)
        
        return {
            "ok": True,
            "acknowledgment": {
                "number": ack.acknowledgment_number,
                "taxpayer_pan": ack.taxpayer_pan,
                "assessment_year": ack.assessment_year,
                "filing_date": ack.filing_date.isoformat(),
                "status": ack.status.value,
                "gross_income": float(ack.gross_income),
                "tax_liability": float(ack.tax_liability),
                "refund_due": float(ack.refund_due) if ack.refund_due else None,
                "processing_status": ack.processing_status,
                "expected_completion": ack.expected_completion_date.isoformat() if ack.expected_completion_date else None,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/submit/otp")
def submit_with_otp(request: SubmitWithOTPRequest):
    """Submit ITR via OTP-based e-filing"""
    try:
        form = ITRForm(
            assessment_year=request.form_data.assessment_year,
            taxpayer_pan=request.form_data.taxpayer_pan,
            taxpayer_name=request.form_data.taxpayer_name,
            residential_status=request.form_data.residential_status,
            date_of_birth=datetime.strptime(request.form_data.date_of_birth, "%Y-%m-%d").date(),
            aadhaar_number=request.form_data.aadhaar_number,
            salary_income=Decimal(str(request.form_data.salary_income)),
            interest_income=Decimal(str(request.form_data.interest_income)),
            dividend_income=Decimal(str(request.form_data.dividend_income)),
            capital_gains=Decimal(str(request.form_data.capital_gains)),
            business_income=Decimal(str(request.form_data.business_income)),
            other_income=Decimal(str(request.form_data.other_income)),
            deductions_80c=Decimal(str(request.form_data.deductions_80c)),
            deductions_80d=Decimal(str(request.form_data.deductions_80d)),
            deductions_80e=Decimal(str(request.form_data.deductions_80e)),
            deductions_80g=Decimal(str(request.form_data.deductions_80g)),
            deductions_80gg=Decimal(str(request.form_data.deductions_80gg)),
            home_loan_interest=Decimal(str(request.form_data.home_loan_interest)),
            tax_liability=Decimal(str(request.form_data.tax_liability)),
            cess=Decimal(str(request.form_data.cess)),
            tds_claimed=Decimal(str(request.form_data.tds_claimed)),
            tcs_paid=Decimal(str(request.form_data.tcs_paid)),
            ais_entry_id=request.form_data.ais_entry_id,
            form_26as_entry_id=request.form_data.form_26as_entry_id,
        )
        
        ack = portal.submit_via_otp(form, request.otp)
        
        return {
            "ok": True,
            "acknowledgment": {
                "number": ack.acknowledgment_number,
                "taxpayer_pan": ack.taxpayer_pan,
                "filing_date": ack.filing_date.isoformat(),
                "status": ack.status.value,
                "processing_status": ack.processing_status,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/submit/offline-xml")
async def submit_offline_xml(
    taxpayer_pan: str,
    assessment_year: int,
    file: UploadFile = File(...)
):
    """Submit offline utility signed XML file"""
    try:
        # Read and validate XML
        contents = await file.read()
        
        # In production, validate signature and structure
        # For now, just acknowledge
        ack = FilingAcknowledgment(
            acknowledgment_number=f"ITR-{assessment_year}-{taxpayer_pan}-OFFLINE-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            taxpayer_pan=taxpayer_pan,
            assessment_year=assessment_year,
            filing_date=datetime.now(),
            filing_method=FilingMethod.OFFLINE_UTILITY,
            status=FilingStatus.ACKNOWLEDGED,
            gross_income=Decimal("0"),
            tax_liability=Decimal("0"),
            processing_status="Submitted - XML received for processing"
        )
        
        return {
            "ok": True,
            "acknowledgment": {
                "number": ack.acknowledgment_number,
                "filing_date": ack.filing_date.isoformat(),
                "status": ack.status.value,
                "notes": "XML signed file received. Processing initiated."
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# AMENDMENT ENDPOINTS
# ============================================================================


@router.post("/amend")
def file_amended_return(request: AmendmentRequest):
    """File amended ITR return"""
    try:
        revised_form = ITRForm(
            assessment_year=request.revised_form_data.assessment_year,
            taxpayer_pan=request.revised_form_data.taxpayer_pan,
            taxpayer_name=request.revised_form_data.taxpayer_name,
            residential_status=request.revised_form_data.residential_status,
            date_of_birth=datetime.strptime(request.revised_form_data.date_of_birth, "%Y-%m-%d").date(),
            aadhaar_number=request.revised_form_data.aadhaar_number,
            salary_income=Decimal(str(request.revised_form_data.salary_income)),
            interest_income=Decimal(str(request.revised_form_data.interest_income)),
            dividend_income=Decimal(str(request.revised_form_data.dividend_income)),
            capital_gains=Decimal(str(request.revised_form_data.capital_gains)),
            business_income=Decimal(str(request.revised_form_data.business_income)),
            other_income=Decimal(str(request.revised_form_data.other_income)),
            deductions_80c=Decimal(str(request.revised_form_data.deductions_80c)),
            deductions_80d=Decimal(str(request.revised_form_data.deductions_80d)),
            deductions_80e=Decimal(str(request.revised_form_data.deductions_80e)),
            deductions_80g=Decimal(str(request.revised_form_data.deductions_80g)),
            deductions_80gg=Decimal(str(request.revised_form_data.deductions_80gg)),
            home_loan_interest=Decimal(str(request.revised_form_data.home_loan_interest)),
            tax_liability=Decimal(str(request.revised_form_data.tax_liability)),
            cess=Decimal(str(request.revised_form_data.cess)),
            tds_claimed=Decimal(str(request.revised_form_data.tds_claimed)),
            tcs_paid=Decimal(str(request.revised_form_data.tcs_paid)),
            ais_entry_id=request.revised_form_data.ais_entry_id,
            form_26as_entry_id=request.revised_form_data.form_26as_entry_id,
        )
        
        ack = amendment_tracker.file_revised_return(
            request.original_acknowledgment,
            revised_form,
            request.amendment_reason
        )
        
        return {
            "ok": True,
            "acknowledgment": {
                "number": ack.acknowledgment_number,
                "original_acknowledgment": request.original_acknowledgment,
                "status": ack.status.value,
                "filing_date": ack.filing_date.isoformat(),
                "amendment_reason": request.amendment_reason,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/amendment-history/{acknowledgment_number}")
def get_amendment_history(acknowledgment_number: str):
    """Get amendment history for acknowledgment"""
    try:
        history = amendment_tracker.get_amendment_history(acknowledgment_number)
        
        return {
            "ok": True,
            "acknowledgment_number": acknowledgment_number,
            "amendments": history,
            "total_amendments": len(history)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# STATUS & TRACKING
# ============================================================================


@router.get("/status/{acknowledgment_number}")
def get_filing_status(acknowledgment_number: str):
    """Get ITR filing status"""
    try:
        # In production, query database
        return {
            "ok": True,
            "acknowledgment_number": acknowledgment_number,
            "status": "submitted",
            "processing_status": "Under Processing",
            "submitted_date": datetime.now().isoformat(),
            "expected_completion": datetime.now().replace(day=datetime.now().day + 7).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
