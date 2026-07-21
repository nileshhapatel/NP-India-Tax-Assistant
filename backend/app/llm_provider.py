"""
Multi-Provider LLM Abstraction Layer
Supports: Claude (Anthropic), ChatGPT (OpenAI), Rule-based fallback
"""
import os
import json
import logging
from typing import Optional, Dict, List, Any
from enum import Enum
from functools import lru_cache

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers"""
    CLAUDE = "claude"
    CHATGPT = "chatgpt"
    RULE_BASED = "rule_based"


class LLMConfig:
    """Multi-provider LLM configuration"""

    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "claude").lower()
        self.claude_api_key = os.getenv("CLAUDE_API_KEY", "")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.fallback_to_rules = os.getenv("LLM_FALLBACK_TO_RULES", "true").lower() == "true"

        # Validate provider
        if self.provider not in [p.value for p in LLMProvider]:
            logger.warning(f"Unknown provider {self.provider}, defaulting to claude")
            self.provider = "claude"

        # Validate API keys
        if self.provider == "claude" and not self.claude_api_key:
            logger.warning("CLAUDE_API_KEY not configured, will use rule-based AI")
            if self.fallback_to_rules:
                self.provider = "rule_based"
        elif self.provider == "chatgpt" and not self.openai_api_key:
            logger.warning("OPENAI_API_KEY not configured, will use rule-based AI")
            if self.fallback_to_rules:
                self.provider = "rule_based"

    def is_available(self) -> bool:
        """Check if configured provider has required credentials"""
        if self.provider == "claude":
            return bool(self.claude_api_key)
        elif self.provider == "chatgpt":
            return bool(self.openai_api_key)
        return True  # rule_based always available

    def get_provider_name(self) -> str:
        """Get human-readable provider name"""
        return {
            "claude": "Claude (Anthropic)",
            "chatgpt": "ChatGPT (OpenAI)",
            "rule_based": "Rule-Based AI"
        }.get(self.provider, "Unknown")


class ClaudeProvider:
    """Claude (Anthropic) LLM Provider"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.model = "claude-3-5-sonnet-20241022"
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            logger.error("anthropic package not installed")
            self.client = None

    def call(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 1024,
    ) -> Optional[str]:
        """Call Claude API"""
        if not self.client:
            return None

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            return message.content[0].text if message.content else None
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return None


