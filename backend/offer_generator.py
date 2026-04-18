"""
offer_generator.py — Dynamic Loan Offer Generation
Creates personalized loan offers based on customer profile,
risk assessment, and policy parameters.
"""

import math
import logging
from typing import List, Optional
from models import (
    ExtractedEntities, RiskAssessment, RiskLevel,
    LoanOffer, LoanPurpose
)

logger = logging.getLogger(__name__)


# ─── Loan Product Configurations ─────────────────────────────

LOAN_PRODUCTS = {
    LoanPurpose.EDUCATION: {
        "name": "Education Loan",
        "base_rate": 10.5,          # base interest rate %
        "min_amount": 100000,       # ₹1 lakh
        "max_amount": 5000000,      # ₹50 lakhs
        "tenures": [12, 24, 36, 48, 60, 72, 84],
        "default_tenure": 48,
        "processing_fee": 0.5,
        "max_ltv": 0.90,            # can finance 90% of cost
    },
    LoanPurpose.PERSONAL: {
        "name": "Personal Loan",
        "base_rate": 12.0,
        "min_amount": 50000,
        "max_amount": 2500000,
        "tenures": [6, 12, 18, 24, 36, 48],
        "default_tenure": 24,
        "processing_fee": 1.5,
        "max_ltv": 1.0,
    },
    LoanPurpose.BUSINESS: {
        "name": "Business Loan",
        "base_rate": 14.0,
        "min_amount": 100000,
        "max_amount": 5000000,
        "tenures": [12, 24, 36, 48, 60],
        "default_tenure": 36,
        "processing_fee": 2.0,
        "max_ltv": 0.85,
    },
    LoanPurpose.GOLD: {
        "name": "Gold Loan",
        "base_rate": 9.5,
        "min_amount": 25000,
        "max_amount": 2500000,
        "tenures": [3, 6, 12, 18, 24],
        "default_tenure": 12,
        "processing_fee": 0.5,
        "max_ltv": 0.75,
    },
    LoanPurpose.HOME: {
        "name": "Home Loan",
        "base_rate": 8.5,
        "min_amount": 500000,
        "max_amount": 50000000,
        "tenures": [60, 120, 180, 240, 300, 360],
        "default_tenure": 240,
        "processing_fee": 0.5,
        "max_ltv": 0.80,
    },
    LoanPurpose.OTHER: {
        "name": "Personal Loan",
        "base_rate": 13.0,
        "min_amount": 50000,
        "max_amount": 1500000,
        "tenures": [6, 12, 18, 24, 36],
        "default_tenure": 24,
        "processing_fee": 1.5,
        "max_ltv": 1.0,
    },
}


# ─── Interest Rate Adjustment ────────────────────────────────

def calculate_interest_rate(
    base_rate: float,
    risk: RiskAssessment,
    entities: ExtractedEntities,
) -> float:
    """
    Adjust base interest rate based on risk profile.
    Lower risk = better (lower) rate.
    """
    rate = base_rate

    # Risk-based adjustment
    if risk.risk_level == RiskLevel.LOW:
        rate -= 1.0      # Reward low risk
    elif risk.risk_level == RiskLevel.MEDIUM:
        rate += 0.5
    elif risk.risk_level == RiskLevel.HIGH:
        rate += 2.0

    # Income-based adjustment
    if entities.monthly_income:
        if entities.monthly_income >= 100000:
            rate -= 0.5   # Premium customer discount
        elif entities.monthly_income >= 50000:
            rate -= 0.25

    # Employment stability adjustment
    if entities.employment_type == "salaried":
        rate -= 0.25
    elif entities.employment_type == "self_employed":
        rate += 0.5

    # Floor at base_rate - 2, ceiling at base_rate + 4
    rate = max(base_rate - 2.0, min(base_rate + 4.0, rate))

    return round(rate, 2)


# ─── EMI Calculation ─────────────────────────────────────────

def calculate_emi(principal: float, annual_rate: float, months: int) -> float:
    """
    Calculate EMI using the standard formula:
    EMI = P * r * (1+r)^n / ((1+r)^n - 1)
    where r = monthly rate, n = months
    """
    if annual_rate <= 0 or months <= 0 or principal <= 0:
        return 0

    r = annual_rate / (12 * 100)   # Monthly interest rate
    n = months

    emi = principal * r * math.pow(1 + r, n) / (math.pow(1 + r, n) - 1)
    return round(emi, 2)


