from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text,
    UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Taxpayer(Base, TimestampMixin):
    __tablename__ = "taxpayers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    pan_last4: Mapped[Optional[str]] = mapped_column(String(4))
    citizenship: Mapped[str] = mapped_column(String(80), default="Indian")
    email: Mapped[Optional[str]] = mapped_column(String(200))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Dependent child details (for daughter benefits)
    has_dependent_child: Mapped[bool] = mapped_column(Boolean, default=False)
    dependent_child_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    dependent_child_age: Mapped[Optional[float]] = mapped_column(Numeric(4,2), nullable=True)
    dependent_child_country_of_residence: Mapped[Optional[str]] = mapped_column(String(80), default="India", nullable=True)
    dependent_child_citizenship: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)

    cases: Mapped[list["TaxCase"]] = relationship(back_populates="taxpayer")

    @property
    def is_eligible_for_80ac(self) -> bool:
        """Return True if taxpayer can claim Section 80AC for their dependent girl child.

        Requirements:
        - Dependent child exists
        - Child is under 10 years old
        - Child is resident in India (explicit requirement)
        """
        if not self.has_dependent_child:
            return False
        try:
            age = float(self.dependent_child_age) if self.dependent_child_age is not None else None
        except Exception:
            age = None
        if age is None or age >= 10:
            return False
        if self.dependent_child_country_of_residence and self.dependent_child_country_of_residence.strip().lower() != "india":
            return False
        return True


