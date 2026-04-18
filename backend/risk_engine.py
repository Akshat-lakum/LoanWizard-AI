"""
risk_engine.py — Risk Assessment & Policy Engine
Evaluates customer eligibility using policy rules + ML-based scoring.
Combines extracted entities, face analysis, and geo verification
to produce a risk assessment.
"""

import logging
from typing import List, Tuple
from models import (
    ExtractedEntities, FaceAnalysisResult, GeoVerification,
    RiskAssessment, RiskLevel, LoanPurpose, ConsentRecord
)

logger = logging.getLogger(__name__)


# ─── Policy Rules (Hard Rules) ───────────────────────────────

class PolicyEngine:
    """Hard policy rules that must be satisfied for eligibility."""

    # Minimum age by loan type
    MIN_AGE = {
        LoanPurpose.EDUCATION: 18,
        LoanPurpose.PERSONAL: 21,
        LoanPurpose.BUSINESS: 21,
        LoanPurpose.GOLD: 18,
        LoanPurpose.HOME: 21,
        LoanPurpose.OTHER: 21,
    }

    # Maximum age
    MAX_AGE = 60

    # Minimum monthly income by loan type
    MIN_INCOME = {
        LoanPurpose.EDUCATION: 0,          # Can be student (co-applicant covers)
        LoanPurpose.PERSONAL: 15000,
        LoanPurpose.BUSINESS: 20000,
        LoanPurpose.GOLD: 10000,
        LoanPurpose.HOME: 25000,
        LoanPurpose.OTHER: 15000,
    }

    # Maximum loan-to-income ratio (annual)
    MAX_LTI_RATIO = {
        LoanPurpose.EDUCATION: 15.0,       # Higher ratio allowed for education
        LoanPurpose.PERSONAL: 3.0,
        LoanPurpose.BUSINESS: 5.0,
        LoanPurpose.GOLD: 2.0,
        LoanPurpose.HOME: 8.0,
        LoanPurpose.OTHER: 3.0,
    }

    @staticmethod
    def check_eligibility(
        entities: ExtractedEntities
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Run hard policy checks.
        Returns: (eligible, passing_factors, rejection_reasons)
        """
        factors = []
        rejections = []
        purpose = entities.loan_purpose or LoanPurpose.OTHER

        # Age check
        if entities.age_declared is not None:
            min_age = PolicyEngine.MIN_AGE.get(purpose, 21)
            if entities.age_declared < min_age:
                rejections.append(f"age_below_minimum_{min_age}")
            elif entities.age_declared > PolicyEngine.MAX_AGE:
                rejections.append("age_above_maximum")
            else:
                factors.append("age_within_range")

        # Income check
        if entities.monthly_income is not None:
            min_income = PolicyEngine.MIN_INCOME.get(purpose, 15000)
            if entities.monthly_income < min_income and purpose != LoanPurpose.EDUCATION:
                rejections.append(f"income_below_minimum_{min_income}")
            else:
                factors.append("income_meets_threshold")

            # Loan-to-income ratio
            if entities.loan_amount_requested and entities.monthly_income > 0:
                annual_income = entities.monthly_income * 12
                ratio = entities.loan_amount_requested / annual_income
                max_ratio = PolicyEngine.MAX_LTI_RATIO.get(purpose, 3.0)
                if ratio > max_ratio:
                    rejections.append(f"loan_to_income_ratio_exceeded_{max_ratio}")
                else:
                    factors.append("healthy_loan_to_income_ratio")

        # Employment check (students need co-applicant for non-education loans)
        if entities.employment_type == "student" and purpose != LoanPurpose.EDUCATION:
            rejections.append("student_needs_coapplicant_for_non_education_loan")

        eligible = len(rejections) == 0
        return eligible, factors, rejections


# ─── Risk Scoring Model ─────────────────────────────────────

class RiskScorer:
    """
    ML-style risk scoring using weighted features.
    In production, this would be a trained model — here we use
    a transparent rule-based scorer for hackathon explainability.
    """

    # Feature weights (0-1, higher weight = more impact on risk)
    WEIGHTS = {
        "income_stability": 0.20,
        "loan_to_income": 0.15,
        "age_factor": 0.10,
        "employment_factor": 0.15,
        "face_verification": 0.15,
        "geo_verification": 0.10,
        "consent_completeness": 0.05,
        "conversation_quality": 0.10,
    }

    @staticmethod
    def compute_score(
        entities: ExtractedEntities,
        face_result: FaceAnalysisResult,
        geo_result: GeoVerification,
        consents: List[ConsentRecord],
        fraud_flags: List[str],
    ) -> Tuple[float, List[str], List[str]]:
        """
        Compute a risk score from 0 (no risk) to 1 (highest risk).
        Returns: (risk_score, positive_factors, red_flags)
        """
        score = 0.0
        factors = []
        red_flags = list(fraud_flags)  # Start with any conversation-based fraud flags
        weights = RiskScorer.WEIGHTS

        # 1. Income stability (0 = good income, 1 = no/low income)
        if entities.monthly_income:
            if entities.monthly_income >= 50000:
                score += 0 * weights["income_stability"]
                factors.append("high_stable_income")
            elif entities.monthly_income >= 25000:
                score += 0.3 * weights["income_stability"]
                factors.append("moderate_income")
            else:
                score += 0.7 * weights["income_stability"]
        else:
            score += 1.0 * weights["income_stability"]

        # 2. Loan-to-income ratio
        if entities.monthly_income and entities.loan_amount_requested:
            annual = entities.monthly_income * 12
            ratio = entities.loan_amount_requested / annual if annual > 0 else 10
            if ratio <= 1.5:
                score += 0 * weights["loan_to_income"]
                factors.append("conservative_loan_amount")
            elif ratio <= 3:
                score += 0.3 * weights["loan_to_income"]
            elif ratio <= 5:
                score += 0.6 * weights["loan_to_income"]
            else:
                score += 1.0 * weights["loan_to_income"]
                red_flags.append("high_loan_to_income_ratio")

        # 3. Age factor (prime working age = lower risk)
        if entities.age_declared:
            if 25 <= entities.age_declared <= 45:
                score += 0 * weights["age_factor"]
                factors.append("prime_working_age")
            elif 21 <= entities.age_declared < 25 or 45 < entities.age_declared <= 55:
                score += 0.3 * weights["age_factor"]
            else:
                score += 0.7 * weights["age_factor"]

        # 4. Employment factor
        emp = entities.employment_type
        if emp == "salaried":
            score += 0 * weights["employment_factor"]
            factors.append("salaried_employment")
        elif emp == "self_employed":
            score += 0.4 * weights["employment_factor"]
            factors.append("self_employed")
        elif emp == "student":
            score += 0.6 * weights["employment_factor"]
        else:
            score += 0.8 * weights["employment_factor"]

        # 5. Face verification
        if face_result.face_detected:
            if face_result.liveness_score > 0.7:
                score += 0 * weights["face_verification"]
                factors.append("strong_liveness_verified")
            elif face_result.liveness_score > 0.4:
                score += 0.3 * weights["face_verification"]
                factors.append("moderate_liveness")
            else:
                score += 0.8 * weights["face_verification"]
                red_flags.append("low_liveness_score")

            if face_result.age_mismatch_flag:
                score += 0.5 * weights["face_verification"]
                red_flags.append("declared_vs_estimated_age_mismatch")

            if not face_result.face_match_consistent:
                red_flags.append("face_changed_during_call")
                score += 0.8 * weights["face_verification"]
        else:
            score += 1.0 * weights["face_verification"]
            red_flags.append("no_face_detected")

        # 6. Geo verification
        if geo_result.location_mismatch_flag:
            score += 0.8 * weights["geo_verification"]
            red_flags.append("location_mismatch")
        elif geo_result.vpn_detected:
            score += 0.6 * weights["geo_verification"]
            red_flags.append("vpn_detected")
        elif geo_result.is_within_serviceable_area:
            score += 0 * weights["geo_verification"]
            factors.append("location_verified")
        else:
            score += 0.5 * weights["geo_verification"]

        # 7. Consent completeness
        granted = sum(1 for c in consents if c.granted)
        total = max(len(consents), 1)
        consent_ratio = granted / total
        score += (1 - consent_ratio) * weights["consent_completeness"]
        if consent_ratio >= 0.8:
            factors.append("all_consents_granted")

        # 8. Conversation quality (fraud flags from LLM analysis)
        if len(fraud_flags) == 0:
            score += 0 * weights["conversation_quality"]
            factors.append("clean_conversation")
        else:
            score += min(len(fraud_flags) * 0.3, 1.0) * weights["conversation_quality"]

        # Clamp to 0-1
        score = max(0, min(1, score))

        return score, factors, red_flags


# ─── Main Assessment Function ────────────────────────────────

async def assess_risk(
    entities: ExtractedEntities,
    face_result: FaceAnalysisResult,
    geo_result: GeoVerification,
    consents: List[ConsentRecord],
    fraud_flags: List[str],
) -> RiskAssessment:
    """
    Full risk assessment combining policy rules and risk scoring.
    
    Returns:
        RiskAssessment with risk level, score, factors, and red flags
    """
    # Step 1: Policy check (hard rules)
    eligible, policy_factors, rejections = PolicyEngine.check_eligibility(entities)

    if not eligible:
        return RiskAssessment(
            risk_level=RiskLevel.REJECTED,
            risk_score=1.0,
            factors=policy_factors,
            red_flags=rejections,
            confidence=0.9
        )

    # Step 2: Risk scoring (soft signals)
    risk_score, score_factors, score_flags = RiskScorer.compute_score(
        entities, face_result, geo_result, consents, fraud_flags
    )

    # Combine factors
    all_factors = policy_factors + score_factors
    all_flags = rejections + score_flags

    # Determine risk level from score
    if risk_score < 0.25:
        level = RiskLevel.LOW
    elif risk_score < 0.55:
        level = RiskLevel.MEDIUM
    elif risk_score < 0.8:
        level = RiskLevel.HIGH
    else:
        level = RiskLevel.REJECTED

    # Confidence based on data completeness
    filled_fields = sum(1 for v in entities.model_dump().values() if v is not None)
    total_fields = 8  # key fields we track
    data_confidence = filled_fields / total_fields
    face_confidence = 0.3 if face_result.face_detected else 0
    confidence = min(1.0, data_confidence * 0.6 + face_confidence + 0.1)

    assessment = RiskAssessment(
        risk_level=level,
        risk_score=round(risk_score, 3),
        factors=all_factors,
        red_flags=all_flags,
        confidence=round(confidence, 2)
    )

    logger.info(
        f"Risk assessment: level={level}, score={risk_score:.3f}, "
        f"factors={len(all_factors)}, flags={len(all_flags)}"
    )

    return assessment
