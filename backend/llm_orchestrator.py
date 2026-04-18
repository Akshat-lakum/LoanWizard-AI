"""
llm_orchestrator.py — LLM-Powered Conversation Engine
Drives the AI agent's conversation during the video call.
Supports: Google Gemini (FREE), Claude, GPT — with template fallback.
"""

import os
import json
import logging
from typing import Optional, List, Dict
from models import ExtractedEntities, LoanPurpose, SessionStatus

logger = logging.getLogger(__name__)

# ─── LLM Client ─────────────────────────────────────────────

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

_client = None
_provider = None


def _get_client():
    """Get or create the LLM client. Tries Gemini (free) first."""
    global _client, _provider
    if _client is not None:
        return _client, _provider

    # Try Google Gemini first (FREE — 10 RPM, 250 requests/day)
    if GEMINI_API_KEY:
        try:
            from google import genai
            _client = genai.Client(api_key=GEMINI_API_KEY)
            _provider = "gemini"
            logger.info("Using Google Gemini API (FREE tier).")
            return _client, _provider
        except ImportError:
            # Try older SDK format
            try:
                import google.generativeai as genai
                genai.configure(api_key=GEMINI_API_KEY)
                _client = genai
                _provider = "gemini_legacy"
                logger.info("Using Google Gemini API (legacy SDK).")
                return _client, _provider
            except Exception as e:
                logger.warning(f"Gemini init failed: {e}")

    # Try Anthropic
    if ANTHROPIC_API_KEY:
        try:
            import anthropic
            _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            _provider = "anthropic"
            logger.info("Using Anthropic Claude API.")
            return _client, _provider
        except Exception as e:
            logger.warning(f"Anthropic init failed: {e}")

    # Fallback to OpenAI
    if OPENAI_API_KEY:
        try:
            from openai import OpenAI
            _client = OpenAI(api_key=OPENAI_API_KEY)
            _provider = "openai"
            logger.info("Using OpenAI GPT API.")
            return _client, _provider
        except Exception as e:
            logger.warning(f"OpenAI init failed: {e}")

    logger.warning("No LLM API key found. Using template-based responses.")
    return None, "template"


# ─── System Prompt ───────────────────────────────────────────

SYSTEM_PROMPT = """You are LoanWizard, a friendly and professional AI loan officer for Poonawalla Fincorp. 
You are conducting a video call with a customer who wants to apply for a loan.

YOUR ROLE:
- Guide the customer through the loan application process conversationally
- Be warm, empathetic, and multilingual (respond in the customer's language)
- Ask questions naturally, one at a time — never overwhelm
- Acknowledge what the customer says before asking the next question

INFORMATION TO COLLECT (in this order):
1. Full name
2. Age
3. City/location
4. Employment type (salaried / self-employed / student)
5. Employer name (if salaried)
6. Monthly income / annual income
7. Loan purpose (education, personal, business, home, gold)
8. Approximate loan amount needed
9. Consent for data processing and credit check

IMPORTANT RULES:
- Keep responses SHORT (2-3 sentences max) — this is a video call, not an essay
- Be conversational, not robotic. Use natural transitions.
- If the customer speaks Hindi or another Indian language, respond in that language
- Never ask for sensitive info like Aadhaar/PAN directly — that comes later
- If something is unclear, ask for clarification politely
- After collecting all info, summarize what you have and confirm with the customer
- Always sound confident and reassuring about the loan process

CURRENT CONVERSATION STATE:
{state_context}

COLLECTED INFORMATION SO FAR:
{entities_context}

Generate ONLY the AI agent's next response. Keep it natural and brief."""


# ─── Conversation State Machine ──────────────────────────────

CONVERSATION_FLOW = [
    {"field": "full_name", "question": "greeting", "prompt": "Greet the customer warmly and ask for their name."},
    {"field": "age_declared", "question": "age", "prompt": "Ask their age naturally."},
    {"field": "city", "question": "location", "prompt": "Ask which city they're from."},
    {"field": "employment_type", "question": "employment", "prompt": "Ask about their employment — are they salaried, self-employed, or a student?"},
    {"field": "employer_name", "question": "employer", "prompt": "Ask where they work (company name). Skip if self-employed."},
    {"field": "monthly_income", "question": "income", "prompt": "Ask about their monthly or annual income."},
    {"field": "loan_purpose", "question": "purpose", "prompt": "Ask what the loan is for."},
    {"field": "loan_amount_requested", "question": "amount", "prompt": "Ask how much loan amount they need."},
    {"field": None, "question": "consent", "prompt": "Summarize collected information and ask for verbal consent to proceed with application and credit check."},
    {"field": None, "question": "offer", "prompt": "Thank the customer and let them know you're generating their personalized loan offer."},
]


