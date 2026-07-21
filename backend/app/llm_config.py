"""LLM Configuration and utilities for Claude API integration"""
import os
from typing import Optional

# Initialize Claude client
CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')
USE_LLM = CLAUDE_API_KEY is not None

if USE_LLM:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    except ImportError:
        print('Warning: anthropic package not installed. Install with: pip install anthropic')
        client = None
else:
    client = None


def call_claude(message: str, system_prompt: str = '', max_tokens: int = 1024) -> Optional[str]:
    """
    Call Claude API with the given message.
    Falls back to None if API is not configured.
    """
    if not client or not USE_LLM:
        return None
    
    try:
        response = client.messages.create(
            model='claude-3-5-sonnet-20241022',
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[
                {"role": "user", "content": message}
            ]
        )
        return response.content[0].text
    except Exception as e:
        print(f'Claude API error: {str(e)}')
        return None


def get_tax_guidance(question: str, context: dict = None) -> str:
    """Get AI-powered tax guidance using Claude"""
    
    system_prompt = """You are an expert Indian Income Tax consultant specializing in ITR filing for NRI and RNOR taxpayers. 
    You provide accurate, government-compliant tax advice based on the latest Income Tax Act, 1961 and circulars.
    Always cite relevant sections of the Income Tax Act and provide practical guidance.
    Be concise but comprehensive. Emphasize compliance and mention when official portal consultation is needed."""
    
    context_str = ''
    if context:
        context_str = f"""
Current tax case context:
- Assessment Year: {context.get('assessment_year', 'N/A')}
- Residency Status: {context.get('residential_status', 'N/A')}
- Income: ₹{context.get('gross_income', 0) / 100000:.2f}L
- TDS: ₹{context.get('tds', 0) / 100000:.2f}L
"""
    
    full_message = f"{context_str}\n\nUser Question: {question}"
    
    return call_claude(full_message, system_prompt=system_prompt, max_tokens=1500)


def get_deduction_recommendations(income_details: dict) -> str:
    """Get AI-powered deduction recommendations"""
    
    system_prompt = """You are an expert tax consultant specializing in Indian income tax deductions.
    Analyze the provided income details and suggest applicable deductions under Chapter VI-A of the Income Tax Act, 1961.
    Provide specific section numbers, limits, and eligibility criteria.
    Format your response as actionable recommendations with priority levels."""
    
    context = f"""Income Profile:
- Gross Income: ₹{income_details.get('gross_income', 0) / 100000:.2f}L
- Income Source: {income_details.get('income_sources', 'Not specified')}
- Age: {income_details.get('age', 'Unknown')}
- Has Children: {income_details.get('has_children', False)}
- Home Loan: {income_details.get('has_home_loan', False)}
- Health Insurance: {income_details.get('has_health_insurance', False)}

Suggest relevant deductions and explain how to optimize tax using these deductions."""
    
    return call_claude(context, system_prompt=system_prompt, max_tokens=2000)


def get_reconciliation_help(variances: dict) -> str:
    """Get AI help explaining reconciliation variances"""
    
    system_prompt = """You are an expert in resolving ITR reconciliation issues.
    Analyze the provided variances between source documents (AIS, 26AS) and ITR amounts.
    Explain possible reasons for discrepancies and suggest steps to resolve them.
    Reference relevant government rules and provide actionable solutions."""
    
    variance_text = f"""Reconciliation Variances Detected:
- Source vs AIS Variance: ₹{abs(variances.get('source_vs_ais', 0)).toLocaleString()}
- AIS vs ITR Variance: ₹{abs(variances.get('ais_vs_itr', 0)).toLocaleString()}
- Variance Status: {variances.get('status', 'flagged')}

Explain these variances and suggest resolution steps."""
    
    return call_claude(variance_text, system_prompt=system_prompt, max_tokens=1500)


def get_residency_analysis(residency_data: dict) -> str:
    """Get AI analysis of residency status implications"""
    
    system_prompt = """You are an expert on Indian residency rules and their tax implications.
    Analyze the provided residency data and explain:
    1. Current residency classification (NRI/RNOR/ROR)
    2. Income taxation rules applicable to this status
    3. Deductions available/restricted
    4. Documentation required
    5. Risk areas and compliance requirements
    
    Reference sections of the Income Tax Act, 1961."""
    
    residency_text = f"""Residency Information:
- Current Status: {residency_data.get('status', 'Unknown')}
- Days in India (Current FY): {residency_data.get('days_in_india_current', 'Unknown')}
- Days in India (Prior 4 FYs): {residency_data.get('days_in_india_prior', 'Unknown')}
- Income Sources: {residency_data.get('income_sources', 'Not specified')}

Provide detailed analysis of tax implications and requirements."""
    
    return call_claude(residency_text, system_prompt=system_prompt, max_tokens=2000)
