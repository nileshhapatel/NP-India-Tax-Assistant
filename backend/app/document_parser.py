"""
Document Parser Module
Extracts structured data from PDF documents (AIS, 26AS, Bank Statements, etc.)
"""
import os
import json
import logging
from typing import Optional, Dict, List, Any
from enum import Enum
import re
from io import BytesIO

logger = logging.getLogger(__name__)


class DocumentType(str, Enum):
    """Supported document types for extraction"""
    AIS = "ais"
    FORM_26AS = "form_26as"
    BANK_STATEMENT = "bank_statement"
    TDS_CERT = "tds_certificate"
    SALARY_SLIP = "salary_slip"
    HOME_LOAN_CERT = "home_loan_certificate"
    CAS = "cas"  # Consolidated Account Statement (MF)
    DIV_REPORT = "dividend_report"
    TAX_AUDIT_CERT = "tax_audit_certificate"


class DocumentParseResult:
    """Result of document parsing"""

    def __init__(
        self,
        success: bool,
        doc_type: str,
        extracted_data: Optional[Dict] = None,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        raw_text: Optional[str] = None,
    ):
        self.success = success
        self.doc_type = doc_type
        self.extracted_data = extracted_data or {}
        self.errors = errors or []
        self.warnings = warnings or []
        self.raw_text = raw_text

    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'doc_type': self.doc_type,
            'extracted_data': self.extracted_data,
            'errors': self.errors,
            'warnings': self.warnings,
            'has_raw_text': bool(self.raw_text),
        }


class PDFParser:
    """PDF extraction using PyPDF2 or pdfplumber if available"""

    def __init__(self):
        self.pdf_library = self._detect_pdf_library()

    def _detect_pdf_library(self) -> Optional[str]:
        """Detect available PDF library"""
        try:
            import pdfplumber
            return "pdfplumber"
        except ImportError:
            pass

        try:
            import PyPDF2
            return "PyPDF2"
        except ImportError:
            pass

        logger.warning("No PDF library available (pdfplumber or PyPDF2)")
        return None

    def extract_text(self, file_path: str) -> Optional[str]:
        """Extract text from PDF file"""
        if not self.pdf_library:
            logger.error("No PDF library available")
            return None

        try:
            if self.pdf_library == "pdfplumber":
                import pdfplumber
                with pdfplumber.open(file_path) as pdf:
                    text = ""
                    for page in pdf.pages:
                        text += page.extract_text() or ""
                    return text

            elif self.pdf_library == "PyPDF2":
                import PyPDF2
                with open(file_path, 'rb') as file:
                    reader = PyPDF2.PdfReader(file)
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text()
                    return text

        except Exception as e:
            logger.error(f"PDF extraction error: {e}")
            return None

        return None

    def extract_tables(self, file_path: str) -> Optional[List[List]]:
        """Extract tables from PDF (pdfplumber only)"""
        if self.pdf_library != "pdfplumber":
            logger.warning("Table extraction requires pdfplumber")
            return None

        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                tables = []
                for page in pdf.pages:
                    page_tables = page.extract_tables()
                    if page_tables:
                        tables.extend(page_tables)
                return tables if tables else None
        except Exception as e:
            logger.error(f"Table extraction error: {e}")
            return None


class AISParser:
    """Parse Annual Information Statement (AIS) PDFs"""

    @staticmethod
    def parse(text: str) -> DocumentParseResult:
        """Parse AIS PDF text"""
        errors = []
        warnings = []
        data = {
            'pan': None,
            'assessment_year': None,
            'financial_year': None,
            'sections': [],
            'total_income': 0,
            'tds_tcs': 0,
        }

        if not text:
            errors.append("No text extracted from AIS PDF")
            return DocumentParseResult(
                success=False,
                doc_type=DocumentType.AIS.value,
                errors=errors,
                extracted_data=data,
            )

        # Extract PAN
        pan_match = re.search(r'PAN[:\s]+([A-Z0-9]{10})', text)
        if pan_match:
            data['pan'] = pan_match.group(1)
        else:
            warnings.append("PAN not found in AIS")

        # Extract Assessment Year
        ay_match = re.search(r'Assessment Year[:\s]+(\d{4}-\d{2})', text)
        if ay_match:
            data['assessment_year'] = ay_match.group(1)
        else:
            warnings.append("Assessment Year not found")

        # Extract sections (salary, interest, dividend, etc.)
        sections = {
            'Salary': re.search(r'Salary.*?₹\s*([\d,]+)', text),
            'Interest': re.search(r'Interest.*?₹\s*([\d,]+)', text),
            'Dividend': re.search(r'Dividend.*?₹\s*([\d,]+)', text),
            'Rental': re.search(r'Rental.*?₹\s*([\d,]+)', text),
            'TDS': re.search(r'TDS.*?₹\s*([\d,]+)', text),
        }

        for section_name, match in sections.items():
            if match:
                amount = int(match.group(1).replace(',', ''))
                data['sections'].append({'section': section_name, 'amount': amount})
                if section_name != 'TDS':
                    data['total_income'] += amount
                else:
                    data['tds_tcs'] = amount

        if not data['sections']:
            warnings.append("No income sections found in AIS")

        return DocumentParseResult(
            success=len(errors) == 0,
            doc_type=DocumentType.AIS.value,
            extracted_data=data,
            errors=errors,
            warnings=warnings,
            raw_text=text[:500],  # Store first 500 chars
        )