def get_current_step(entities: ExtractedEntities) -> Dict:
    """Determine which step of the conversation we're at."""
    entity_dict = entities.model_dump()

    for step in CONVERSATION_FLOW:
        if step["field"] is None:
            # Consent/offer step — only reach here if all fields are filled
            return step
        if entity_dict.get(step["field"]) is None:
            # Skip employer if self-employed
            if step["field"] == "employer_name" and entity_dict.get("employment_type") == "self_employed":
                continue
            return step

    # All fields collected — move to consent/offer
    return CONVERSATION_FLOW[-2]  # consent step


def build_entities_context(entities: ExtractedEntities) -> str:
    """Build a human-readable summary of collected entities."""
    d = entities.model_dump()
    parts = []
    labels = {
        "full_name": "Name",
        "age_declared": "Age",
        "city": "City",
        "employment_type": "Employment",
        "employer_name": "Employer",
        "monthly_income": "Monthly Income",
        "loan_purpose": "Loan Purpose",
        "loan_amount_requested": "Loan Amount",
    }

    for field, label in labels.items():
        value = d.get(field)
        if value is not None:
            if field == "monthly_income":
                parts.append(f"- {label}: ₹{value:,.0f}")
            elif field == "loan_amount_requested":
                parts.append(f"- {label}: ₹{value:,.0f}")
            else:
                parts.append(f"- {label}: {value}")
        else:
            parts.append(f"- {label}: [not yet collected]")

    return "\n".join(parts)


# ─── Generate Response ───────────────────────────────────────

async def generate_agent_response(
    transcript: str,
    entities: ExtractedEntities,
    conversation_history: List[Dict[str, str]],
    language: str = "en",
) -> str:
    """
    Generate the AI agent's next response based on the conversation state.
    
    Args:
        transcript: Latest customer speech (from STT)
        entities: Currently extracted entities
        conversation_history: List of {"role": "user"/"assistant", "content": "..."}
        language: Detected language of customer
    
    Returns:
        Agent's response text (to be converted to speech via TTS)
    """
    client, provider = _get_client()

    # Determine current step
    current_step = get_current_step(entities)
    state_context = f"Current step: {current_step['question']}\nInstruction: {current_step['prompt']}"
    if language != "en":
        state_context += f"\nCustomer is speaking in: {language}. Respond in the same language."

    entities_context = build_entities_context(entities)

    system = SYSTEM_PROMPT.format(
        state_context=state_context,
        entities_context=entities_context
    )

    # Build messages
    messages = []
    for msg in conversation_history[-10:]:  # Last 10 messages for context
        messages.append(msg)

    if transcript.strip():
        messages.append({"role": "user", "content": transcript})

    if provider == "gemini" and client:
        return await _call_gemini(client, system, messages)
    elif provider == "gemini_legacy" and client:
        return await _call_gemini_legacy(client, system, messages)
    elif provider == "anthropic" and client:
        return await _call_anthropic(client, system, messages)
    elif provider == "openai" and client:
        return await _call_openai(client, system, messages)
    else:
        return _template_response(current_step, entities, transcript)


async def _call_gemini(client, system: str, messages: List[Dict]) -> str:
    """Call Google Gemini API (new google-genai SDK)."""
    try:
        # Build the full prompt with system context
        full_prompt = system + "\n\n"
        for msg in messages[-8:]:
            role = "Customer" if msg["role"] == "user" else "Agent"
            full_prompt += f"{role}: {msg['content']}\n"
        full_prompt += "Agent:"

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=full_prompt,
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return "I apologize for the brief pause. Could you please repeat that?"


async def _call_gemini_legacy(client, system: str, messages: List[Dict]) -> str:
    """Call Google Gemini API (legacy google-generativeai SDK)."""
    try:
        model = client.GenerativeModel(
            "gemini-2.5-flash",
            system_instruction=system,
        )

        # Convert messages to Gemini chat format
        history = []
        for msg in messages[:-1]:  # All except last
            role = "user" if msg["role"] == "user" else "model"
            history.append({"role": role, "parts": [msg["content"]]})

        chat = model.start_chat(history=history)
        last_msg = messages[-1]["content"] if messages else "Start the conversation."
        response = chat.send_message(last_msg)

        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini Legacy API error: {e}")
        return "I apologize for the brief pause. Could you please repeat that?"


