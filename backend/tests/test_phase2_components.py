"""
Tests for Phase 2 components:
- Tax Report Generator
- Household Assistant
- AI Master Orchestrator
- Document Parser AI
"""

import pytest
from datetime import date, datetime
from decimal import Decimal

from backend.app.tax_calculator import (
    TaxCalculator, TaxRegime, ResidencyStatus as TCResidencyStatus,
    IncomeSource, Deduction, TaxCalculationResult
)
from backend.app.report_generator import (
    TaxReportGenerator, ReportMetadata, ReportFormat,
    CalculationBreakdownReport, FormSummaryReport
)
from backend.app.household_assistant import (
    HouseholdAssistant, FamilyMember, Relationship, ResidencyStatus as HAResidencyStatus,
    LifeEvent, LifeEventType, HouseholdProfile
)
from backend.app.ai_orchestrator import (
    AIMasterOrchestrator, IntentClassifier, SpecialistType, SessionContext
)
from backend.app.document_parser_ai import (
    DocumentParser, DocumentType, BankStatementParser,
    Form26ASParser, AISParser
)


class TestTaxReportGenerator:
    """Tests for tax report generation"""

    @pytest.fixture
    def calculation_result(self):
        """Create sample calculation result"""
        calc = TaxCalculator()
        income = [IncomeSource("Salary", Decimal(1500000), "salary")]
        result = calc.calculate(
            income_sources=income,
            deductions=[],
            residency_status=TCResidencyStatus.ROR,
        )
        return result

    @pytest.fixture
    def metadata(self):
        """Create report metadata"""
        return ReportMetadata(
            assessment_year=2026,
            financial_year="2025-26",
            individual_name="Nilesh Hapatel",
            pan="XXXX1234",
            residency_status=TCResidencyStatus.ROR,
            date_generated=datetime.now(),
        )

    def test_calculation_breakdown_json(self, calculation_result, metadata):
        """Test JSON report generation"""
        report = CalculationBreakdownReport(calculation_result, metadata)
        json_output = report.generate_json()
        
        assert "metadata" in json_output
        assert "tax_summary" in json_output
        assert json_output["metadata"]["assessment_year"] == 2026

    def test_calculation_breakdown_html(self, calculation_result, metadata):
        """Test HTML report generation"""
        report = CalculationBreakdownReport(calculation_result, metadata)
        html_output = report.generate_html()
        
        assert "<!DOCTYPE html>" in html_output
        assert metadata.individual_name in html_output

    def test_form_summary_itr2_mapping(self, calculation_result, metadata):
        """Test ITR-2 form mapping"""
        report = FormSummaryReport(calculation_result, metadata)
        mapping = report.generate_itr2_mapping()
        
        assert "part_a" in mapping
        assert "part_b" in mapping
        assert mapping["part_a"]["pan"] == metadata.pan

    def test_complete_report_generation(self, calculation_result, metadata):
        """Test complete report with both parts"""
        generator = TaxReportGenerator()
        complete_report = generator.generate_complete_report(
            calculation_result, metadata
        )
        
        assert "metadata" in complete_report
        assert "calculation_breakdown" in complete_report
        assert "form_summary" in complete_report


class TestHouseholdAssistant:
    """Tests for household management"""

    @pytest.fixture
    def primary_member(self):
        """Create primary family member"""
        return FamilyMember(
            name="Nilesh Hapatel",
            pan="1234",
            date_of_birth=date(1990, 5, 15),
            relationship_to_primary=Relationship.SELF,
            residency_status=HAResidencyStatus.NRI,
            assessment_year=2026,
            annual_income=Decimal(2000000),
        )

    @pytest.fixture
    def household_assistant(self):
        """Create household assistant"""
        return HouseholdAssistant(assessment_year=2026)

    def test_create_household(self, household_assistant, primary_member):
        """Test household creation"""
        household = household_assistant.create_household(primary_member)
        
        assert len(household.members) == 1
        assert household.assessment_year == 2026

    def test_add_family_member(self, household_assistant, primary_member):
        """Test adding family member"""
        household = household_assistant.create_household(primary_member)
        
        spouse = FamilyMember(
            name="Avani Hapatel",
            pan="5678",
            date_of_birth=date(1992, 8, 20),
            relationship_to_primary=Relationship.SPOUSE,
            residency_status=HAResidencyStatus.RNOR,
            assessment_year=2026,
            annual_income=Decimal(1500000),
        )
        
        assert household.add_member(spouse)
        assert len(household.members) == 2

    def test_life_event_tracking(self, household_assistant, primary_member):
        """Test life event recording"""
        household = household_assistant.create_household(primary_member)
        
        event = LifeEvent(
            event_type=LifeEventType.MARRIAGE,
            date=date(2020, 6, 15),
            description="Marriage event",
            impact_on_residency=True,
            impact_on_deductions=True,
            documentation_required=["Marriage Certificate"],
        )
        
        assert household.add_life_event(primary_member.id, event)
        assert len(primary_member.life_events) == 1

    def test_filing_checklist_generation(self, household_assistant, primary_member):
        """Test filing checklist"""
        household = household_assistant.create_household(primary_member)
        checklist = household.get_filing_checklist()
        
        assert "Nilesh Hapatel" in checklist
        assert "tasks" in checklist["Nilesh Hapatel"]

    def test_household_dashboard(self, household_assistant, primary_member):
        """Test household dashboard"""
        household = household_assistant.create_household(primary_member)
        dashboard = household.get_household_dashboard()
        
        assert dashboard["household"]["total_members"] == 1
        assert "filing_summary" in dashboard
        assert "income_summary" in dashboard

    def test_senior_citizen_check(self):
        """Test senior citizen identification"""
        senior = FamilyMember(
            name="Senior Member",
            pan="0000",
            date_of_birth=date(1960, 1, 1),
            relationship_to_primary=Relationship.PARENT,
            residency_status=HAResidencyStatus.ROR,
            assessment_year=2026,
        )
        
        assert senior.is_senior_citizen()