class ChatGPTProvider:
    """ChatGPT (OpenAI) LLM Provider"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.model = "gpt-4o-mini"
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)
        except ImportError:
            logger.error("openai package not installed")
            self.client = None

    def call(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 1024,
    ) -> Optional[str]:
        """Call OpenAI ChatGPT API"""
        if not self.client:
            return None

        try:
            message = self.client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )
            return message.choices[0].message.content if message.choices else None
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return None


class RuleBasedProvider:
    """Rule-based AI fallback (no external API calls)"""

    def __init__(self):
        self.rules = self._load_rules()

    def _load_rules(self) -> Dict[str, List[str]]:
        """Load tax rules database"""
        return {
            "80C": {
                "description": "Section 80C - Deduction for investments and tuition",
                "limit": 150000,
                "items": [
                    "PPF deposits up to ₹150,000",
                    "ELSS mutual funds",
                    "NSC deposits",
                    "Principal repayment on home loan",
                    "Life insurance premium",
                    "Tuition fees for children",
                ],
            },
            "80D": {
                "description": "Section 80D - Deduction for health insurance premium",
                "limit": 100000,
                "items": [
                    "Self & spouse health insurance: ₹25,000",
                    "Parents health insurance: ₹25,000 (₹30,000 if senior citizen)",
                    "Total combined limit: ₹100,000",
                ],
            },
            "80AC": {
                "description": "Section 80AC - Deduction for insurance related to construction",
                "limit": 150000,
                "items": [
                    "Life insurance premium for home loan",
                    "Building insurance premium",
                ],
            },
            "24(b)": {
                "description": "Section 24(b) - Deduction for interest on borrowed capital",
                "limit": None,  # Unlimited but must be on property
                "items": [
                    "Home loan interest (unlimited on one property)",
                    "Home loan interest ₹200,000 cap on second property",
                ],
            },
        }

    def call(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 1024,
    ) -> Optional[str]:
        """Generate response using rule-based logic"""
        query = user_message.lower()
        
        # Tax terminology responses
        if "80c" in query:
            rule = self.rules.get("80C", {})
            return f"**{rule.get('description')}**\n\n" \
                   f"Maximum deduction: ₹{rule.get('limit'):,}\n\n" \
                   f"Eligible items:\n" + \
                   "\n".join(f"• {item}" for item in rule.get("items", []))
        
        elif "80d" in query or "health insurance" in query:
            rule = self.rules.get("80D", {})
            return f"**{rule.get('description')}**\n\n" \
                   f"Maximum deduction: ₹{rule.get('limit'):,}\n\n" \
                   f"Details:\n" + \
                   "\n".join(f"• {item}" for item in rule.get("items", []))
        
        elif "interest" in query or "24(b)" in query or "home loan" in query:
            rule = self.rules.get("24(b)", {})
            return f"**{rule.get('description')}**\n\n" \
                   f"Details:\n" + \
                   "\n".join(f"• {item}" for item in rule.get("items", []))
        
        elif "nri" in query or "residency" in query:
            return "**NRI Taxation**\n\n" \
                   "• NRI (Non-Resident Indian) status determined by residency test\n" \
                   "• Income from India only is taxable in India\n" \
                   "• Foreign income: Not taxable in India\n" \
                   "• Must file ITR-2 form\n" \
                   "• Available deductions: 80C, 80D, 24(b), depending on income source"
        
        elif "rnor" in query or "resident not ordinarily" in query:
            return "**RNOR (Resident Not Ordinarily Resident)**\n\n" \
                   "• Worldwide income is taxable\n" \
                   "• More deductions available than NRI\n" \
                   "• Foreign remittance not taxable in India (in most cases)\n" \
                   "• Full section 80C, 80D benefits available\n" \
                   "• Must file ITR-2 form"
        
        elif "refund" in query:
            return "**Tax Refund Process**\n\n" \
                   "• If TDS > tax liability, you get refund\n" \
                   "• Refund amount = TDS deducted - Total tax\n" \
                   "• File ITR within 31st July to claim refund\n" \
                   "• Refund usually credited within 3-6 months\n" \
                   "• No interest if refund after 3 months (as per new rules)"
        
        elif "tds" in query or "tax deducted at source" in query:
            return "**TDS (Tax Deducted at Source)**\n\n" \
                   "• TDS is advance tax deducted at payment source\n" \
                   "• Common TDS rates: 10% (salary), 20% (interest), 30% (dividends)\n" \
                   "• You get credit for TDS paid against total tax liability\n" \
                   "• Form 26AS shows all TDS deducted on your PAN\n" \
                   "• Reconcile TDS in ITR with Form 26AS"
        
        else:
            return "I can help with tax concepts. Ask me about:\n" \
                   "• Section 80C (deductions up to ₹1.5L)\n" \
                   "• Section 80D (health insurance)\n" \
                   "• Section 24(b) (home loan interest)\n" \
                   "• NRI/RNOR residency status\n" \
                   "• TDS and refund process\n" \
                   "• Tax-saving strategies"


@lru_cache(maxsize=1)
def get_llm_config() -> LLMConfig:
    """Get singleton LLM configuration"""
    return LLMConfig()


def get_llm_provider() -> Optional[Any]:
    """Get configured LLM provider instance"""
    config = get_llm_config()

    try:
        if config.provider == "claude" and config.claude_api_key:
            return ClaudeProvider(config.claude_api_key)
        elif config.provider == "chatgpt" and config.openai_api_key:
            return ChatGPTProvider(config.openai_api_key)
        else:
            return RuleBasedProvider()
    except Exception as e:
        logger.error(f"Error initializing LLM provider: {e}")
        return RuleBasedProvider()


async def call_llm(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 1024,
) -> Dict[str, Any]:
    """
    Unified LLM call interface
    Returns: {ok: bool, response: str, source: str, provider: str}
    """
    config = get_llm_config()
    provider = get_llm_provider()

    try:
        response = provider.call(system_prompt, user_message, max_tokens)
        
        if response:
            return {
                "ok": True,
                "response": response,
                "source": config.provider,
                "provider": config.get_provider_name(),
            }
        else:
            # Fallback if provider returned None
            if config.provider != "rule_based" and config.fallback_to_rules:
                logger.info(f"{config.provider} returned None, falling back to rules")
                rule_provider = RuleBasedProvider()
                response = rule_provider.call(system_prompt, user_message, max_tokens)
                return {
                    "ok": True,
                    "response": response or "Unable to process request",
                    "source": "rule_based",
                    "provider": "Rule-Based AI (Fallback)",
                }
            else:
                return {
                    "ok": False,
                    "response": "LLM provider unavailable",
                    "source": config.provider,
                    "provider": config.get_provider_name(),
                }
    except Exception as e:
        logger.error(f"LLM call error: {e}")
        return {
            "ok": False,
            "response": str(e),
            "source": "error",
            "provider": "Unknown",
        }


# Tax-specific system prompts
SYSTEM_PROMPTS = {
    "tax_guidance": """You are an expert Indian Income Tax (ITR) filing assistant. 