async def _call_anthropic(client, system: str, messages: List[Dict]) -> str:
    """Call Claude API."""
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            system=system,
            messages=messages if messages else [{"role": "user", "content": "Start the conversation."}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Anthropic API error: {e}")
        return "I apologize for the brief pause. Could you please repeat that?"


async def _call_openai(client, system: str, messages: List[Dict]) -> str:
    """Call OpenAI GPT API."""
    try:
        msgs = [{"role": "system", "content": system}]
        msgs.extend(messages if messages else [{"role": "user", "content": "Start the conversation."}])

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=200,
            messages=msgs,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return "I apologize for the brief pause. Could you please repeat that?"


# ─── Template Fallback (No API Key) ─────────────────────────

def _template_response(step: Dict, entities: ExtractedEntities, transcript: str) -> str:
    """
    Template-based responses when no LLM API is available.
    This ensures the demo works even without API keys.
    """
    q = step["question"]

    templates = {
        "greeting": "Welcome to Poonawalla Fincorp! I'm LoanWizard, your AI loan assistant. "
                     "I'll help you with your loan application today. Could you please tell me your name?",

        "age": f"Nice to meet you{', ' + entities.full_name if entities.full_name else ''}! "
               "Could you tell me your age please?",

        "location": "Great, thank you! Which city are you currently based in?",

        "employment": "Got it! And are you currently salaried, self-employed, or a student?",

        "employer": "Wonderful! Could you tell me which company you work with?",

        "income": "Thank you! Could you share your approximate monthly or annual income? "
                  "This helps us determine the best loan options for you.",

        "purpose": "Perfect! What would you like the loan for? "
                   "Is it for education, personal needs, business, home, or something else?",

        "amount": "I see! And approximately how much loan amount are you looking for?",

        "consent": f"Thank you for sharing all the details! Let me summarize:\n"
                   f"Name: {entities.full_name or 'N/A'}, "
                   f"Age: {entities.age_declared or 'N/A'}, "
                   f"Income: ₹{entities.monthly_income:,.0f}/month, "
                   f"Loan Purpose: {entities.loan_purpose or 'N/A'}, "
                   f"Amount: ₹{entities.loan_amount_requested:,.0f}. "
                   f"Do I have your consent to proceed with the application and credit check?"
                   if entities.monthly_income and entities.loan_amount_requested
                   else "Thank you for sharing the details. Do I have your consent to proceed?",

        "offer": "Excellent! Thank you for your consent. I'm now generating your personalized loan offer. "
                 "Please hold on for just a moment!",
    }

    return templates.get(q, "Thank you! Let me process that information.")


# ─── Consent Verification ────────────────────────────────────

async def verify_consent(transcript: str) -> bool:
    """
    Check if the customer's response indicates consent.
    Looks for affirmative keywords in multiple languages.
    """
    text = transcript.lower().strip()

    # Affirmative keywords (English, Hindi, Gujarati, Marathi)
    yes_keywords = [
        "yes", "yeah", "yep", "sure", "okay", "ok", "fine", "agree",
        "i consent", "i agree", "go ahead", "proceed", "haan", "ha",
        "ji haan", "theek hai", "bilkul", "zaroor", "ho",
        "chalo", "karo", "kar do",
    ]

    return any(kw in text for kw in yes_keywords)


# ─── Fraud Conversation Analysis ─────────────────────────────

async def analyze_conversation_for_fraud(
    conversation_history: List[Dict[str, str]],
    entities: ExtractedEntities
) -> List[str]:
    """
    Analyze conversation patterns for potential fraud signals.
    Returns list of red flags detected.
    """
    red_flags = []

    # Check for inconsistencies
    if entities.monthly_income and entities.loan_amount_requested:
        # Loan-to-income ratio check
        ratio = entities.loan_amount_requested / (entities.monthly_income * 12)
        if ratio > 10:
            red_flags.append("loan_amount_extremely_high_vs_income")

    # Check for coached/scripted responses
    user_messages = [m["content"] for m in conversation_history if m["role"] == "user"]
    if len(user_messages) >= 3:
        # All responses suspiciously similar length
        lengths = [len(m) for m in user_messages]
        avg_len = sum(lengths) / len(lengths)
        if all(abs(l - avg_len) < 5 for l in lengths) and avg_len > 20:
            red_flags.append("suspiciously_uniform_response_lengths")

    # Student claiming very high income
    if entities.employment_type == "student" and entities.monthly_income and entities.monthly_income > 100000:
        red_flags.append("student_claiming_high_income")

    return red_flags
