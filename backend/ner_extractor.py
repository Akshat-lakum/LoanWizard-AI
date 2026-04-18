"""
ner_extractor.py — Named Entity & Information Extraction
Extracts structured data from customer speech transcripts.
Combines spaCy NER with rule-based regex patterns for financial entities.
"""

import re
import logging
from typing import Optional
from models import ExtractedEntities, LoanPurpose

logger = logging.getLogger(__name__)

# ─── spaCy Model (lazy load) ─────────────────────────────────

_nlp = None


def _load_spacy():
    """Load spaCy model on first use."""
    global _nlp
    if _nlp is not None:
        return _nlp
    try:
        import spacy
        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.info("Downloading spaCy en_core_web_sm model...")
            from spacy.cli import download
            download("en_core_web_sm")
            _nlp = spacy.load("en_core_web_sm")
        logger.info("spaCy model loaded.")
        return _nlp
    except Exception as e:
        logger.warning(f"Could not load spaCy: {e}")
        return None


# ─── Regex Patterns ──────────────────────────────────────────

# Income patterns (Indian context)
INCOME_PATTERNS = [
    # "I earn 50000 per month" / "my salary is 50,000"
    r'(?:earn|salary|income|make|get paid|drawing)\s*(?:is|of)?\s*(?:around|about|approximately|roughly)?\s*(?:Rs\.?|₹|INR)?\s*([\d,]+(?:\.\d+)?)\s*(?:per month|monthly|p\.?m\.?|a month)?',
    # "50k per month" / "50K monthly"
    r'(?:Rs\.?|₹|INR)?\s*([\d,]+(?:\.\d+)?)\s*[kK]\s*(?:per month|monthly|p\.?m\.?|a month)',
    # "my monthly income is 50000"
    r'monthly\s+(?:income|salary|earning)\s+(?:is|of)\s+(?:Rs\.?|₹|INR)?\s*([\d,]+(?:\.\d+)?)',
    # "I get 5 lakhs per annum" / "5 LPA"
    r'([\d,.]+)\s*(?:lakhs?|lacs?|L)\s*(?:per annum|per year|annually|p\.?a\.?|LPA)',
    # Simple number after income keyword
    r'(?:income|salary)\s*(?:is)?\s*(?:Rs\.?|₹|INR)?\s*([\d,]+)',
]

# Loan amount patterns
LOAN_AMOUNT_PATTERNS = [
    r'(?:need|want|require|looking for|apply for)\s+(?:a loan of|loan for|loan of)?\s*(?:Rs\.?|₹|INR)?\s*([\d,]+(?:\.\d+)?)\s*(?:lakhs?|lacs?|L)?',
    r'(?:loan|amount)\s+(?:of|for)\s+(?:Rs\.?|₹|INR)?\s*([\d,]+(?:\.\d+)?)\s*(?:lakhs?|lacs?|L)?',
    r'(?:Rs\.?|₹|INR)\s*([\d,]+(?:\.\d+)?)\s*(?:lakhs?|lacs?|L)?\s*(?:loan|ka loan)',
]

# Age patterns
AGE_PATTERNS = [
    r'(?:I am|I\'m|my age is|age)\s+(\d{2})\s*(?:years?\s*old)?',
    r'(\d{2})\s*(?:years?\s*old|yrs?\s*old|sal ka)',
]

# Employment patterns
EMPLOYMENT_KEYWORDS = {
    "salaried": ["salaried", "employee", "working at", "work at", "job at", "employed", "naukri"],
    "self_employed": ["self employed", "self-employed", "business", "own business", "freelancer", "freelancing", "entrepreneur", "shop", "dukaan"],
    "student": ["student", "studying", "college", "university", "school", "padhai"],
}

# Loan purpose patterns
PURPOSE_KEYWORDS = {
    LoanPurpose.EDUCATION: ["education", "study", "college", "university", "course", "tuition", "abroad", "masters", "MBA", "padhai", "fees"],
    LoanPurpose.PERSONAL: ["personal", "wedding", "marriage", "medical", "emergency", "travel", "shaadi"],
    LoanPurpose.BUSINESS: ["business", "startup", "shop", "inventory", "equipment", "dukaan", "karobar"],
    LoanPurpose.GOLD: ["gold", "jewellery", "jewelry", "sona", "gold loan"],
    LoanPurpose.HOME: ["home", "house", "flat", "apartment", "property", "ghar", "construction"],
}

# City patterns (major Indian cities)
INDIAN_CITIES = [
    "mumbai", "delhi", "bangalore", "bengaluru", "hyderabad", "ahmedabad",
    "chennai", "kolkata", "pune", "jaipur", "lucknow", "kanpur", "nagpur",
    "indore", "thane", "bhopal", "visakhapatnam", "patna", "vadodara",
    "ghaziabad", "ludhiana", "agra", "nashik", "faridabad", "meerut",
    "rajkot", "varanasi", "srinagar", "aurangabad", "dhanbad", "amritsar",
    "allahabad", "ranchi", "coimbatore", "jabalpur", "gwalior", "vijayawada",
    "jodhpur", "madurai", "raipur", "kochi", "chandigarh", "mysore",
    "surat", "noida", "gurgaon", "gurugram", "navi mumbai",
]


