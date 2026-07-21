"""
AI Master Orchestrator - Central Conversation Router

Routes user intents to specialist AI assistants:
- Tax Specialist
- Deduction Specialist
- Compliance Specialist
- Reconciliation Specialist
- Document Specialist
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import re


class SpecialistType(Enum):
    """Available specialist AI assistants"""
    TAX = "tax_specialist"
    DEDUCTION = "deduction_specialist"
    COMPLIANCE = "compliance_specialist"
    RECONCILIATION = "reconciliation_specialist"
    DOCUMENT = "document_specialist"
    GENERAL = "general_assistant"


@dataclass
class ConversationTurn:
    """Single turn in conversation"""
    user_message: str
    specialist_routed_to: SpecialistType
    assistant_response: str
    confidence_score: float
    timestamp: datetime = field(default_factory=datetime.now)
    follow_up_questions: List[str] = field(default_factory=list)


@dataclass
class SessionContext:
    """Session state and context"""
    session_id: str
    household_id: str
    member_ids: List[str]
    assessment_year: int
    conversation_history: List[ConversationTurn] = field(default_factory=list)
    current_topic: Optional[str] = None
    filing_stage: str = "intake"  # intake, income_entry, deduction_entry, validation, filing
    last_interaction: datetime = field(default_factory=datetime.now)


class IntentClassifier:
    """Classify user intent and route to appropriate specialist"""

    # Intent patterns for routing
    INTENT_PATTERNS = {
        SpecialistType.TAX: [
            r"(tax|calculation|how much|effective rate|bracket|slab|rate|regime)",
            r"(old regime|new regime|comparison)",
            r"(liability|payable|refund|amount owed)",
        ],
        SpecialistType.DEDUCTION: [
            r"(deduction|80c|80d|80e|savings|insurance|education|home loan)",
            r"(claim|eligible|limit|maximum)",
            r"(save|optimize|reduce tax)",
        ],
        SpecialistType.COMPLIANCE: [
            r"(rule|regulation|government|requirement|compliance|valid)",
            r"(income tax act|section|law|legal)",
            r"(penalty|fine|error|incorrect)",
        ],
        SpecialistType.RECONCILIATION: [
            r"(reconcil|match|mismatch|differ|discrepancy)",
            r"(26as|ais|form|tds|salary)",
            r"(statement|report|verify|validate)",
        ],
        SpecialistType.DOCUMENT: [
            r"(document|upload|file|image|pdf|certificate)",
            r"(bank.*statement|26as|ais|cas|cersai|form)",
            r"(extract|parse|read|scan)",
        ],
    }

    def classify(self, user_message: str) -> tuple[SpecialistType, float]:
        """
        Classify user message and return specialist type with confidence.
        
        Returns: (specialist_type, confidence_score)
        """
        message_lower = user_message.lower()
        scores = {}

        for specialist, patterns in self.INTENT_PATTERNS.items():
            specialist_score = 0
            matches = 0
            
            for pattern in patterns:
                if re.search(pattern, message_lower, re.IGNORECASE):
                    matches += 1
                    specialist_score += 1
            
            scores[specialist] = specialist_score

        # Find specialist with highest score
        if not any(scores.values()):
            return SpecialistType.GENERAL, 0.3

        best_specialist = max(scores, key=scores.get)
        confidence = min(scores[best_specialist] / 3.0, 1.0)  # Normalize to 0-1

        return best_specialist, confidence

    def extract_entities(self, user_message: str) -> Dict[str, Any]:
        """Extract relevant entities from message"""
        entities = {}

        # Extract amounts
        amounts = re.findall(r'₹?\s*(\d{1,3}(?:,\d{3})*|\d+)', user_message)
        if amounts:
            entities["amounts"] = amounts

        # Extract sections
        sections = re.findall(r'80[A-Z]|Section \d+', user_message, re.IGNORECASE)
        if sections:
            entities["sections"] = sections

        # Extract dates
        dates = re.findall(
            r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}',
            user_message
        )
        if dates:
            entities["dates"] = dates

        return entities


class SpecialistAIRouter:
    """Route and manage specialist AI responses"""

    SPECIALIST_PROMPTS = {
        SpecialistType.TAX: """You are a TAX SPECIALIST for Indian Income Tax (ITR).
- Explain tax calculations clearly
- Reference specific tax slabs and rules
- Compare old vs new regimes
- Calculate effective tax rates
- Provide government portal references
Answer professionally with exact figures.""",

        SpecialistType.DEDUCTION: """You are a DEDUCTION SPECIALIST for Income Tax Act Chapter VIA.