class Form26ASParser:
    """Parse Form 26AS PDFs (TDS and TCS Statement)"""

    @staticmethod
    def parse(text: str) -> DocumentParseResult:
        """Parse Form 26AS PDF text"""
        errors = []
        warnings = []
        data = {
            'pan': None,
            'assessment_year': None,
            'tds_entries': [],
            'tcs_entries': [],
            'total_tds': 0,
            'total_tcs': 0,
        }

        if not text:
            errors.append("No text extracted from Form 26AS PDF")
            return DocumentParseResult(
                success=False,
                doc_type=DocumentType.FORM_26AS.value,
                errors=errors,
                extracted_data=data,
            )

        # Extract PAN
        pan_match = re.search(r'PAN[:\s]+([A-Z0-9]{10})', text)
        if pan_match:
            data['pan'] = pan_match.group(1)
        else:
            warnings.append("PAN not found in Form 26AS")

        # Extract Assessment Year
        ay_match = re.search(r'Assessment Year[:\s]+(\d{4}-\d{2})', text)
        if ay_match:
            data['assessment_year'] = ay_match.group(1)

        # Extract TDS entries (salary, interest, dividend, professional fees)
        tds_pattern = r'(Salary|Interest|Dividend|Professional Fees).*?₹\s*([\d,]+)'
        tds_matches = re.finditer(tds_pattern, text)
        for match in tds_matches:
            source = match.group(1)
            amount = int(match.group(2).replace(',', ''))
            data['tds_entries'].append({'source': source, 'amount': amount})
            data['total_tds'] += amount

        if not data['tds_entries']:
            warnings.append("No TDS entries found in Form 26AS")

        return DocumentParseResult(
            success=len(errors) == 0,
            doc_type=DocumentType.FORM_26AS.value,
            extracted_data=data,
            errors=errors,
            warnings=warnings,
            raw_text=text[:500],
        )


class BankStatementParser:
    """Parse bank statement PDFs"""

    @staticmethod
    def parse(text: str) -> DocumentParseResult:
        """Parse bank statement PDF text"""
        errors = []
        warnings = []
        data = {
            'account_number': None,
            'bank_name': None,
            'account_type': None,
            'opening_balance': 0,
            'closing_balance': 0,
            'total_credits': 0,
            'total_debits': 0,
            'transactions_count': 0,
            'period_from': None,
            'period_to': None,
        }

        if not text:
            errors.append("No text extracted from bank statement")
            return DocumentParseResult(
                success=False,
                doc_type=DocumentType.BANK_STATEMENT.value,
                errors=errors,
                extracted_data=data,
            )

        # Extract account number
        acc_match = re.search(r'Account[:\s]+([0-9]{10,18})', text)
        if acc_match:
            data['account_number'] = acc_match.group(1)
        else:
            warnings.append("Account number not found")

        # Extract bank name
        bank_match = re.search(r'(HDFC|ICICI|Axis|BOB|SBI|IDBI|IndusInd)', text)
        if bank_match:
            data['bank_name'] = bank_match.group(1)
        else:
            warnings.append("Bank name not found")

        # Extract opening and closing balances
        opening_match = re.search(r'Opening Balance[:\s]*₹\s*([\d,]+)', text)
        if opening_match:
            data['opening_balance'] = int(opening_match.group(1).replace(',', ''))

        closing_match = re.search(r'Closing Balance[:\s]*₹\s*([\d,]+)', text)
        if closing_match:
            data['closing_balance'] = int(closing_match.group(1).replace(',', ''))

        # Extract period
        period_match = re.search(r'Period[:\s]*(.+?)\s*to\s*(.+?)(?:\n|$)', text)
        if period_match:
            data['period_from'] = period_match.group(1).strip()
            data['period_to'] = period_match.group(2).strip()

        # Count transactions
        trans_count = len(re.findall(r'\d{2}-\d{2}-\d{4}', text))
        data['transactions_count'] = trans_count

        return DocumentParseResult(
            success=len(errors) == 0,
            doc_type=DocumentType.BANK_STATEMENT.value,
            extracted_data=data,
            errors=errors,
            warnings=warnings,
            raw_text=text[:500],
        )