class TestAIMasterOrchestrator:
    """Tests for AI orchestrator"""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator"""
        return AIMasterOrchestrator()

    def test_intent_classification_tax(self):
        """Test tax question classification"""
        classifier = IntentClassifier()
        specialist, confidence = classifier.classify(
            "What's my tax calculation? Is the new regime better?"
        )
        
        assert specialist == SpecialistType.TAX
        assert confidence > 0

    def test_intent_classification_deduction(self):
        """Test deduction question classification"""
        classifier = IntentClassifier()
        specialist, confidence = classifier.classify(
            "How much can I claim under 80C? I have PPF and insurance."
        )
        
        assert specialist == SpecialistType.DEDUCTION

    def test_entity_extraction(self):
        """Test entity extraction"""
        classifier = IntentClassifier()
        entities = classifier.extract_entities(
            "I have ₹50,000 in 80C and earned ₹500,000 this year."
        )
        
        assert "amounts" in entities

    def test_session_creation(self, orchestrator):
        """Test session creation"""
        session = orchestrator.start_session(
            household_id="hh1",
            member_ids=["m1", "m2"],
            assessment_year=2026,
        )
        
        assert session.household_id == "hh1"
        assert len(session.member_ids) == 2

    def test_message_routing(self, orchestrator):
        """Test message routing to specialist"""
        session = orchestrator.start_session(
            household_id="hh1",
            member_ids=["m1"],
        )
        
        turn = orchestrator.process_user_message(
            session.session_id,
            "What's my tax calculation for ₹1500000 income?"
        )
        
        assert turn.specialist_routed_to == SpecialistType.TAX
        assert len(turn.follow_up_questions) > 0


class TestDocumentParser:
    """Tests for document parsing"""

    @pytest.fixture
    def parser(self):
        """Create document parser"""
        return DocumentParser()

    def test_bank_statement_parsing(self, parser):
        """Test bank statement parsing"""
        bank_text = """
        Account Number: 123456789012
        Interest Credited: ₹50,000
        Account Type: NRE
        """
        
        result = parser.parse_document(
            bank_text,
            "doc1",
            DocumentType.BANK_STATEMENT
        )
        
        assert result.document_type == DocumentType.BANK_STATEMENT
        assert "account_type" in result.content

    def test_form_26as_parsing(self, parser):
        """Test Form 26AS parsing"""
        form_text = """
        Form 26AS
        TDS Deducted: ₹100,000
        Section 192: ₹50,000
        Section 194: ₹50,000
        """
        
        result = parser.parse_document(
            form_text,
            "doc2",
            DocumentType.FORM_26AS
        )
        
        assert result.document_type == DocumentType.FORM_26AS

    def test_ais_parsing(self, parser):
        """Test AIS parsing"""
        ais_text = """
        Annual Information Statement
        Total Income: ₹2,000,000
        Salary: ₹1,500,000
        Dividend: ₹300,000
        Interest: ₹200,000
        """
        
        result = parser.parse_document(
            ais_text,
            "doc3",
            DocumentType.AIS
        )
        
        assert result.document_type == DocumentType.AIS

    def test_mutual_fund_parsing(self, parser):
        """Test mutual fund CAS parsing"""
        mf_text = """
        Consolidated Account Statement
        Folio: 123456
        Units: 1,000
        NAV: ₹500
        """
        
        result = parser.parse_document(
            mf_text,
            "doc4",
            DocumentType.MUTUAL_FUND_CAS
        )
        
        assert result.document_type == DocumentType.MUTUAL_FUND_CAS

    def test_document_classification(self, parser):
        """Test document type classification"""
        form_26as_text = "Form 26AS - Tax Deducted - TDS"
        doc_type, confidence = parser.classify_document(form_26as_text)
        
        assert doc_type == DocumentType.FORM_26AS
        assert confidence > 0

    def test_validation(self, parser):
        """Test extraction validation"""
        form_text = "TDS: ₹100,000"
        result = parser.parse_document(
            form_text,
            "doc5",
            DocumentType.FORM_26AS
        )
        
        validation = parser.validate_extraction("doc5")
        assert "validation_status" in validation


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