Provide guidance on:
- Income tax calculations and tax slabs
- Tax deductions (80C, 80D, 24b, etc.)
- NRI/RNOR/ROR tax implications
- Form 26AS and AIS reconciliation
- TDS and refund processes

Always provide accurate, government-compliant information. Include relevant section numbers.
Cite: Income Tax Act, 1961 and latest Finance Act provisions.""",

    "deductions": """You are a tax deductions specialist for Indian ITR filing.
Help users identify and maximize deductions under:
- Section 80C: ₹1.5L investments limit
- Section 80D: Health insurance premiums
- Section 80AC: Life insurance for home loan
- Section 24(b): Home loan interest
- Section 80G: Charitable donations
- Section 80E: Education loan interest

Provide specific recommendations based on user profile.""",

    "reconciliation": """You are an expert in reconciling ITR with government records.
Help users understand:
- AIS (Annual Information Statement) vs Form 26AS
- Source vs reported income in ITR
- TDS credit reconciliation
- Income variance analysis
- Filing requirements and compliance

Be precise with numbers and explain variances professionally.""",

    "residency": """You are an expert on Indian tax residency and NRI/RNOR taxation.
Explain:
- Residency determination tests (182-day rule, 60/120 day tests)
- NRI vs RNOR vs ROR tax implications
- Income source classification (salary, business, capital gains)
- Foreign remittance exemptions
- Form 26AS filing for non-residents

Provide clear guidance on residency changes and ITR impact.""",

    "tax_savings": """You are a tax optimization specialist for Indian taxpayers.
Suggest strategies to minimize legal tax liability:
- Optimal Section 80C investments
- Health insurance under 80D
- Education loan interest under 80E
- Capital gain planning
- Residency optimization
- Deduction timing across years

Ensure all suggestions comply with Income Tax Act, 1961.""",
}


async def get_tax_guidance(
    query: str, context: Optional[Dict] = None
) -> Dict[str, Any]:
    """Get tax guidance on specific topic"""
    return await call_llm(
        system_prompt=SYSTEM_PROMPTS["tax_guidance"],
        user_message=query,
    )


async def get_deduction_recommendations(
    income_data: Dict, context: Optional[Dict] = None
) -> Dict[str, Any]:
    """Get personalized deduction recommendations"""
    user_msg = f"""Based on this profile, suggest deductions:
- Gross Income: ₹{income_data.get('gross_income', 0):,}
- Residency: {income_data.get('residency', 'Unknown')}
- Dependents: {income_data.get('dependents', 0)}
- Health Status: {income_data.get('health_status', 'Normal')}
- Home Loan: {'Yes' if income_data.get('has_home_loan') else 'No'}

Prioritize and quantify recommendations."""

    return await call_llm(
        system_prompt=SYSTEM_PROMPTS["deductions"],
        user_message=user_msg,
    )


async def get_reconciliation_help(
    variance_data: Dict,
) -> Dict[str, Any]:
    """Explain reconciliation variances"""
    user_msg = f"""Analyze these reconciliation variances:
- Source Income: ₹{variance_data.get('source_income', 0):,}
- AIS Income: ₹{variance_data.get('ais_income', 0):,}
- ITR Income: ₹{variance_data.get('itr_income', 0):,}
- TDS Source: ₹{variance_data.get('tds_source', 0):,}
- TDS 26AS: ₹{variance_data.get('tds_26as', 0):,}

What might explain these differences? What actions needed?"""

    return await call_llm(
        system_prompt=SYSTEM_PROMPTS["reconciliation"],
        user_message=user_msg,
    )


async def get_residency_analysis(
    profile_data: Dict,
) -> Dict[str, Any]:
    """Analyze residency status and implications"""
    user_msg = f"""Analyze residency status and tax implications:
- Current Status: {profile_data.get('current_status', 'Unknown')}
- Days in India FY: {profile_data.get('days_in_india', 0)}
- Previous 4 Years Status: {profile_data.get('previous_status', 'Unknown')}
- Visa Type: {profile_data.get('visa_type', 'Unknown')}
- Permanent Residence: {profile_data.get('permanent_residence', 'India')}

What's the filing requirement and tax implications?"""

    return await call_llm(
        system_prompt=SYSTEM_PROMPTS["residency"],
        user_message=user_msg,
    )
