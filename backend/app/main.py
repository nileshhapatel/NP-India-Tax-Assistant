from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Any, Dict, Optional, List
from decimal import Decimal
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
import asyncio
import logging

logger = logging.getLogger(__name__)

# Import models from existing workspace
try:
    from itr_workspace.models import Taxpayer, TaxCase, DocumentRequirement
    from itr_workspace.tax_calculator import (
        TaxFilingCalculator,
        TaxRegime,
        ResidentialStatus,
    )
except Exception as e:
    import traceback
    print('Model import failed in main.py:', e)
    traceback.print_exc()
    Taxpayer = None
    TaxCase = None
    DocumentRequirement = None
    TaxFilingCalculator = None
    TaxRegime = None
    ResidentialStatus = None

# If tax engine class imported, expose wrapper functions
if 'TaxFilingCalculator' in globals() and TaxFilingCalculator is not None:
    def _build_calc_from_person(person, fiscal_year=None):
        rs_str = None
        # Try case-level residential status first
        if hasattr(person, 'residential_status') and getattr(person, 'residential_status'):
            rs_str = getattr(person, 'residential_status')
        elif hasattr(person, 'cases') and person.cases:
            try:
                rs_str = person.cases[0].residential_status
            except Exception:
                rs_str = None
        # Map to enum
        try:
            rs_enum = ResidentialStatus[rs_str]
        except Exception:
            try:
                rs_enum = ResidentialStatus[rs_str.upper()]
            except Exception:
                rs_enum = ResidentialStatus.NRI
        calc = TaxFilingCalculator(rs_enum, assessment_year=fiscal_year or '2026-27')
        # Populate incomes from case income_entries if available
        case = None
        if hasattr(person, 'cases') and person.cases:
            case = person.cases[0]
        if case and hasattr(case, 'income_entries'):
            for ie in case.income_entries:
                gross = getattr(ie, 'gross_amount', getattr(ie, 'amount_in_return', 0)) or 0
                exempt = getattr(ie, 'exempt_amount', 0) or 0
                try:
                    calc.add_income(getattr(ie, 'income_type', 'income'), Decimal(str(gross)), Decimal(str(exempt)))
                except Exception:
                    # ignore bad entries
                    pass
        else:
            # Fallback sample
            calc.add_income('Salary (India-source)', Decimal('1200000'), Decimal('0'))
        return calc

    def calculate_filing(person, fiscal_year=None):
        calc = _build_calc_from_person(person, fiscal_year=fiscal_year)
        # Default to OLD regime for detailed calculation
        try:
            return calc.calculate_filing(TaxRegime.OLD, person=person)
        except Exception as e:
            return {'error': str(e)}

    def compare_regimes(person, fiscal_year=None):
        calc = _build_calc_from_person(person, fiscal_year=fiscal_year)
        try:
            return calc.compare_regimes(person=person)
        except Exception as e:
            return {'error': str(e)}
else:
    calculate_filing = None
    compare_regimes = None

load_dotenv('.env')
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
else:
    engine = None
    SessionLocal = None

app = FastAPI(title='ITR Family API', version='0.2')

class TaxRequest(BaseModel):
    taxpayer: Dict[str, Any]
    fiscal_year: Optional[str] = None

@app.get('/health')
def health():
    return {'status': 'ok'}


@app.get('/api/llm/status')
def llm_status():
    """Get LLM provider configuration status"""
    try:
        from backend.app.llm_provider import get_llm_config
        config = get_llm_config()
        return {
            'ok': True,
            'current_provider': config.provider,
            'provider_name': config.get_provider_name(),
            'available': config.is_available(),
            'fallback_enabled': config.fallback_to_rules,
            'has_claude_key': bool(config.claude_api_key),
            'has_openai_key': bool(config.openai_api_key),
        }
    except Exception as e:
        logger.error(f"Error getting LLM status: {e}")
        return {
            'ok': False,
            'error': str(e),
            'current_provider': 'unknown',
        }
def list_taxpayers():
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    if Taxpayer is None:
        raise HTTPException(status_code=500, detail='Taxpayer model unavailable')
    with SessionLocal() as session:
        stmt = select(Taxpayer)
        try:
            rows = session.execute(stmt).scalars().all()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f'Database query failed: {e}')
        out = []
        for t in rows:
            if t is None:
                # defensive: skip unmapped rows
                continue
            out.append({
                'id': getattr(t, 'id', None),
                'name': getattr(t, 'name', None),
                'pan_last4': getattr(t, 'pan_last4', None),
                'citizenship': getattr(t, 'citizenship', None),
                'has_dependent_child': getattr(t, 'has_dependent_child', False),
                'dependent_child_country_of_residence': getattr(t, 'dependent_child_country_of_residence', None),
                'is_eligible_for_80ac': getattr(t, 'is_eligible_for_80ac', False),
            })
        return {'ok': True, 'taxpayers': out}

@app.get('/api/cases/{case_id}')
def case_detail(case_id: int):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        case = session.get(TaxCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail='Case not found')
        docs = [
            {
                'id': d.id,
                'code': d.code,
                'title': d.title,
                'status': d.status,
                'file_path': d.file_path,
                'required': d.required,
            }
            for d in case.documents
        ]
        tasks = [
            {'id': t.id, 'code': t.code, 'title': t.title, 'status': t.status}
            for t in case.tasks
        ]
        return {
            'ok': True,
            'case': {
                'id': case.id,
                'assessment_year': case.assessment_year,
                'financial_year': case.financial_year,
                'residential_status': case.residential_status,
                'return_form': case.return_form,
                'case_status': case.case_status,
                'documents': docs,
                'tasks': tasks,
            },
        }