# ─── Eligible Amount Calculation ─────────────────────────────

def calculate_max_eligible_amount(
    monthly_income: float,
    existing_emi: float,
    annual_rate: float,
    tenure_months: int,
    max_foir: float = 0.50,   # Fixed Obligations to Income Ratio
) -> float:
    """
    Calculate maximum loan amount based on income and obligations.
    FOIR = (Existing EMI + New EMI) / Monthly Income <= 50%
    """
    if monthly_income <= 0 or annual_rate <= 0:
        return 0

    # Maximum EMI the customer can afford
    max_new_emi = (monthly_income * max_foir) - existing_emi

    if max_new_emi <= 0:
        return 0

    # Reverse-calculate principal from EMI
    r = annual_rate / (12 * 100)
    n = tenure_months

    if r <= 0:
        return max_new_emi * n

    max_principal = max_new_emi * (math.pow(1 + r, n) - 1) / (r * math.pow(1 + r, n))

    return round(max_principal, 0)


# ─── Main Offer Generation ───────────────────────────────────

async def generate_offer(
    entities: ExtractedEntities,
    risk: RiskAssessment,
) -> LoanOffer:
    """
    Generate a personalized loan offer based on customer profile and risk.
    
    Returns:
        LoanOffer with amount range, rate, tenure options, and EMI
    """
    # Check if rejected by risk engine
    if risk.risk_level == RiskLevel.REJECTED:
        return LoanOffer(
            eligible=False,
            rejection_reason=f"Application could not be approved: {', '.join(risk.red_flags[:3])}"
        )

    # Get product configuration
    purpose = entities.loan_purpose or LoanPurpose.OTHER
    product = LOAN_PRODUCTS.get(purpose, LOAN_PRODUCTS[LoanPurpose.OTHER])

    # Calculate interest rate
    interest_rate = calculate_interest_rate(product["base_rate"], risk, entities)

    # Determine loan amount range
    requested = entities.loan_amount_requested or product["min_amount"]
    monthly_income = entities.monthly_income or 0

    # Calculate max eligible amount (if income available)
    if monthly_income > 0:
        max_eligible = calculate_max_eligible_amount(
            monthly_income=monthly_income,
            existing_emi=0,     # Simplified — no existing loan data
            annual_rate=interest_rate,
            tenure_months=product["default_tenure"],
        )
    else:
        max_eligible = product["max_amount"]

    # Apply product limits
    loan_max = min(max_eligible, product["max_amount"])
    loan_min = max(product["min_amount"], loan_max * 0.3)  # Offer at least 30% of max

    # If requested amount is within range, use it
    if requested > loan_max:
        loan_max = loan_max   # Can't offer more than eligible
    elif requested < loan_min:
        loan_min = product["min_amount"]

    # Ensure min < max
    if loan_min > loan_max:
        loan_min = loan_max * 0.5

    # Risk-based amount adjustment
    if risk.risk_level == RiskLevel.HIGH:
        loan_max *= 0.7   # Reduce max by 30% for high risk
        loan_min = min(loan_min, loan_max * 0.5)

    # Calculate default EMI
    default_amount = min(requested, loan_max) if requested > 0 else loan_max * 0.7
    default_tenure = product["default_tenure"]
    emi = calculate_emi(default_amount, interest_rate, default_tenure)

    # Special conditions based on risk
    conditions = []
    if risk.risk_level == RiskLevel.HIGH:
        conditions.append("Subject to additional document verification")
        conditions.append("Co-applicant may be required")
    if risk.risk_level == RiskLevel.MEDIUM:
        conditions.append("Subject to income proof verification")
    if purpose == LoanPurpose.EDUCATION:
        conditions.append("Moratorium period of 6 months available after course completion")
    if entities.employment_type == "salaried" and monthly_income >= 50000:
        conditions.append("Pre-approved — minimal documentation required")

    offer = LoanOffer(
        eligible=True,
        loan_amount_min=round(loan_min, 0),
        loan_amount_max=round(loan_max, 0),
        interest_rate=interest_rate,
        tenure_months=product["tenures"],
        emi_estimate=emi,
        processing_fee_percent=product["processing_fee"],
        special_conditions=conditions,
    )

    logger.info(
        f"Offer generated: ₹{loan_min:,.0f}-₹{loan_max:,.0f} @ {interest_rate}%, "
        f"EMI ₹{emi:,.0f} for {default_tenure} months"
    )

    return offer
