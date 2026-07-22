"""
Document Parser Module
Extracts structured data from PDF documents (AIS, 26AS, Bank Statements, Interest Certificates, etc.)

Parsers are tuned for the actual document formats produced by:
  - Bank of Baroda (NRE/NRO combined Interest cum TDS certificate)
  - HDFC Bank (NRE/NRO interest certificates)
  - TRACES Form 26AS
  - NSDL/CBDT Annual Information Statement (AIS)
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
    INTEREST_CERTIFICATE = "interest_certificate"
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
    """
    Parse Annual Information Statement (AIS) PDFs.
    AIS contains: salary, interest, dividend, rent, capital gains, etc.
    """

    @staticmethod
    def parse(text: str) -> DocumentParseResult:
        errors = []
        warnings = []
        data = {
            'pan': None,
            'assessment_year': None,
            'financial_year': None,
            'sections': [],
            'total_income': 0.0,
            'tds_tcs': 0.0,
        }

        if not text:
            errors.append("No text extracted from AIS PDF")
            return DocumentParseResult(
                success=False, doc_type=DocumentType.AIS.value,
                errors=errors, extracted_data=data,
            )

        # PAN
        pan_match = re.search(r'PAN[:\s\(]+([A-Z]{5}\d{4}[A-Z])', text)
        if pan_match:
            data['pan'] = pan_match.group(1)
        else:
            warnings.append("PAN not found in AIS")

        # Assessment Year
        ay_match = re.search(r'Assessment Year[:\s]+(\d{4}-\d{2})', text, re.IGNORECASE)
        if ay_match:
            data['assessment_year'] = ay_match.group(1)

        # AIS sections — try ₹ patterns and plain number patterns
        section_keywords = [
            ('Salary', 'salary_india'),
            ('Interest from savings', 'interest_savings'),
            ('Interest from deposits', 'interest_fd'),
            ('Interest from others', 'interest_other'),
            ('Dividend', 'dividend'),
            ('Rent', 'rental'),
            ('Capital gains', 'cg_long'),
        ]
        for label, itype in section_keywords:
            m = re.search(
                rf'{re.escape(label)}[^\n]*?(?:₹|Rs\.?)?\s*([\d,]+(?:\.\d{{1,2}})?)',
                text, re.IGNORECASE
            )
            if m:
                amt = _parse_amount(m.group(1))
                if amt > 0:
                    data['sections'].append({'section': label, 'amount': amt, 'income_type': itype})
                    data['total_income'] += amt

        if not data['sections']:
            warnings.append("No income sections found in AIS. The AIS PDF may be image-based or encrypted.")

        return DocumentParseResult(
            success=len(errors) == 0,
            doc_type=DocumentType.AIS.value,
            extracted_data=data,
            errors=errors,
            warnings=warnings,
            raw_text=text[:800],
        )


class Form26ASParser:
    """
    Parse Form 26AS PDFs (Annual Tax Statement from TRACES).
    
    Actual format:
      PART-I - Details of Tax Deducted at Source
      1  BANK OF BARODA-OSHIWARA LINK RD   MUMB21306F   5037.00   1572.00   1572.00
         [Sr]  [Name of Deductor]            [TAN]        [Paid]    [TDS]     [Deposited]
    """

    @staticmethod
    def parse(text: str) -> DocumentParseResult:
        errors = []
        warnings = []
        data = {
            'pan': None,
            'assessment_year': None,
            'financial_year': None,
            'tds_entries': [],
            'total_gross': 0.0,
            'total_tds': 0.0,
        }

        if not text:
            errors.append("No text extracted from Form 26AS PDF")
            return DocumentParseResult(
                success=False, doc_type=DocumentType.FORM_26AS.value,
                errors=errors, extracted_data=data,
            )

        # PAN
        pan_match = re.search(r'(?:PAN|Permanent Account Number)[:\s\(]+([A-Z]{5}\d{4}[A-Z])', text)
        if pan_match:
            data['pan'] = pan_match.group(1)
        else:
            warnings.append("PAN not found in Form 26AS")

        # Assessment Year
        ay_match = re.search(r'Assessment Year\s+(\d{4}-\d{2})', text)
        if ay_match:
            data['assessment_year'] = ay_match.group(1)

        # Financial Year
        fy_match = re.search(r'Financial Year\s+(\d{4}-\d{2})', text)
        if fy_match:
            data['financial_year'] = fy_match.group(1)

        # PART-I deductor summary lines (one line per deductor)
        # Pattern: [number]  [deductor name]  [TAN: 4 letters + 5 digits + 1 letter]  [paid]  [tds]  [deposited]
        entry_re = re.compile(
            r'^\d+\s+([A-Z][A-Z0-9\s\-,&./\']+?)\s+([A-Z]{4}\d{5}[A-Z])\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)',
            re.MULTILINE,
        )

        # Restrict to PART-I section if possible
        part1_start = text.find('PART-I')
        part2_start = text.find('PART-II') if 'PART-II' in text else len(text)
        scope = text[part1_start:part2_start] if part1_start >= 0 else text

        for m in entry_re.finditer(scope):
            deductor = m.group(1).strip()
            gross = _parse_amount(m.group(3))
            tds = _parse_amount(m.group(4))
            if gross == 0 and tds == 0:
                continue
            data['tds_entries'].append({
                'deductor': deductor,
                'gross_amount': gross,
                'tds': tds,
            })
            data['total_gross'] += gross
            data['total_tds'] += tds

        if not data['tds_entries']:
            warnings.append(
                "No deductor entries parsed from Form 26AS. "
                "Verify the PDF is text-based (not scanned image)."
            )

        return DocumentParseResult(
            success=len(errors) == 0,
            doc_type=DocumentType.FORM_26AS.value,
            extracted_data=data,
            errors=errors,
            warnings=warnings,
            raw_text=text[:800],
        )


def _parse_amount(text: str) -> float:
    """Parse a numeric string with optional commas to float."""
    try:
        return float(str(text).replace(',', '').strip())
    except (ValueError, AttributeError):
        return 0.0


class InterestCertificateParser:
    """
    Parse bank interest / TDS certificates.

    Handles two actual formats encountered:

    1. **Bank of Baroda "Interest cum TDS Certificate"** (combined NRE + NRO):
       Each account block ends with: ``Total  <gross>  <tds>  <interest_collected>``
       NRE accounts → TDS = 0 (exempt), NRO accounts → TDS > 0 (taxable).

    2. **HDFC Bank Interest Certificate** (separate NRE / NRO):
       NRO: ``Total  <principal>  <interest_accrued>  <tax_deducted>  <interest_amount>``
       NRE: ``Total  <principal>  <interest>  0.00``  (non-taxable, no TDS)
       NRE certs contain the word "NON-TAXABLE" or note about NRE/FCNR deposits.
    """

    @staticmethod
    def parse(text: str) -> DocumentParseResult:
        errors = []
        warnings = []
        data = {
            'bank': None,
            'period': None,
            'nre_total_interest': 0.0,
            'nre_total_tds': 0.0,
            'nro_total_interest': 0.0,
            'nro_total_tds': 0.0,
            'total_interest': 0.0,
            'total_tds': 0.0,
            'is_nre': False,
            'is_nro': False,
            'is_combined': False,
            'accounts': [],
        }

        if not text:
            errors.append("No text extracted from interest certificate")
            return DocumentParseResult(
                success=False,
                doc_type=DocumentType.INTEREST_CERTIFICATE.value,
                errors=errors,
                extracted_data=data,
            )

        text_upper = text.upper()

        # Detect bank — HDFC does not print bank name in PDF text (letterhead is image)
        # Use structural/content clues instead
        if 'BANK OF BARODA' in text_upper or 'INTEREST CUM TDS CERTIFICATE' in text_upper:
            data['bank'] = 'BOB'
        elif ('INTEREST CERTIFICATE' in text_upper and 'CUSTOMER ID:' in text_upper) or \
             'NRE / FCNR DEPOSITS' in text_upper or 'RAYSAN' in text_upper:
            data['bank'] = 'HDFC'

        # Detect period
        period_match = re.search(
            r'(\d{2}[/\-]\d{2}[/\-]\d{4})\s+(?:to|\-)\s+(\d{2}[/\-]\d{2}[/\-]\d{4})',
            text, re.IGNORECASE,
        )
        if period_match:
            data['period'] = f"{period_match.group(1)} to {period_match.group(2)}"

        # ── BOB "INTEREST CUM TDS CERTIFICATE" ──────────────────────────────
        if data['bank'] == 'BOB' or 'INTEREST CUM TDS' in text_upper:
            # Each account group ends with: "Total  gross  tds  interest_collected"
            total_matches = re.findall(
                r'^Total\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)',
                text, re.MULTILINE | re.IGNORECASE,
            )
            for match in total_matches:
                gross = _parse_amount(match[0])
                tds = _parse_amount(match[1])
                is_nre_acct = (tds == 0 and gross > 0)
                data['accounts'].append({'gross': gross, 'tds': tds, 'is_nre': is_nre_acct})
                if is_nre_acct:
                    data['nre_total_interest'] += gross
                    data['is_nre'] = True
                elif gross > 0 or tds > 0:
                    data['nro_total_interest'] += gross
                    data['nro_total_tds'] += tds
                    data['is_nro'] = True

            data['is_combined'] = data['is_nre'] and data['is_nro']
            data['total_interest'] = data['nre_total_interest'] + data['nro_total_interest']
            data['total_tds'] = data['nre_total_tds'] + data['nro_total_tds']

        # ── HDFC Interest Certificate ────────────────────────────────────────
        elif data['bank'] == 'HDFC':
            is_nre_cert = 'NON-TAXABLE' in text_upper

            # NRO cert (4 cols after Total): principal | interest_accrued | tax_deducted | interest
            total_4 = re.search(
                r'Total\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)',
                text,
            )
            # NRE cert (3 cols after Total): principal | interest | tds(0)
            total_3 = re.search(
                r'Total\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)',
                text,
            )

            if total_4:
                # HDFC NRO: principal | interest_accrued | additional_interest | tds_deducted
                # Columns 2+3 = total gross interest (confirmed: matches 26AS paid/credited amount)
                # Column 4 = TDS deducted (confirmed: matches 26AS TDS exactly)
                interest = _parse_amount(total_4.group(2)) + _parse_amount(total_4.group(3))
                tds = _parse_amount(total_4.group(4))
            elif total_3:
                # HDFC NRE: principal | interest | tds (always 0 for NRE)
                interest = _parse_amount(total_3.group(2))
                tds = _parse_amount(total_3.group(3))
            else:
                interest = 0.0
                tds = 0.0
                warnings.append("Could not find Total line in HDFC interest certificate")

            if is_nre_cert:
                data['nre_total_interest'] = interest
                data['nre_total_tds'] = tds
                data['is_nre'] = True
            else:
                data['nro_total_interest'] = interest
                data['nro_total_tds'] = tds
                data['is_nro'] = True

            data['total_interest'] = interest
            data['total_tds'] = tds

        # ── Generic fallback ────────────────────────────────────────────────
        else:
            total_match = re.search(
                r'Total[:\s]+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)',
                text, re.IGNORECASE,
            )
            if total_match:
                data['total_interest'] = _parse_amount(total_match.group(1))
                data['total_tds'] = _parse_amount(total_match.group(2))
            else:
                interest_m = re.search(
                    r'(?:gross\s+)?interest\s+(?:paid|earned|accrued|amount)?\s*[:\-]?\s*([\d,]+\.?\d*)',
                    text, re.IGNORECASE,
                )
                tds_m = re.search(
                    r'(?:tax\s+deducted|tds\s+collected|tds\s+amount)\s*[:\-]?\s*([\d,]+\.?\d*)',
                    text, re.IGNORECASE,
                )
                if interest_m:
                    data['total_interest'] = _parse_amount(interest_m.group(1))
                if tds_m:
                    data['total_tds'] = _parse_amount(tds_m.group(1))
            data['is_nro'] = data['total_tds'] > 0

        if data['total_interest'] == 0 and data['total_tds'] == 0:
            warnings.append("No interest or TDS amounts extracted. Manual entry required.")

        return DocumentParseResult(
            success=len(errors) == 0,
            doc_type=DocumentType.INTEREST_CERTIFICATE.value,
            extracted_data=data,
            errors=errors,
            warnings=warnings,
            raw_text=text[:800],
        )


class HomeLoanCertParser:
    """
    Parse HDFC NRI Home Loan Account Statement / Income Tax Certificate.

    The HDFC statement does NOT show interest vs principal split directly.
    This parser extracts loan parameters and CALCULATES the split via
    monthly-rest amortization — giving authoritative approximations that
    match the actual bank schedule (accurate to within ₹1 due to rounding).

    Actual format:
      LOAN AMOUNT : 13800000 ROI : 07.35 % CURRENT EMI: 128714
      Transactions: PRE EMI 5747, then E M I 128714 × N months
    """

    @staticmethod
    def parse(text: str) -> DocumentParseResult:
        errors = []
        warnings = []
        data = {
            'loan_account': None,
            'loan_type': None,
            'loan_amount': 0.0,
            'roi_percent': 0.0,
            'current_emi': 0.0,
            'disbursement_year': 0.0,
            'period': None,
            'pre_emi_amount': 0.0,
            'regular_emi_count': 0,
            'regular_emi_amount': 0.0,
            'total_paid': 0.0,
            'interest_paid': 0.0,
            'principal_paid': 0.0,
            'section_24b_deductible_self_occ': 0.0,
            'section_80c_deductible': 0.0,
            'calculation_method': 'monthly_rest_amortization',
        }

        if not text:
            errors.append("No text extracted from home loan certificate")
            return DocumentParseResult(
                success=False,
                doc_type=DocumentType.HOME_LOAN_CERT.value,
                errors=errors,
                extracted_data=data,
            )

        # Loan account number
        acc = re.search(r'Loan Account Number\s*:\s*(\d+)', text, re.IGNORECASE)
        if acc:
            data['loan_account'] = acc.group(1)

        # Loan type
        typ = re.search(r'TYPE\s*:\s*(.+)', text, re.IGNORECASE)
        if typ:
            data['loan_type'] = typ.group(1).strip()

        # Loan amount, ROI, EMI — all on the same line
        params = re.search(
            r'LOAN AMOUNT\s*:\s*([\d,]+).*?ROI\s*:\s*([\d.]+)\s*%.*?CURRENT EMI\s*:\s*([\d,]+)',
            text, re.IGNORECASE | re.DOTALL,
        )
        if params:
            data['loan_amount'] = _parse_amount(params.group(1))
            data['roi_percent'] = float(params.group(2))
            data['current_emi'] = _parse_amount(params.group(3))
        else:
            warnings.append("Could not extract loan amount / ROI / EMI from statement")

        # Disbursement for the year
        disb = re.search(r'DISBURSEMENT FOR THE YEAR\s*:\s*([\d,.]+)', text, re.IGNORECASE)
        if disb:
            data['disbursement_year'] = _parse_amount(disb.group(1))

        # Statement period
        period = re.search(
            r'STATEMENT OF ACCOUNT FOR THE PERIOD\s+([\w\-]+)\s+TO\s+([\w\-]+)',
            text, re.IGNORECASE,
        )
        if period:
            data['period'] = f"{period.group(1)} to {period.group(2)}"

        # Transaction extraction: PRE EMI and regular E M I lines
        pre_emi_matches = re.findall(r'PRE\s*EMI\s+([\d,]+)', text, re.IGNORECASE)
        for m in pre_emi_matches:
            data['pre_emi_amount'] += _parse_amount(m)

        # Regular EMI transactions (avoid matching the "CURRENT EMI:" line)
        emi_matches = re.findall(r'\bE M I\s+([\d,]+)', text)
        for m in emi_matches:
            amt = _parse_amount(m)
            if amt > 10000:  # Filter out small amounts that aren't full EMIs
                data['regular_emi_count'] += 1
                data['regular_emi_amount'] = amt

        data['total_paid'] = data['pre_emi_amount'] + (data['regular_emi_count'] * data['regular_emi_amount'])

        # ── Amortization calculation ───────────────────────────────────────
        if data['loan_amount'] > 0 and data['roi_percent'] > 0 and data['current_emi'] > 0 and data['regular_emi_count'] > 0:
            monthly_rate = data['roi_percent'] / 12 / 100
            outstanding = data['loan_amount']
            total_interest = data['pre_emi_amount']   # Pre-EMI is pure interest
            total_principal = 0.0

            for _ in range(data['regular_emi_count']):
                month_interest = round(outstanding * monthly_rate, 2)
                month_principal = data['current_emi'] - month_interest
                total_interest += month_interest
                total_principal += month_principal
                outstanding -= month_principal

            data['interest_paid'] = round(total_interest, 2)
            data['principal_paid'] = round(total_principal, 2)

            # Deduction limits (FY 2025-26 rules)
            data['section_24b_deductible_self_occ'] = min(data['interest_paid'], 200000.0)
            data['section_80c_deductible'] = min(data['principal_paid'], 150000.0)

            warnings.append(
                "Interest/principal calculated via monthly-rest amortization. "
                "For official figures, request HDFC's formal 'Interest & Principal Certificate'."
            )
        else:
            errors.append("Cannot calculate amortization — missing loan amount, ROI, EMI, or transaction count")

        return DocumentParseResult(
            success=len(errors) == 0,
            doc_type=DocumentType.HOME_LOAN_CERT.value,
            extracted_data=data,
            errors=errors,
            warnings=warnings,
            raw_text=text[:800],
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
            'interest_amount': 0,
            'tds_amount': 0,
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

        # Heuristic extraction for interest certificates / combined TDS statements
        amount_patterns = [
            (r'(?:interest(?:\s+paid)?(?:\s+amount)?|int(?:erest)?)\s*[:\-]?\s*(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d{1,2})?)', 'interest_amount'),
            (r'(?:tax\s+deducted(?:\s+at\s+source)?|tds(?:\s+amount)?)\s*[:\-]?\s*(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d{1,2})?)', 'tds_amount'),
        ]
        lowered = text.lower()
        for pattern, field in amount_patterns:
            match = re.search(pattern, lowered, flags=re.IGNORECASE)
            if match:
                try:
                    data[field] = float(match.group(1).replace(',', ''))
                except Exception:
                    pass

        # Fallback: sum all "TDS" numeric mentions if direct field not found
        if data['tds_amount'] == 0:
            tds_candidates = re.findall(r'tds[^0-9]{0,20}([\d,]+(?:\.\d{1,2})?)', lowered, flags=re.IGNORECASE)
            if tds_candidates:
                try:
                    data['tds_amount'] = sum(float(x.replace(',', '')) for x in tds_candidates)
                except Exception:
                    pass

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


class ZerodhaDividendParser:
    """
    Parse Zerodha Dividend report (XLSX format).

    Actual file layout (data starts row 16 after header rows):
      Col B: Symbol  Col C: ISIN  Col D: Ex-Date  Col E: Quantity
      Col F: Dividend Per Share  Col G: Net Dividend Amount

    Row 24: "Total Dividend Amount" + total in Col G.

    Note: Amounts represent GROSS dividends declared (qty × DPS).
    TDS deducted by individual companies appears in Form 26AS, not here.
    """

    @staticmethod
    def parse_xlsx(file_path: str) -> DocumentParseResult:
        errors = []
        warnings = []
        data = {
            'client_id': None,
            'pan': None,
            'period': None,
            'entries': [],
            'total_dividend': 0.0,
        }

        try:
            import openpyxl
        except ImportError:
            return DocumentParseResult(
                success=False,
                doc_type=DocumentType.DIV_REPORT.value,
                errors=["openpyxl not installed — cannot read XLSX files"],
            )

        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            ws = wb.active
        except Exception as e:
            return DocumentParseResult(
                success=False,
                doc_type=DocumentType.DIV_REPORT.value,
                errors=[f"Cannot open XLSX: {e}"],
            )

        for row in ws.iter_rows(values_only=True):
            if row[1] == 'Client ID' and row[2]:
                data['client_id'] = row[2]
            elif row[1] == 'PAN' and row[2]:
                data['pan'] = row[2]
            elif isinstance(row[1], str) and 'Equity Dividends from' in row[1]:
                data['period'] = row[1]
            elif row[1] == 'Symbol' and row[2] == 'ISIN':
                # Header row — next rows are data
                continue
            elif isinstance(row[1], str) and row[1] not in ('', None, 'Symbol') and \
                 isinstance(row[6], (int, float)) and row[1] != 'Total Dividend Amount':
                # Data row: Symbol, ISIN, Ex-Date, Qty, DPS, Net Amount
                net_div = float(row[6])
                data['entries'].append({
                    'symbol': row[1],
                    'isin': row[2],
                    'ex_date': str(row[3]) if row[3] else None,
                    'quantity': row[4],
                    'dps': float(row[5]) if row[5] else 0.0,
                    'gross_dividend': net_div,
                })
                data['total_dividend'] += net_div
            elif isinstance(row[1], str) and 'Total Dividend Amount' in row[1] and row[6]:
                data['total_dividend'] = float(row[6])

        if not data['entries']:
            warnings.append("No dividend entries found in Zerodha dividend report")

        return DocumentParseResult(
            success=len(errors) == 0,
            doc_type=DocumentType.DIV_REPORT.value,
            extracted_data=data,
            errors=errors,
            warnings=warnings,
        )


class ZerodhaTradebookParser:
    """
    Parse Zerodha Tradebook XLSX (equity trades).
    Determines if any sells occurred (for capital gains assessment).
    """

    @staticmethod
    def parse_xlsx(file_path: str) -> DocumentParseResult:
        errors = []
        warnings = []
        data = {
            'period': None,
            'buy_count': 0,
            'sell_count': 0,
            'has_sells': False,
            'sell_symbols': [],
        }

        try:
            import openpyxl
        except ImportError:
            return DocumentParseResult(
                success=False,
                doc_type=DocumentType.DIV_REPORT.value,
                errors=["openpyxl not installed"],
            )

        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            ws = wb.active
        except Exception as e:
            return DocumentParseResult(
                success=False,
                doc_type=DocumentType.DIV_REPORT.value,
                errors=[f"Cannot open XLSX: {e}"],
            )

        for row in ws.iter_rows(values_only=True):
            if isinstance(row[1], str) and 'Tradebook for Equity from' in row[1]:
                data['period'] = row[1]
            elif row[1] == 'Symbol' and row[7] == 'Trade Type':
                continue
            elif isinstance(row[7], str) and row[7].lower() == 'sell':
                data['sell_count'] += 1
                data['has_sells'] = True
                sym = row[1]
                if sym and sym not in data['sell_symbols']:
                    data['sell_symbols'].append(sym)
            elif isinstance(row[7], str) and row[7].lower() == 'buy':
                data['buy_count'] += 1

        if not data['has_sells']:
            warnings.append(
                f"No sell trades found in tradebook ({data['buy_count']} buy trades). "
                "Capital gains section not applicable."
            )

        return DocumentParseResult(
            success=True,
            doc_type="tradebook",
            extracted_data=data,
            errors=errors,
            warnings=warnings,
        )


class DocumentParserFactory:
    """Factory for document parsing"""

    _parsers = {
        DocumentType.AIS: AISParser,
        DocumentType.FORM_26AS: Form26ASParser,
        DocumentType.INTEREST_CERTIFICATE: InterestCertificateParser,
        DocumentType.HOME_LOAN_CERT: HomeLoanCertParser,
        DocumentType.BANK_STATEMENT: BankStatementParser,
        DocumentType.CAS: CASParser,
    }

    @staticmethod
    def parse_document(
        file_path: str,
        doc_type: DocumentType,
    ) -> DocumentParseResult:
        if not os.path.exists(file_path):
            return DocumentParseResult(
                success=False,
                doc_type=doc_type.value,
                errors=[f"File not found: {file_path}"],
            )

        ext = os.path.splitext(file_path)[1].lower()

        # Route XLSX files to dedicated Excel parsers
        if ext in ('.xlsx', '.xls', '.csv'):
            if doc_type == DocumentType.DIV_REPORT:
                return ZerodhaDividendParser.parse_xlsx(file_path)
            return DocumentParseResult(
                success=False,
                doc_type=doc_type.value,
                errors=[f"No Excel parser available for doc type: {doc_type.value}"],
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
        """Auto-detect document type from filename and parse."""
        filename = os.path.basename(file_path).lower()

        if 'dividend' in filename:
            return ZerodhaDividendParser.parse_xlsx(file_path)
        if 'tradebook' in filename:
            return ZerodhaTradebookParser.parse_xlsx(file_path)
        if '26as' in filename:
            doc_type = DocumentType.FORM_26AS
        elif 'ais' in filename:
            doc_type = DocumentType.AIS
        elif 'cas' in filename or 'mutual' in filename:
            doc_type = DocumentType.CAS
        elif 'bank' in filename or 'statement' in filename:
            doc_type = DocumentType.BANK_STATEMENT
        else:
            doc_type = DocumentType.BANK_STATEMENT

        return DocumentParserFactory.parse_document(file_path, doc_type)