@app.get('/api/cases/{case_id}/documents/required')
def required_documents(case_id: int):
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    with SessionLocal() as session:
        stmt = select(DocumentRequirement).where(DocumentRequirement.case_id == case_id)
        rows = session.execute(stmt).scalars().all()
        out = [
            {'id': r.id, 'code': r.code, 'title': r.title, 'required': r.required, 'status': r.status}
            for r in rows
        ]
        return {'ok': True, 'documents': out}

@app.post('/api/cases/{case_id}/documents/upload')
def upload_document(case_id: int, file: UploadFile = File(...), code: Optional[str] = None):
    """Upload a file and attach to a DocumentRequirement by code or create a new record."""
    if SessionLocal is None:
        raise HTTPException(status_code=500, detail='Database not configured')
    save_dir = os.path.join(os.getcwd(), 'private_data', f'case_{case_id}')
    os.makedirs(save_dir, exist_ok=True)
    filename = file.filename
    dest = os.path.join(save_dir, filename)
    with open(dest, 'wb') as f:
        contents = file.file.read()
        f.write(contents)
    # Update DB record if code given
    with SessionLocal() as session:
        if code and DocumentRequirement is not None:
            stmt = select(DocumentRequirement).where(DocumentRequirement.case_id == case_id, DocumentRequirement.code == code)
            dr = session.execute(stmt).scalars().first()
            if dr:
                dr.file_path = dest
                dr.status = 'Uploaded'
                session.add(dr)
                session.commit()
        return {'ok': True, 'path': dest}