- Suggest applicable deductions based on user profile
- Explain deduction limits and eligibility
- Help optimize tax savings
- Mention investment options
- Reference relevant sections (80C, 80D, 80E, etc.)
Focus on legitimate and compliant deductions only.""",

        SpecialistType.COMPLIANCE: """You are a COMPLIANCE SPECIALIST for Income Tax Act.
- Verify compliance with government rules
- Flag potential errors or violations
- Reference relevant sections and amendments
- Explain government requirements
- Link to official Income Tax Department resources
Ensure 100% compliance with current tax laws.""",

        SpecialistType.RECONCILIATION: """You are a RECONCILIATION SPECIALIST.
- Match source statements with AIS/Form 26AS
- Identify discrepancies
- Suggest corrections
- Explain differences with government links
- Validate three-way reconciliation
Help users understand and resolve mismatches.""",

        SpecialistType.DOCUMENT: """You are a DOCUMENT SPECIALIST.
- Assist with document uploads and parsing
- Extract data from bank statements, certificates, reports
- Identify required documents for filing
- Validate document completeness
- Guide through document organization
Be precise about extracted data.""",

        SpecialistType.GENERAL: """You are a helpful ITR FILING ASSISTANT.
- Answer general questions about ITR filing
- Guide through the filing process
- Clarify terminology
- Route complex questions to specialists
- Provide encouragement and support
Be friendly and supportive.""",
    }

    def __init__(self, llm_provider=None):
        """Initialize router with LLM provider"""
        self.llm_provider = llm_provider  # Will be injected at runtime
        self.intent_classifier = IntentClassifier()

    def route_and_respond(
        self,
        user_message: str,
        context: SessionContext,
    ) -> ConversationTurn:
        """
        Route user message to appropriate specialist and get response.
        
        Returns ConversationTurn with specialist response.
        """
        # Classify intent
        specialist, confidence = self.intent_classifier.classify(user_message)
        
        # Extract entities
        entities = self.intent_classifier.extract_entities(user_message)
        
        # Get specialist prompt
        system_prompt = self.SPECIALIST_PROMPTS[specialist]
        
        # Build context for LLM
        context_str = self._build_context_string(context, specialist)
        
        # Get response from LLM (mocked for now)
        assistant_response = self._get_specialist_response(
            user_message,
            system_prompt,
            context_str,
            specialist,
            entities,
        )
        
        # Generate follow-up questions
        follow_ups = self._generate_follow_up_questions(specialist, user_message)
        
        # Create conversation turn
        turn = ConversationTurn(
            user_message=user_message,
            specialist_routed_to=specialist,
            assistant_response=assistant_response,
            confidence_score=confidence,
            follow_up_questions=follow_ups,
        )
        
        # Update session context
        context.conversation_history.append(turn)
        context.current_topic = specialist.value
        context.last_interaction = datetime.now()
        
        return turn

    def _build_context_string(
        self,
        context: SessionContext,
        specialist: SpecialistType,
    ) -> str:
        """Build context string for specialist"""
        context_lines = [
            f"Assessment Year: {context.assessment_year}",
            f"Filing Stage: {context.filing_stage}",
            f"Household Members: {len(context.member_ids)}",
            f"Previous Messages: {len(context.conversation_history)}",
        ]
        
        if context.conversation_history:
            last_topic = context.conversation_history[-1].specialist_routed_to.value
            context_lines.append(f"Last Topic: {last_topic}")
        
        return "\n".join(context_lines)

    def _get_specialist_response(
        self,
        user_message: str,
        system_prompt: str,
        context: str,
        specialist: SpecialistType,
        entities: Dict,
    ) -> str:
        """Get response from specialist AI (LLM call)"""
        # This will be replaced with actual LLM call
        # For now, return mock response
        
        mock_responses = {
            SpecialistType.TAX: f"""Based on your income of ₹{entities.get('amounts', ['500000'])[0]} and the current tax slabs:
- Your effective tax rate would be approximately 15-20%
- Consider the new regime if you have minimal deductions
- Refer: Income Tax Act, Section 87-88
- More details: https://www.incometax.gov.in""",

            SpecialistType.DEDUCTION: f"""You may be eligible for deductions under Section {entities.get('sections', ['80C'])[0]}.
- Eligible limit: ₹1,50,000 for Section 80C
- Consider PPF, ELSS, Life Insurance
- Get your investment proof/policy documents ready
- Refer: Income Tax Act, Chapter VIA""",

            SpecialistType.COMPLIANCE: """To ensure compliance:
- File ITR before due date (July 31st for FY 2025-26)
- Provide all supporting documents
- Ensure all income is reported
- Match against AIS/Form 26AS
- Refer: Income Tax Department official portal""",

            SpecialistType.RECONCILIATION: """Let's verify your income details:
1. Compare salary from Form 26AS
2. Match with your bank account deposits
3. Reconcile investment income
4. Validate TDS credits
Would you like to upload documents for verification?""",

            SpecialistType.DOCUMENT: """For document uploads:
1. Bank statements (last 12 months)
2. Form 26AS / AIS from Income Tax portal
3. Salary certificates
4. Investment certificates
5. Property documents (if applicable)
Please ensure documents are clear and readable.""",

            SpecialistType.GENERAL: """I'm here to help you with your ITR filing! 
I can assist with:
- Tax calculations
- Deduction optimization
- Document management
- Compliance verification
- Three-way reconciliation
What would you like help with?""",
        }
        
        return mock_responses.get(specialist, "How can I assist you with your ITR filing?")

    def _generate_follow_up_questions(
        self,
        specialist: SpecialistType,
        user_message: str,
    ) -> List[str]:
        """Generate contextual follow-up questions"""
        
        follow_ups = {
            SpecialistType.TAX: [
                "Would you like to compare old vs new tax regime?",
                "Do you want to explore tax-saving strategies?",
                "Should I calculate your effective tax rate?",
            ],
            SpecialistType.DEDUCTION: [
                "Do you have any health insurance premiums to claim?",
                "Are you investing in any tax-saving instruments?",
                "Do you have education loan interest to claim?",
            ],
            SpecialistType.COMPLIANCE: [
                "Have you filed ITR in previous years?",
                "Do you have any pending compliance issues?",
                "Would you like to verify against government data?",
            ],
            SpecialistType.RECONCILIATION: [
                "Can you provide your Form 26AS details?",
                "Do you have any salary certificate?",
                "Are there any discrepancies you've noticed?",
            ],
            SpecialistType.DOCUMENT: [
                "Which documents would you like to upload first?",
                "Do you need help organizing your documents?",
                "Would you like to batch upload documents?",
            ],
            SpecialistType.GENERAL: [
                "Is there a specific section of ITR you need help with?",
                "Would you like me to explain the filing process?",
                "Can I route you to a specialist?",
            ],
        }
        
        return follow_ups.get(specialist, ["How else can I help?"])


class AIMasterOrchestrator:
    """Main AI orchestrator for household ITR assistance"""

    def __init__(self, llm_provider=None):
        self.router = SpecialistAIRouter(llm_provider)
        self.sessions: Dict[str, SessionContext] = {}

    def start_session(
        self,
        household_id: str,
        member_ids: List[str],
        assessment_year: int = 2026,
    ) -> SessionContext:
        """Start new conversation session"""
        session = SessionContext(
            session_id=f"session_{datetime.now().timestamp()}",
            household_id=household_id,
            member_ids=member_ids,
            assessment_year=assessment_year,
        )
        self.sessions[session.session_id] = session
        return session

    def process_user_message(
        self,
        session_id: str,
        user_message: str,
    ) -> ConversationTurn:
        """Process user message in session"""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")
        
        context = self.sessions[session_id]
        return self.router.route_and_respond(user_message, context)

    def get_session_summary(self, session_id: str) -> Dict:
        """Get summary of conversation session"""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")
        
        context = self.sessions[session_id]
        return {
            "session_id": context.session_id,
            "household_id": context.household_id,
            "assessment_year": context.assessment_year,
            "turns_count": len(context.conversation_history),
            "current_topic": context.current_topic,
            "filing_stage": context.filing_stage,
            "specialists_engaged": list(set(
                turn.specialist_routed_to.value
                for turn in context.conversation_history
            )),
            "last_interaction": context.last_interaction.isoformat(),
        }

    def get_conversation_history(self, session_id: str) -> List[Dict]:
        """Get full conversation history"""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")
        
        context = self.sessions[session_id]
        return [
            {
                "user_message": turn.user_message,
                "specialist": turn.specialist_routed_to.value,
                "response": turn.assistant_response,
                "confidence": turn.confidence_score,
                "follow_ups": turn.follow_up_questions,
                "timestamp": turn.timestamp.isoformat(),
            }
            for turn in context.conversation_history
        ]