# ─── Extraction Functions ────────────────────────────────────

def extract_income(text: str) -> Optional[float]:
    """Extract monthly income from text."""
    text_lower = text.lower()

    for pattern in INCOME_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            amount_str = match.group(1).replace(",", "")
            try:
                amount = float(amount_str)

                # Handle "k" suffix
                if "k" in text_lower[match.start():match.end()].lower():
                    amount *= 1000

                # Handle "lakhs per annum" — convert to monthly
                if any(kw in text_lower[match.start():match.end()]
                       for kw in ["per annum", "per year", "annually", "p.a", "lpa"]):
                    amount = (amount * 100000) / 12  # lakhs to monthly

                # Handle "lakhs" without per annum (assume it's the amount itself)
                elif any(kw in text_lower[match.start():match.end()]
                         for kw in ["lakh", "lac", " l "]):
                    amount *= 100000

                return amount
            except ValueError:
                continue
    return None


def extract_loan_amount(text: str) -> Optional[float]:
    """Extract requested loan amount from text."""
    text_lower = text.lower()

    for pattern in LOAN_AMOUNT_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            amount_str = match.group(1).replace(",", "")
            try:
                amount = float(amount_str)

                # Check for lakhs
                full_match = text_lower[match.start():match.end()]
                if any(kw in full_match for kw in ["lakh", "lac", " l"]):
                    amount *= 100000

                return amount
            except ValueError:
                continue
    return None


def extract_age(text: str) -> Optional[int]:
    """Extract declared age from text."""
    for pattern in AGE_PATTERNS:
        match = re.search(pattern, text.lower())
        if match:
            age = int(match.group(1))
            if 18 <= age <= 80:
                return age
    return None


def extract_employment_type(text: str) -> Optional[str]:
    """Detect employment type from keywords."""
    text_lower = text.lower()
    for emp_type, keywords in EMPLOYMENT_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return emp_type
    return None


def extract_loan_purpose(text: str) -> Optional[LoanPurpose]:
    """Detect loan purpose from keywords."""
    text_lower = text.lower()
    scores = {}
    for purpose, keywords in PURPOSE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[purpose] = score

    if scores:
        return max(scores, key=scores.get)
    return None


def extract_city(text: str) -> Optional[str]:
    """Extract city name from text."""
    text_lower = text.lower()
    for city in INDIAN_CITIES:
        if city in text_lower:
            return city.title()
    return None


def extract_name_spacy(text: str) -> Optional[str]:
    """Extract person name using spaCy NER."""
    nlp = _load_spacy()
    if nlp is None:
        return None

    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            return ent.text
    return None


# ─── Main Extraction Pipeline ────────────────────────────────

async def extract_entities(transcript: str, existing: Optional[ExtractedEntities] = None) -> ExtractedEntities:
    """
    Extract all entities from a transcript chunk.
    Merges with existing entities (doesn't overwrite already-extracted data).
    
    Args:
        transcript: Text from STT
        existing: Previously extracted entities to merge with
    
    Returns:
        Updated ExtractedEntities
    """
    result = existing or ExtractedEntities()

    # Only update fields that are currently empty
    if not result.full_name:
        name = extract_name_spacy(transcript)
        if name:
            result.full_name = name

    if result.age_declared is None:
        age = extract_age(transcript)
        if age:
            result.age_declared = age

    if not result.employment_type:
        emp = extract_employment_type(transcript)
        if emp:
            result.employment_type = emp

    if result.monthly_income is None:
        income = extract_income(transcript)
        if income:
            result.monthly_income = income

    if result.loan_purpose is None:
        purpose = extract_loan_purpose(transcript)
        if purpose:
            result.loan_purpose = purpose

    if result.loan_amount_requested is None:
        amount = extract_loan_amount(transcript)
        if amount:
            result.loan_amount_requested = amount

    if not result.city:
        city = extract_city(transcript)
        if city:
            result.city = city

    # Log what we found
    filled = {k: v for k, v in result.model_dump().items() if v is not None}
    logger.info(f"Extracted entities: {filled}")

    return result


async def extract_employer_name(transcript: str) -> Optional[str]:
    """
    Try to extract employer/company name from text like:
    "I work at TCS" / "I'm employed with Infosys"
    """
    nlp = _load_spacy()
    if nlp is None:
        return None

    patterns = [
        r'(?:work|working|employed|job)\s+(?:at|with|in|for)\s+(.+?)(?:\.|,|$)',
        r'(?:company|employer|organization)\s+(?:is|name is)\s+(.+?)(?:\.|,|$)',
    ]

    for pattern in patterns:
        match = re.search(pattern, transcript, re.IGNORECASE)
        if match:
            company = match.group(1).strip()
            # Clean up common suffixes
            company = re.sub(r'\s+(and|where|since|from|for)\s+.*', '', company, flags=re.IGNORECASE)
            if len(company) > 2:
                return company

    # Fallback: try spaCy ORG entity
    doc = nlp(transcript)
    for ent in doc.ents:
        if ent.label_ == "ORG":
            return ent.text

    return None