class CASParser:
    """Parse Consolidated Account Statement (MF/Securities)"""

    @staticmethod
    def parse(text: str) -> DocumentParseResult:
        """Parse CAS PDF text"""
        errors = []
        warnings = []
        data = {
            'pan': None,
            'folio_numbers': [],
            'total_holdings': 0,
            'total_cost': 0,
            'market_value': 0,
            'holdings': [],
        }

        if not text:
            errors.append("No text extracted from CAS PDF")
            return DocumentParseResult(
                success=False,
                doc_type=DocumentType.CAS.value,
                errors=errors,
                extracted_data=data,
            )

        # Extract PAN
        pan_match = re.search(r'PAN[:\s]+([A-Z0-9]{10})', text)
        if pan_match:
            data['pan'] = pan_match.group(1)

        # Extract folio numbers
        folios = re.findall(r'Folio[:\s]+([0-9]+)', text)
        if folios:
            data['folio_numbers'] = list(set(folios))
        else:
            warnings.append("No folio numbers found")

        # Extract holdings info
        holdings_pattern = r'([A-Z][\w\s]+ELSS|Growth|Dividend)\s+([\d,]+)\s+₹\s*([\d,]+)'
        holdings_matches = re.finditer(holdings_pattern, text)
        for match in holdings_matches:
            fund_name = match.group(1).strip()
            units = int(match.group(2).replace(',', ''))
            value = int(match.group(3).replace(',', ''))
            data['holdings'].append({
                'fund': fund_name,
                'units': units,
                'value': value
            })
            data['total_holdings'] += units
            data['market_value'] += value

        if not data['holdings']:
            warnings.append("No holdings found in CAS")

        return DocumentParseResult(
            success=len(errors) == 0,
            doc_type=DocumentType.CAS.value,
            extracted_data=data,
            errors=errors,
            warnings=warnings,
            raw_text=text[:500],
        )


class DocumentParserFactory:
    """Factory for document parsing"""

    _parsers = {
        DocumentType.AIS: AISParser,
        DocumentType.FORM_26AS: Form26ASParser,
        DocumentType.BANK_STATEMENT: BankStatementParser,
        DocumentType.CAS: CASParser,
    }

    @staticmethod
    def parse_document(
        file_path: str,
        doc_type: DocumentType,
    ) -> DocumentParseResult:
        """
        Parse document with appropriate parser
        
        Args:
            file_path: Path to PDF file
            doc_type: Type of document
            
        Returns:
            DocumentParseResult with extracted data
        """
        if not os.path.exists(file_path):
            return DocumentParseResult(
                success=False,
                doc_type=doc_type.value,
                errors=[f"File not found: {file_path}"],
            )

        # Extract text from PDF
        pdf_parser = PDFParser()
        text = pdf_parser.extract_text(file_path)

        if not text:
            return DocumentParseResult(
                success=False,
                doc_type=doc_type.value,
                errors=["Could not extract text from PDF (PDF library not available)"],
                warnings=["Install pdfplumber or PyPDF2 to enable PDF parsing: pip install pdfplumber"],
            )

        # Parse based on document type
        parser_class = DocumentParserFactory._parsers.get(doc_type)
        if parser_class:
            return parser_class.parse(text)
        else:
            return DocumentParseResult(
                success=False,
                doc_type=doc_type.value,
                errors=[f"No parser available for document type: {doc_type.value}"],
            )

    @staticmethod
    def auto_detect_and_parse(file_path: str) -> DocumentParseResult:
        """
        Auto-detect document type and parse
        
        Looks for keywords like "26AS", "AIS", "CAS" in filename or text
        """
        filename = os.path.basename(file_path).lower()

        if '26as' in filename:
            doc_type = DocumentType.FORM_26AS
        elif 'ais' in filename:
            doc_type = DocumentType.AIS
        elif 'cas' in filename or 'mutual' in filename:
            doc_type = DocumentType.CAS
        elif 'bank' in filename or 'statement' in filename:
            doc_type = DocumentType.BANK_STATEMENT
        else:
            doc_type = DocumentType.BANK_STATEMENT  # Default

        return DocumentParserFactory.parse_document(file_path, doc_type)