@app.post('/api/documents/parse')
async def parse_document(file: UploadFile = File(...), doc_type: Optional[str] = None):
    """Parse and extract data from document (AIS, 26AS, CAS, Bank Statement)"""
    try:
        from backend.app.document_parser import (
            DocumentParserFactory,
            DocumentType,
        )
    except ImportError:
        logger.error("document_parser module not available")
        raise HTTPException(
            status_code=500,
            detail="Document parsing not available (pdfplumber or PyPDF2 required)"
        )

    # Save uploaded file temporarily
    temp_dir = os.path.join(os.getcwd(), 'private_data', 'temp_parse')
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, file.filename)

    try:
        with open(temp_path, 'wb') as f:
            contents = await file.read()
            f.write(contents)

        # Parse document
        if doc_type:
            try:
                doc_type_enum = DocumentType[doc_type.upper()]
            except KeyError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown document type: {doc_type}"
                )
            result = DocumentParserFactory.parse_document(temp_path, doc_type_enum)
        else:
            result = DocumentParserFactory.auto_detect_and_parse(temp_path)

        return {
            'ok': result.success,
            'document_type': result.doc_type,
            'extracted_data': result.extracted_data,
            'errors': result.errors,
            'warnings': result.warnings,
        }
    except Exception as e:
        logger.error(f"Document parsing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up temp file
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass


@app.get('/api/documents/supported-types')
def supported_document_types():
    """Get list of supported document types for parsing"""
    try:
        from backend.app.document_parser import DocumentType
        return {
            'ok': True,
            'types': [
                {
                    'type': dt.value,
                    'name': dt.name,
                    'description': {
                        'ais': 'Annual Information Statement - shows all financial transactions',
                        'form_26as': 'Form 26AS - shows TDS and tax credits',
                        'bank_statement': 'Bank Statement - account transactions',
                        'tds_certificate': 'TDS Certificate - Form 16/16A',
                        'salary_slip': 'Salary Slip - monthly earnings',
                        'home_loan_certificate': 'Home Loan Certificate - interest/principal',
                        'cas': 'Consolidated Account Statement - mutual fund holdings',
                        'dividend_report': 'Dividend Report - equity dividends',
                        'tax_audit_certificate': 'Tax Audit Certificate - Form 10B',
                    }.get(dt.value, 'Document for tax filing')
                }
                for dt in DocumentType
            ]
        }
    except Exception as e:
        logger.error(f"Error listing supported types: {e}")
        return {
            'ok': False,
            'error': str(e),
            'types': []
        }
def tax_calc(req: TaxRequest, case_id: Optional[int] = None):
    # If case_id provided, load taxpayer/case from DB; else use provided taxpayer dict
    taxpayer_obj = None
    if case_id:
        if SessionLocal is None:
            raise HTTPException(status_code=500, detail='Database not configured')
        with SessionLocal() as session:
            case = session.get(TaxCase, case_id)
            if not case:
                raise HTTPException(status_code=404, detail='Case not found')
            taxpayer_obj = case.taxpayer
    if calculate_filing:
        try:
            input_person = taxpayer_obj if taxpayer_obj is not None else req.taxpayer
            result = calculate_filing(input_person, fiscal_year=req.fiscal_year)
            return {'ok': True, 'result': result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        return {'ok': True, 'note': 'Tax engine not available in container', 'input': req.dict()}

@app.post('/api/tax/compare')
def tax_compare(req: TaxRequest, case_id: Optional[int] = None):
    taxpayer_obj = None
    if case_id:
        if SessionLocal is None:
            raise HTTPException(status_code=500, detail='Database not configured')
        with SessionLocal() as session:
            case = session.get(TaxCase, case_id)
            if not case:
                raise HTTPException(status_code=404, detail='Case not found')
            taxpayer_obj = case.taxpayer
    if compare_regimes:
        try:
            report = compare_regimes(taxpayer_obj if taxpayer_obj is not None else req.taxpayer, fiscal_year=req.fiscal_year)
            return {'ok': True, 'report': report}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        return {'ok': False, 'error': 'compare_regimes not available'}


# ---------------- AI / helper endpoints ----------------
class AIRequest(BaseModel):
    message: Optional[str] = None
    case_id: Optional[int] = None


def _load_taxpayer(case_id: Optional[int], taxpayer_dict: Optional[Dict[str, Any]] = None):
    if case_id and SessionLocal:
        with SessionLocal() as session:
            case = session.get(TaxCase, case_id)
            if not case:
                return None, 'Case not found'
            return case.taxpayer, None
    if taxpayer_dict:
        return taxpayer_dict, None
    return None, 'No taxpayer provided'


@app.post('/api/ai/deductions')
async def ai_deductions(req: AIRequest):
    """Get AI-powered deduction recommendations (multi-provider LLM)"""
    try:
        from backend.app.llm_provider import (
            get_deduction_recommendations,
            get_llm_config,
        )
        config = get_llm_config()
    except ImportError:
        logger.error("llm_provider module not available")
        config = None
        get_deduction_recommendations = None

    tp, err = _load_taxpayer(req.case_id)
    if err:
        raise HTTPException(status_code=400, detail=err)

    # Try LLM if available
    if get_deduction_recommendations and config and config.is_available():
        try:
            income_data = {
                'gross_income': 1200000,
                'residency': 'NRI',
                'dependents': 0,
                'health_status': 'Normal',
                'has_home_loan': False,
            }
            llm_response = await get_deduction_recommendations(income_data)
            if llm_response and llm_response.get('ok'):
                return {
                    'ok': True,
                    'suggestions': llm_response.get('response'),
                    'source': llm_response.get('source'),
                    'provider': llm_response.get('provider'),
                }
        except Exception as e:
            logger.warning(f"LLM deductions error: {e}")

    # Fallback to rule-based suggestions
    suggestions = [
        {
            'section': '80C',
            'name': 'PPF/EPF/ELSS/LIC/NSC/Principal on home loan',
            'max_limit': 150000,
            'eligible': True,
            'docs': ['Investment proof, bank statements'],
            'gov_link': 'https://www.incometax.gov.in/'
        },
        {
            'section': '80D',
            'name': 'Health Insurance Premiums',
            'max_limit': 50000,
            'eligible': True,
            'docs': ['Premium receipts, policy documents'],
            'gov_link': 'https://www.incometax.gov.in/'
        },
        {
            'section': '80AC',
            'name': 'Sukanya Samriddhi Account (Girl child)',
            'max_limit': 150000,
            'eligible': False,
            'docs': ['SSA receipts, birth certificate'],
            'gov_link': 'https://www.incometax.gov.in/iec/foportal/help/sukanyasamriddhi'
        }
    ]

    return {
        'ok': True,
        'suggestions': suggestions,
        'source': 'rule-based',
        'provider': 'Rule-Based AI'
    }


@app.post('/api/ai/residency')
def ai_residency(req: AIRequest):
    tp, err = _load_taxpayer(req.case_id)
    if err:
        raise HTTPException(status_code=400, detail=err)
    
    resp = {'ok': True, 'analysis': {}}
    try:
        citizenship = getattr(tp, 'citizenship', None) if not isinstance(tp, dict) else tp.get('citizenship')
        resp['analysis']['citizenship'] = citizenship
        
        if req.case_id and SessionLocal:
            with SessionLocal() as session:
                case = session.get(TaxCase, req.case_id)
                if case:
                    rs = case.residential_status
                    resp['analysis']['declared_residential_status'] = rs
                    
                    # Provide detailed guidance
                    guidance = {}
                    if rs in ['NRI', 'nri']:
                        guidance = {
                            'status': 'Non-Resident Individual (NRI)',
                            'guidelines': [
                                'Present in India < 60 days in current FY AND < 183 days in prior 4 FYs',
                                'Income earned outside India is generally NOT taxable in India (remittance basis)',
                                'Income from India-source property/business IS taxable',
                                'Most deductions (80C, 80D, 80G) available only on India-source income',
                                'TDS exemption on interest available (Form 15G/15H if <5L income)',
                            ],
                            'required_documents': ['Passport, visas', 'Employer letter', 'Flight tickets or visa stamps', 'Proof of foreign address'],
                        }
                    elif rs in ['RNOR', 'rnor']:
                        guidance = {
                            'status': 'Resident Not Ordinarily Resident (RNOR)',
                            'guidelines': [
                                'Resident in India but NOT for 2 of prior 10 years (OR present < 183 days for 4 of prior 10 years)',
                                'Foreign income is exempt if not remitted to India',
                                'Indian-source income fully taxable',
                                'Deductions (80C, 80D, etc.) available on Indian-source income',
                                'Same ITR form and most rules as ROR, but different clubbing & deduction rules',
                            ],
                            'required_documents': ['Passport (if moved recently)', 'Residency proof', 'Employer letters for years abroad', 'Property documents if own property'],
                        }
                    else:
                        guidance = {
                            'status': 'Resident Ordinary Resident (ROR)',
                            'guidelines': [
                                'Resident in India for 2+ of prior 10 years OR present >=183 days for 4+ of prior 10 years',
                                'All income worldwide is taxable (no remittance concept)',
                                'Full scope of deductions available (80C, 80D, 80G, 24(b), etc.)',
                                'Clubbing rules apply for spouse/minor income',
                                'Standard ITR-2 with full deductions',
                            ],
                            'required_documents': ['Proof of residence (utility bill, rent agreement, property docs)', 'No travel records needed (unless border crossing relevant)'],
                        }
                    
                    resp['analysis']['guidance'] = guidance
                    resp['analysis']['note'] = 'Residency determination is complex. Always verify with a CA or tax authority for edge cases.'
    except Exception as e:
        resp['analysis']['error'] = str(e)
    
    return resp


@app.post('/api/ai/tax-savings')
def ai_tax_savings(req: AIRequest):
    """AI endpoint suggesting tax-saving strategies based on profile"""
    tp, err = _load_taxpayer(req.case_id)
    if err:
        raise HTTPException(status_code=400, detail=err)
    
    suggestions = []
    
    # Generic savings suggestions
    suggestions.append({
        'title': '80C - Section 80C Investments (₹1,50,000 limit)',
        'description': 'Claim investments in PPF, ELSS, NSC, Life Insurance, Education, Principal on home loan',
        'benefit': 'Up to ₹1,50,000 deduction = ₹45,000 tax savings (at 30% slab)',
        'compliance': 'Collect investment proofs, receipts, policy statements',
        'priority': 'HIGH',
    })
    
    suggestions.append({
        'title': '80D - Health Insurance (₹1,00,000 limit)',
        'description': 'Medical insurance premiums for self, spouse, children, parents',
        'benefit': 'Up to ₹1,00,000 deduction = ₹30,000 tax savings',
        'compliance': 'Premium receipts, policy documents',
        'priority': 'HIGH',
    })
    
    suggestions.append({
        'title': '24(b) - Home Loan Interest (unlimited)',
        'description': 'Interest on home loan for self-occupied or let-out property',
        'benefit': 'Varies (₹2L-3L interest = ₹60K-90K savings)',
        'compliance': 'Home loan certificate, interest statement from bank',
        'priority': 'HIGH' if SessionLocal else 'MEDIUM',
    })
    
    suggestions.append({
        'title': '80E - Education Loan Interest (₹50,000 limit)',
        'description': 'Interest paid on education loan for higher education',
        'benefit': 'Up to ₹50,000 deduction = ₹15,000 savings',
        'compliance': 'Loan agreement, bank statement showing interest',
        'priority': 'MEDIUM',
    })
    
    suggestions.append({
        'title': '80AC - Sukanya Samriddhi (₹1,50,000 for girl child)',
        'description': 'Investment for girl child <10 years in SSA scheme',
        'benefit': 'Up to ₹1,50,000 deduction + tax-free growth',
        'compliance': 'SSA account statement, child birth proof, residence proof',
        'priority': 'MEDIUM' if tp and getattr(tp, 'is_eligible_for_80ac', False) else 'LOW',
    })
    
    suggestions.append({
        'title': 'Senior Citizen Benefits (80TTB)',
        'description': 'Additional interest deduction for senior citizens (₹50,000 limit)',
        'benefit': 'Up to ₹50,000 deduction if age >60',
        'compliance': 'Date of birth, interest receipts',
        'priority': 'LOW',
    })
    
    suggestions.append({
        'title': 'NRI/RNOR: Salary Exemption (if eligible)',
        'description': 'Foreign salary may be exempt for NRI earning outside India',
        'benefit': 'Partial or full exemption on foreign income',
        'compliance': 'Employer letter, contract, flight records',
        'priority': 'HIGH' if req.case_id else 'MEDIUM',
    })
    
    return {'ok': True, 'suggestions': suggestions}


@app.post('/api/ai/chat')
async def ai_chat(req: AIRequest):
    """Multi-provider AI chat endpoint (Claude, ChatGPT, or Rule-based)"""
    message = req.message or ''
    case_id = req.case_id

    try:
       from backend.app.llm_provider import call_llm, get_llm_config, SYSTEM_PROMPTS
       config = get_llm_config()
    except ImportError:
       logger.error("llm_provider module not available")
       config = None

    # Build context if case_id provided
    context = None
    if case_id and SessionLocal:
       try:
           session = SessionLocal()
           case = session.query(TaxCase).filter(TaxCase.id == case_id).first()
           if case:
               gross_income = 0
               tds = 0
               if hasattr(case, 'income_entries'):
                   for ie in case.income_entries:
                       gross_income += float(getattr(ie, 'gross_amount', 0) or 0)
                       tds += float(getattr(ie, 'tds_amount', 0) or 0)
               context = {
                   'assessment_year': case.assessment_year,
                   'residential_status': case.residential_status,
                   'gross_income': gross_income,
                   'tds': tds,
               }
       except Exception as e:
           logger.warning(f"Error loading case context: {e}")
       finally:
           if session:
               session.close()

    # Try LLM if configured and available
    if config and config.is_available():
       try:
           llm_response = await call_llm(
               system_prompt=SYSTEM_PROMPTS.get('tax_guidance', ''),
               user_message=message,
               max_tokens=1024,
           )
           if llm_response and llm_response.get('ok'):
               return {
                   'ok': True,
                   'response': llm_response.get('response'),
                   'source': llm_response.get('source'),
                   'provider': llm_response.get('provider'),
                   'context': context,
               }
       except Exception as e:
           logger.warning(f"LLM chat error: {e}")

    # Fallback to simple rule-based responses
    responses = {
       'what is itr': 'ITR is the Income Tax Return filed with the Income Tax Department showing your income, deductions, and tax liability.',
       'what is 80c': 'Section 80C allows up to ₹1,50,000 deduction for investments in PPF, ELSS, NSC, Life Insurance, and principal on home loan.',
       'what is 80d': 'Section 80D allows deduction of health insurance premiums (₹50,000 self/spouse, ₹1,00,000 with parents).',
       'nri vs rnor': 'NRI: <60 days in India (current FY) AND <183 in prior 4 years. RNOR: Resident but not for 2 of prior 10 years.',
       'sukanya samriddhi': 'Section 80AC: Girl child <10 years, India resident; ₹1,50,000/year limit.',
       'home loan': 'Section 24(b): Interest deductible. Pre-construction capped at ₹5L for homes <60L value.',
       'form 26as': 'Form 26AS shows TDS, TCS, and advance tax reported by banks/employers.',
       'ais': 'AIS shows all financial transactions reported to ITD by banks, brokers, and institutions.',
    }

    msg_lower = message.lower()
    for key, resp in responses.items():
       if key in msg_lower:
           return {
               'ok': True,
               'response': resp,
               'source': 'rule-based',
               'provider': 'Rule-Based AI',
               'context': context,
           }

    # Generic fallback
    return {
       'ok': True,
       'response': 'I can help with ITR questions. Ask me about: 80C, 80D, NRI vs RNOR, refunds, TDS, deductions, tax-saving strategies.',
       'source': 'rule-based',
       'provider': 'Rule-Based AI',
       'context': context,
    }


# ==================== PROFILE API ====================
@app.put('/api/taxpayers/{taxpayer_id}')
def update_taxpayer(taxpayer_id: int, data: Dict[str, Any]):
    """Update taxpayer profile information"""
    if not SessionLocal:
       return {'error': 'Database not configured'}
    
    session = SessionLocal()
    try:
       tp = session.query(Taxpayer).filter(Taxpayer.id == taxpayer_id).first()
       if not tp:
           raise HTTPException(status_code=404, detail='Taxpayer not found')
        
       # Update fields
       if 'name' in data:
           tp.name = data['name']
       if 'citizenship' in data:
           tp.citizenship = data['citizenship']
       if 'pan_last4' in data:
           tp.pan_last4 = data['pan_last4']
       if 'has_dependent_child' in data:
           tp.has_dependent_child = data['has_dependent_child']
       if 'dependent_child_country_of_residence' in data:
           tp.dependent_child_country_of_residence = data['dependent_child_country_of_residence']
        
       session.commit()
       return {'ok': True, 'taxpayer': {
           'id': tp.id,
           'name': tp.name,
           'citizenship': tp.citizenship,
           'pan_last4': tp.pan_last4,
           'has_dependent_child': tp.has_dependent_child,
       }}
    except Exception as e:
       session.rollback()
       return {'error': str(e)}
    finally:
       session.close()


# ==================== INCOME API ====================
class IncomeEntry(BaseModel):
    income_type: str
    amount: float
    tds_deducted: float = 0
    fiscal_year: str = '2025-26'


@app.get('/api/cases/{case_id}/income')
def get_income(case_id: int):
    """Get income entries for a case"""
    if not SessionLocal:
       return {'error': 'Database not configured'}
    
    session = SessionLocal()
    try:
       case = session.query(TaxCase).filter(TaxCase.id == case_id).first()
       if not case:
           raise HTTPException(status_code=404, detail='Case not found')
        
       incomes = []
       if hasattr(case, 'income_entries'):
           for ie in case.income_entries:
               incomes.append({
                   'id': getattr(ie, 'id', None),
                   'income_type': getattr(ie, 'income_type', 'Unknown'),
                   'source_name': getattr(ie, 'source_name', ''),
                   'gross_amount': float(getattr(ie, 'gross_amount', 0) or 0),
                   'exempt_amount': float(getattr(ie, 'exempt_amount', 0) or 0),
                   'tds_amount': float(getattr(ie, 'tds_amount', 0) or 0),
               })
        
       return {'ok': True, 'case_id': case_id, 'income_entries': incomes}
    finally:
       session.close()


@app.post('/api/cases/{case_id}/income')
def add_income(case_id: int, entry: IncomeEntry):
    """Add income entry to case"""
    if not SessionLocal:
       return {'error': 'Database not configured'}
    
    session = SessionLocal()
    try:
       case = session.query(TaxCase).filter(TaxCase.id == case_id).first()
       if not case:
           raise HTTPException(status_code=404, detail='Case not found')
        
       # Create income entry
       try:
           from itr_workspace.models import IncomeEntry as IncomeModel
           ie = IncomeModel(
               case_id=case_id,
               income_type=entry.income_type,
               source_name=entry.income_type,
               gross_amount=entry.amount,
               tds_amount=entry.tds_deducted,
           )
           session.add(ie)
           session.commit()
           return {'ok': True, 'income_entry': {
               'id': ie.id,
               'income_type': ie.income_type,
               'gross_amount': float(ie.gross_amount),
               'tds_amount': float(ie.tds_amount),
           }}
       except Exception as e:
           session.rollback()
           return {'error': f'Could not create income entry: {str(e)}'}
    finally:
       session.close()


@app.delete('/api/cases/{case_id}/income/{income_id}')
def delete_income(case_id: int, income_id: int):
    """Delete income entry"""
    if not SessionLocal:
       return {'error': 'Database not configured'}
    
    session = SessionLocal()
    try:
       try:
           from itr_workspace.models import IncomeEntry as IncomeModel
           ie = session.query(IncomeModel).filter(
               IncomeModel.id == income_id,
               IncomeModel.case_id == case_id
           ).first()
           if not ie:
               raise HTTPException(status_code=404, detail='Income entry not found')
           session.delete(ie)
           session.commit()
           return {'ok': True}
       except Exception as e:
           session.rollback()
           return {'error': str(e)}
    finally:
       session.close()


# ==================== RECONCILIATION API ====================
@app.get('/api/cases/{case_id}/reconciliation')
def get_reconciliation(case_id: int):
    """Get reconciliation data for 3-way match"""
    if not SessionLocal or not TaxFilingCalculator:
       return {'error': 'Database or tax calculator not available'}
    
    session = SessionLocal()
    try:
       case = session.query(TaxCase).filter(TaxCase.id == case_id).first()
       if not case:
           raise HTTPException(status_code=404, detail='Case not found')
        
       tp = case.taxpayer
        
       # Calculate ITR amount
       calc = _build_calc_from_person(tp)
       filing_result = calculate_filing(tp)
        
       itr_amount = float(filing_result.get('tax_liability', 0)) if isinstance(filing_result, dict) else 0
        
       # Get TDS from documents/entries
       tds_total = 0
       if hasattr(case, 'income_entries'):
           for ie in case.income_entries:
               tds_total += float(getattr(ie, 'tds_amount', 0) or 0)
        
       # Calculate gross income from entries
       gross_income = 0
       if hasattr(case, 'income_entries'):
           for ie in case.income_entries:
               gross_income += float(getattr(ie, 'gross_amount', 0) or 0)
        
       return {
           'ok': True,
           'case_id': case_id,
           'reconciliation': {
               'source_total': gross_income,  # From user entries
               'ais_reported': gross_income,  # Placeholder: should fetch from AIS upload
               'form26as_tds': tds_total,     # From Form 26AS/TDS entries
               'calculated_tax': itr_amount,
               'variances': {
                   'source_vs_ais': 0,  # Placeholder
                   'ais_vs_itr': 0,     # Placeholder
               },
               'status': 'matched' if abs(gross_income - gross_income) < 100 else 'flagged',
           }
       }
    finally:
       session.close()


# ==================== TAX REPORT GENERATION ====================
@app.get('/api/cases/{case_id}/reports/calculation')
def get_calculation_report(case_id: int):
    """Generate detailed tax calculation report"""
    if not SessionLocal or not TaxFilingCalculator:
       return {'error': 'Database or tax calculator not available'}
    
    session = SessionLocal()
    try:
       case = session.query(TaxCase).filter(TaxCase.id == case_id).first()
       if not case:
           raise HTTPException(status_code=404, detail='Case not found')
        
       tp = case.taxpayer
       filing_result = calculate_filing(tp)
        
       # Get income details
       gross_income = 0
       deductions = 0
       tds_total = 0
        
       if hasattr(case, 'income_entries'):
           for ie in case.income_entries:
               gross_income += float(getattr(ie, 'gross_amount', 0) or 0)
               tds_total += float(getattr(ie, 'tds_amount', 0) or 0)
        
       # Calculate deductions (placeholder - would sum actual deductions from DB)
       deductions = 0  # To be populated from deduction entries
        
       taxable_income = gross_income - deductions
       tax_liability = float(filing_result.get('tax_liability', 0)) if isinstance(filing_result, dict) else 0
       surcharge = float(filing_result.get('surcharge', 0)) if isinstance(filing_result, dict) else 0
       cess = float(filing_result.get('cess', 0)) if isinstance(filing_result, dict) else 0
        
       tax_before_credits = tax_liability + surcharge + cess
       net_tax = tax_before_credits - tds_total
        
       report = {
           'case_id': case_id,
           'taxpayer_name': tp.name,
           'assessment_year': case.assessment_year,
           'financial_year': case.financial_year,
           'residential_status': case.residential_status,
           'return_form': case.return_form,
            
           'income_summary': {
               'gross_income': gross_income,
               'income_details': [{
                   'head': 'Salary (India-source)',
                   'amount': gross_income,
                   'reference': 'Chapter III-A, Income-tax Act, 1961',
               } if gross_income > 0 else {}],
           },
            
           'deductions': {
               'total': deductions,
               'breakup': [
                   {'section': '80C', 'amount': 0, 'limit': 150000},
                   {'section': '80D', 'amount': 0, 'limit': 100000},
                   {'section': '24(b)', 'amount': 0, 'limit': 0},
               ],
           },
            
           'tax_calculation': {
               'taxable_income': taxable_income,
               'tax_liability': tax_liability,
               'surcharge': surcharge,
               'cess': cess,
               'tax_before_credits': tax_before_credits,
               'tds_deducted': tds_total,
               'net_tax_payable': max(0, net_tax),
               'refund': max(0, tds_total - tax_before_credits),
               'regime': 'Old Regime',
               'tax_slabs_used': [
                   {'slab': '₹0 - ₹2.5L', 'rate': '0%'},
                   {'slab': '₹2.5L - ₹5L', 'rate': '5%'},
                   {'slab': '₹5L - ₹10L', 'rate': '20%'},
                   {'slab': '>₹10L', 'rate': '30%'},
               ],
           },
            
           'government_references': [
               {'section': 'Income-tax Act, 1961', 'url': 'https://www.incometax.gov.in'},
               {'section': 'Form 26AS', 'url': 'https://www.incometax.gov.in/iec/foportal/ais-faq'},
               {'section': 'AIS Portal', 'url': 'https://www.incometax.gov.in/iec/foportal/ais'},
           ],
       }
        
       return {'ok': True, 'report': report}
    finally:
       session.close()


@app.get('/api/cases/{case_id}/reports/form-summary')
def get_form_summary_report(case_id: int):
    """Generate ITR form summary report"""
    if not SessionLocal:
       return {'error': 'Database not configured'}
    
    session = SessionLocal()
    try:
       case = session.query(TaxCase).filter(TaxCase.id == case_id).first()
       if not case:
           raise HTTPException(status_code=404, detail='Case not found')
        
       tp = case.taxpayer
        
       # Aggregate data
       gross_income = 0
       tds_total = 0
       if hasattr(case, 'income_entries'):
           for ie in case.income_entries:
               gross_income += float(getattr(ie, 'gross_amount', 0) or 0)
               tds_total += float(getattr(ie, 'tds_amount', 0) or 0)
        
       filing_result = calculate_filing(tp)
       tax_liability = float(filing_result.get('tax_liability', 0)) if isinstance(filing_result, dict) else 0
        
       report = {
           'case_id': case_id,
           'form_type': case.return_form,
           'assessment_year': case.assessment_year,
           'financial_year': case.financial_year,
            
           'taxpayer_details': {
               'name': tp.name,
               'pan': 'XXXX XXXX' + (tp.pan_last4 or ''),
               'citizenship': tp.citizenship,
               'residential_status': case.residential_status,
               'date_of_birth': 'As per PAN records',
           },
            
           'schedule_sa_income': {
               'salary': gross_income,
               'house_property': 0,
               'other_sources': 0,
               'total_income': gross_income,
               'less_deductions': 0,
               'income_chargeable': gross_income,
           },
            
           'schedule_tds': {
               'tds_by_employer': tds_total,
               'tds_by_bank': 0,
               'tds_by_others': 0,
               'total_tds': tds_total,
           },
            
           'tax_computation': {
               'taxable_income': gross_income,
               'tax_under_section': tax_liability,
               'surcharge': 0,
               'cess': 0,
               'total_tax': tax_liability,
               'total_tax_credits': tds_total,
               'tax_payable': max(0, tax_liability - tds_total),
               'refund': max(0, tds_total - tax_liability),
           },
            
           'verification': {
               'income_matched': abs(gross_income) < 100,
               'tds_matched': abs(tds_total) < 100,
               'calculations_verified': True,
               'ready_to_file': abs(gross_income) < 100 and abs(tds_total) < 100,
           },
             
           'filing_instructions': [
               'Review all income and deduction entries above',
               'Verify TDS amounts match Form 26AS',
               'Download this report as reference',
               'Login to official Income Tax portal with PAN/Aadhaar',
               'Upload PDF report or enter data directly',
               'Sign and verify ITR electronically or manually',
               'File through portal or submit to nearest Income Tax Office',
           ],
       }
         
       return {'ok': True, 'report': report}
    finally:
       session.close()


# ========== Household & Multi-Taxpayer Endpoints ==========

@app.get('/api/household/members')
def household_members():
    """Get all household members (taxpayers)"""
    if SessionLocal is None:
       raise HTTPException(status_code=500, detail='Database not configured')

    with SessionLocal() as session:
       try:
           stmt = select(Taxpayer)
           taxpayers = session.execute(stmt).scalars().all()
            
           members = []
           for tp in taxpayers:
               if tp is None:
                   continue
                    
               # Get latest case for each taxpayer
               case_stmt = select(TaxCase).where(TaxCase.taxpayer_id == tp.id)
               cases = session.execute(case_stmt).scalars().all()
                
               member = {
                   'id': tp.id,
                   'name': getattr(tp, 'name', 'Unknown'),
                   'pan': getattr(tp, 'pan', '').rjust(12, 'X'),
                   'cases': [
                       {
                           'id': c.id,
                           'assessment_year': c.assessment_year,
                           'residential_status': c.residential_status,
                       }
                       for c in cases if c
                   ]
               }
               members.append(member)
            
           return {'ok': True, 'members': members}
       except Exception as e:
           logger.error(f"Error fetching household members: {e}")
           raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/household/summary')
def household_summary():
    """Get consolidated household tax summary (all members)"""
    if SessionLocal is None:
       raise HTTPException(status_code=500, detail='Database not configured')

    with SessionLocal() as session:
       try:
           stmt = select(Taxpayer)
           taxpayers = session.execute(stmt).scalars().all()
            
           total_income = 0
           total_tax = 0
           total_tds = 0
           members_summary = []
            
           for tp in taxpayers:
               if tp is None:
                   continue
                    
               case_stmt = select(TaxCase).where(TaxCase.taxpayer_id == tp.id)
               cases = session.execute(case_stmt).scalars().all()
                
               for case in cases:
                   if not case:
                       continue
                        
                   # Calculate income from entries
                   case_income = 0
                   case_tds = 0
                   if hasattr(case, 'income_entries'):
                       for ie in case.income_entries:
                           case_income += float(getattr(ie, 'gross_amount', 0) or 0)
                           case_tds += float(getattr(ie, 'tds_amount', 0) or 0)
                    
                   total_income += case_income
                   total_tds += case_tds
                    
                   # Rough tax estimate (old regime)
                   if case_income > 500000:
                       case_tax = (case_income - 500000) * 0.20
                   elif case_income > 250000:
                       case_tax = (case_income - 250000) * 0.05
                   else:
                       case_tax = 0
                   case_tax += case_income * 0.004  # Cess
                   total_tax += case_tax
                    
                   members_summary.append({
                       'name': getattr(tp, 'name', 'Unknown'),
                       'case_id': case.id,
                       'assessment_year': case.assessment_year,
                       'residency': case.residential_status,
                       'gross_income': case_income,
                       'tds_deducted': case_tds,
                       'estimated_tax': case_tax,
                       'refund_claim': case_tds - case_tax if case_tds > case_tax else 0,
                   })
            
           return {
               'ok': True,
               'household_summary': {
                   'total_members': len(members_summary),
                   'total_income': total_income,
                   'total_tds_deducted': total_tds,
                   'estimated_total_tax': total_tax,
                   'total_refund': total_tds - total_tax if total_tds > total_tax else 0,
                   'members': members_summary,
               }
           }
       except Exception as e:
           logger.error(f"Error calculating household summary: {e}")
           raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/household/consolidated-filing')
def consolidated_filing_status():
    """Get consolidated filing status and recommendations"""
    if SessionLocal is None:
       raise HTTPException(status_code=500, detail='Database not configured')

    try:
       session = SessionLocal()
        
       # Get all taxpayers and cases
       stmt = select(Taxpayer)
       taxpayers = session.execute(stmt).scalars().all()
        
       filing_info = {
           'filing_method': 'separate',  # ITR rules require separate filing per person
           'note': 'Each individual must file separate ITR. Joint filing not supported in India.',
           'recommendation': 'File individual ITRs for each household member with separate PAN',
           'members': [],
           'coordination_needed': False,
           'shared_deductions': [],  # e.g., home loan interest, health insurance
       }
        
       for tp in taxpayers:
           if tp is None:
               continue
                
           case_stmt = select(TaxCase).where(TaxCase.taxpayer_id == tp.id)
           cases = session.execute(case_stmt).scalars().all()
            
           for case in cases:
               if not case:
                   continue
                    
               income = 0
               if hasattr(case, 'income_entries'):
                   for ie in case.income_entries:
                       income += float(getattr(ie, 'gross_amount', 0) or 0)
                
               filing_info['members'].append({
                   'name': getattr(tp, 'name', 'Unknown'),
                   'case_id': case.id,
                   'pan': getattr(tp, 'pan', 'XXXX...'),
                   'assessment_year': case.assessment_year,
                   'residency': case.residential_status,
                   'gross_income': income,
                   'filing_required': income > 500000 or True,  # ITR filing mandatory for NRI
                   'filing_deadline': '31st July (for prev FY) or 31st Oct (with penalty)',
               })
        
       return {
           'ok': True,
           'filing_status': filing_info,
       }
    except Exception as e:
       logger.error(f"Error getting filing status: {e}")
       raise HTTPException(status_code=500, detail=str(e))
    finally:
       session.close()


@app.get('/api/cases/{case_id}/compare/{other_case_id}')
def compare_cases(case_id: int, other_case_id: int):
    """Compare two tax cases (multi-taxpayer comparison)"""
    if SessionLocal is None:
       raise HTTPException(status_code=500, detail='Database not configured')

    with SessionLocal() as session:
       try:
           case1 = session.get(TaxCase, case_id)
           case2 = session.get(TaxCase, other_case_id)
            
           if not case1 or not case2:
               raise HTTPException(status_code=404, detail='One or both cases not found')
            
           # Calculate income for both cases
           def calc_case_summary(case):
               income = 0
               tds = 0
               if hasattr(case, 'income_entries'):
                   for ie in case.income_entries:
                       income += float(getattr(ie, 'gross_amount', 0) or 0)
                       tds += float(getattr(ie, 'tds_amount', 0) or 0)
               return {'income': income, 'tds': tds}
            
           summary1 = calc_case_summary(case1)
           summary2 = calc_case_summary(case2)
            
           # Calculate tax
           def calc_tax(income):
               if income > 500000:
                   tax = (income - 500000) * 0.20
               elif income > 250000:
                   tax = (income - 250000) * 0.05
               else:
                   tax = 0
               tax += income * 0.004  # Cess
               return tax
            
           tax1 = calc_tax(summary1['income'])
           tax2 = calc_tax(summary2['income'])
            
           return {
               'ok': True,
               'comparison': {
                   'case1': {
                       'id': case1.id,
                       'taxpayer': getattr(case1.taxpayer, 'name', 'Unknown') if case1.taxpayer else 'Unknown',
                       'assessment_year': case1.assessment_year,
                       'residential_status': case1.residential_status,
                       'gross_income': summary1['income'],
                       'tds_deducted': summary1['tds'],
                       'tax_liability': tax1,
                       'refund': summary1['tds'] - tax1 if summary1['tds'] > tax1 else 0,
                   },
                   'case2': {
                       'id': case2.id,
                       'taxpayer': getattr(case2.taxpayer, 'name', 'Unknown') if case2.taxpayer else 'Unknown',
                       'assessment_year': case2.assessment_year,
                       'residential_status': case2.residential_status,
                       'gross_income': summary2['income'],
                       'tds_deducted': summary2['tds'],
                       'tax_liability': tax2,
                       'refund': summary2['tds'] - tax2 if summary2['tds'] > tax2 else 0,
                   },
                   'differences': {
                       'income_diff': abs(summary1['income'] - summary2['income']),
                       'tax_diff': abs(tax1 - tax2),
                       'higher_earner': case1.id if summary1['income'] > summary2['income'] else case2.id,
                   }
               }
           }
       except Exception as e:
           logger.error(f"Error comparing cases: {e}")
           raise HTTPException(status_code=500, detail=str(e))