class TaxCase(Base, TimestampMixin):
    __tablename__ = "tax_cases"
    __table_args__ = (UniqueConstraint("taxpayer_id", "assessment_year"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    taxpayer_id: Mapped[int] = mapped_column(ForeignKey("taxpayers.id"))
    assessment_year: Mapped[str] = mapped_column(String(9))
    financial_year: Mapped[str] = mapped_column(String(9))
    residential_status: Mapped[str] = mapped_column(String(10))
    return_form: Mapped[str] = mapped_column(String(20), default="ITR-2")
    tax_regime: Mapped[str] = mapped_column(String(20), default="Undecided")
    case_status: Mapped[str] = mapped_column(String(30), default="Collecting")
    filing_date: Mapped[Optional[date]] = mapped_column(Date)
    acknowledgement_no: Mapped[Optional[str]] = mapped_column(String(80))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    taxpayer: Mapped["Taxpayer"] = relationship(back_populates="cases")
    documents: Mapped[list["DocumentRequirement"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    income_entries: Mapped[list["IncomeEntry"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )


class BankAccount(Base, TimestampMixin):
    __tablename__ = "bank_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    taxpayer_id: Mapped[int] = mapped_column(ForeignKey("taxpayers.id"))
    bank_name: Mapped[str] = mapped_column(String(120))
    account_type: Mapped[str] = mapped_column(String(30))
    account_last4: Mapped[Optional[str]] = mapped_column(String(4))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)


class DocumentRequirement(Base, TimestampMixin):
    __tablename__ = "document_requirements"
    __table_args__ = (UniqueConstraint("case_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("tax_cases.id"))
    code: Mapped[str] = mapped_column(String(80))
    category: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(240))
    institution: Mapped[Optional[str]] = mapped_column(String(120))
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(30), default="Missing")
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    file_path: Mapped[Optional[str]] = mapped_column(Text)
    source_period: Mapped[Optional[str]] = mapped_column(String(50))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    case: Mapped["TaxCase"] = relationship(back_populates="documents")


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"
    __table_args__ = (UniqueConstraint("case_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("tax_cases.id"))
    code: Mapped[str] = mapped_column(String(80))
    phase: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(30), default="Not started")
    blocking: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    case: Mapped["TaxCase"] = relationship(back_populates="tasks")


class ResidencyRecord(Base, TimestampMixin):
    __tablename__ = "residency_records"
    __table_args__ = (UniqueConstraint("case_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("tax_cases.id"))
    days_in_india_current_fy: Mapped[Optional[int]] = mapped_column(Integer)
    days_in_india_prior_4y: Mapped[Optional[int]] = mapped_column(Integer)
    days_in_india_prior_7y: Mapped[Optional[int]] = mapped_column(Integer)
    nonresident_years_prior_10y: Mapped[Optional[int]] = mapped_column(Integer)
    date_returned_to_india: Mapped[Optional[date]] = mapped_column(Date)
    foreign_income_received_in_india: Mapped[bool] = mapped_column(Boolean, default=False)
    business_controlled_from_india: Mapped[bool] = mapped_column(Boolean, default=False)
    conclusion: Mapped[Optional[str]] = mapped_column(String(20))
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(120))
    notes: Mapped[Optional[str]] = mapped_column(Text)


class IncomeEntry(Base, TimestampMixin):
    __tablename__ = "income_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("tax_cases.id"))
    income_type: Mapped[str] = mapped_column(String(60))
    source_name: Mapped[str] = mapped_column(String(160))
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    tds_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    amount_in_return: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    exempt_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    bank_account_last4: Mapped[Optional[str]] = mapped_column(String(4))
    evidence_code: Mapped[Optional[str]] = mapped_column(String(80))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    
    case: Mapped["TaxCase"] = relationship(back_populates="income_entries")


class TaxCredit(Base, TimestampMixin):
    __tablename__ = "tax_credits"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("tax_cases.id"))
    deductor: Mapped[str] = mapped_column(String(180))
    credit_type: Mapped[str] = mapped_column(String(40), default="TDS")
    section_code: Mapped[Optional[str]] = mapped_column(String(20))
    gross_amount_26as: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    tax_amount_26as: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    tax_claimed: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text)


class ReconciliationItem(Base, TimestampMixin):
    __tablename__ = "reconciliation_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeKey("tax_cases.id")) if False else mapped_column(ForeignKey("tax_cases.id"))
    category: Mapped[str] = mapped_column(String(80))
    source: Mapped[str] = mapped_column(String(120))
    source_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    ais_26as_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    return_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    status: Mapped[str] = mapped_column(String(30), default="Open")
    explanation: Mapped[Optional[str]] = mapped_column(Text)


class PropertyLoan(Base, TimestampMixin):
    __tablename__ = "property_loans"
    __table_args__ = (UniqueConstraint("case_id", "property_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("tax_cases.id"))
    property_name: Mapped[str] = mapped_column(String(180))
    property_address: Mapped[Optional[str]] = mapped_column(Text)
    ownership_percent: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    self_occupied: Mapped[bool] = mapped_column(Boolean, default=True)
    possession_date: Mapped[Optional[date]] = mapped_column(Date)
    loan_start_date: Mapped[Optional[date]] = mapped_column(Date)
    lender: Mapped[Optional[str]] = mapped_column(String(120))
    interest_fy: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    principal_fy: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    preconstruction_interest: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    actual_payment_percent: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tax_cases.id"))
    event_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    action: Mapped[str] = mapped_column(String(80))
    entity: Mapped[str] = mapped_column(String(80))
    details: Mapped[Optional[str]] = mapped_column(Text)


class TaxDeduction(Base, TimestampMixin):
    """Tax deduction entries (80C, 80D, 80E, 80AC, 24(b), 80CCD, etc.)"""
    __tablename__ = "tax_deductions"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("tax_cases.id"))
    section_code: Mapped[str] = mapped_column(String(20))  # 80C, 80D, 80E, 80AC, etc.
    category: Mapped[str] = mapped_column(String(100))  # Life Insurance, Education, Health, etc.
    description: Mapped[str] = mapped_column(String(240))
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    max_eligible: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    eligible: Mapped[bool] = mapped_column(Boolean, default=True)
    reason_ineligible: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)


class DeductionReference(Base):
    """Government references for deductions with explanations"""
    __tablename__ = "deduction_references"

    id: Mapped[int] = mapped_column(primary_key=True)
    section_code: Mapped[str] = mapped_column(String(20), unique=True)
    act_reference: Mapped[str] = mapped_column(String(80))  # Income Tax Act, 1961
    max_limit_fy: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    description: Mapped[str] = mapped_column(Text)
    eligibility_criteria: Mapped[str] = mapped_column(Text)
    applicable_to_nri: Mapped[bool] = mapped_column(Boolean, default=False)
    applicable_to_rnor: Mapped[bool] = mapped_column(Boolean, default=True)
    portal_url: Mapped[str] = mapped_column(String(500))
    last_updated_ay: Mapped[str] = mapped_column(String(9))


class TaxCalculationSummary(Base, TimestampMixin):
    """Final tax calculation summary for filing"""
    __tablename__ = "tax_calculation_summary"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("tax_cases.id"), unique=True)
    
    # Income
    total_gross_income: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    exempt_income: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    taxable_income: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    
    # Deductions (computed)
    total_80c_deduction: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    total_80d_deduction: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    total_80e_deduction: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    total_80ac_deduction: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    home_loan_interest_24b: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    nps_deduction_80ccd: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    other_deductions: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    total_deductions: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    
    # Taxable income after deductions
    income_after_deductions: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    
    # Old Regime Calculation
    old_regime_tax: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    old_regime_surcharge: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    old_regime_cess: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    old_regime_total_tax: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    old_regime_effective_rate: Mapped[Decimal] = mapped_column(Numeric(6, 3), default=0)  # %
    
    # New Regime Calculation
    new_regime_tax: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    new_regime_surcharge: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    new_regime_cess: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    new_regime_total_tax: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    new_regime_effective_rate: Mapped[Decimal] = mapped_column(Numeric(6, 3), default=0)  # %
    
    # Tax credits & Final tax
    total_tds_credits: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    total_tcs_credits: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    
    # Final payable/refund
    final_tax_payable_old_regime: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    final_tax_payable_new_regime: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    recommended_regime: Mapped[str] = mapped_column(String(20))  # "Old" or "New"
    tax_savings_opportunity: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    
    # Filing status
    filing_status: Mapped[str] = mapped_column(String(30), default="Draft")  # Draft, Review, Ready, Filed
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    filed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class FilingReport(Base, TimestampMixin):
    """Professional reports for review before filing"""
    __tablename__ = "filing_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("tax_cases.id"))
    
    # Report 1: Calculation Breakdown
    report1_title: Mapped[str] = mapped_column(String(240), default="Tax Calculation Breakdown with Government References")
    report1_content_json: Mapped[Text] = mapped_column(Text)  # Detailed calculations
    report1_generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Report 2: ITR Form Summary
    report2_title: Mapped[str] = mapped_column(String(240), default="ITR-2 Form Summary - Ready to File")
    report2_content_json: Mapped[Text] = mapped_column(Text)  # Form data in portal format
    report2_generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Signature & Filing
    signature_captured: Mapped[bool] = mapped_column(Boolean, default=False)
    signature_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime)
    portal_filing_link: Mapped[Optional[str]] = mapped_column(String(500))
    filing_acknowledgement_no: Mapped[Optional[str]] = mapped_column(String(80))
    filing_status: Mapped[str] = mapped_column(String(30), default="Pending")  # Pending, Submitted, Acknowledged, Filed
