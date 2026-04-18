"""
audit_logger.py — Audit & Compliance Logger
Maintains a complete audit trail of the entire loan onboarding session.
Stores video recordings references, transcripts, consents, decisions,
and all verification results for regulatory compliance.
"""

import json
import os
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from models import (
    AuditEntry, Session, ConsentRecord, FaceAnalysisResult,
    GeoVerification, RiskAssessment, LoanOffer, ExtractedEntities,
    STTResult, LoanApplication
)

logger = logging.getLogger(__name__)

# ─── In-Memory Store (SQLite in production) ──────────────────

_audit_store: Dict[str, List[AuditEntry]] = {}
_sessions: Dict[str, Session] = {}
_applications: Dict[str, LoanApplication] = {}


# ─── Session Management ──────────────────────────────────────

def create_session(session: Session) -> Session:
    """Register a new session."""
    _sessions[session.session_id] = session
    _applications[session.session_id] = LoanApplication(
        session_id=session.session_id
    )
    log_event(session.session_id, "session_created", {
        "source_campaign": session.source_campaign,
        "customer_name": session.customer_name,
    })
    logger.info(f"Session created: {session.session_id}")
    return session


def get_session(session_id: str) -> Optional[Session]:
    """Retrieve a session."""
    return _sessions.get(session_id)


def get_application(session_id: str) -> Optional[LoanApplication]:
    """Retrieve the full application for a session."""
    return _applications.get(session_id)


def update_application(session_id: str, **kwargs) -> Optional[LoanApplication]:
    """Update fields on the loan application."""
    app = _applications.get(session_id)
    if not app:
        return None

    for key, value in kwargs.items():
        if hasattr(app, key):
            setattr(app, key, value)

    return app


# ─── Event Logging ───────────────────────────────────────────

def log_event(session_id: str, event_type: str, event_data: Dict[str, Any] = {}) -> AuditEntry:
    """
    Log an audit event.
    Every significant action in the session gets logged here.
    """
    entry = AuditEntry(
        session_id=session_id,
        event_type=event_type,
        event_data=_sanitize_data(event_data),
    )

    if session_id not in _audit_store:
        _audit_store[session_id] = []
    _audit_store[session_id].append(entry)

    logger.debug(f"Audit [{session_id[:8]}]: {event_type}")
    return entry


def _sanitize_data(data: Dict) -> Dict:
    """Remove any sensitive data that shouldn't be in audit logs."""
    sanitized = {}
    sensitive_keys = {"aadhaar", "pan", "password", "otp", "pin"}

    for key, value in data.items():
        if key.lower() in sensitive_keys:
            sanitized[key] = "***REDACTED***"
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_data(value)
        else:
            sanitized[key] = value

    return sanitized


# ─── Specific Event Loggers ──────────────────────────────────

def log_transcript(session_id: str, stt_result: STTResult):
    """Log a speech-to-text transcription."""
    log_event(session_id, "transcript_captured", {
        "text": stt_result.text,
        "language": stt_result.language,
        "confidence": stt_result.confidence,
    })

    # Also append to application transcript
    app = _applications.get(session_id)
    if app:
        app.conversation_transcript.append(stt_result)


def log_consent(session_id: str, consent: ConsentRecord):
    """Log a consent event."""
    log_event(session_id, "consent_captured", {
        "consent_type": consent.consent_type,
        "granted": consent.granted,
        "verbal_confirmation": consent.verbal_confirmation,
    })

    # Append to application consents
    app = _applications.get(session_id)
    if app:
        app.consents.append(consent)


def log_face_analysis(session_id: str, result: FaceAnalysisResult):
    """Log face analysis results."""
    log_event(session_id, "face_analyzed", result.model_dump())

    app = _applications.get(session_id)
    if app:
        app.face_analysis = result


def log_geo_verification(session_id: str, result: GeoVerification):
    """Log geo-location verification."""
    log_event(session_id, "geo_verified", result.model_dump())

    app = _applications.get(session_id)
    if app:
        app.geo_verification = result


def log_entities_extracted(session_id: str, entities: ExtractedEntities):
    """Log extracted entities."""
    log_event(session_id, "entities_extracted", entities.model_dump())

    app = _applications.get(session_id)
    if app:
        app.applicant = entities


def log_risk_assessment(session_id: str, assessment: RiskAssessment):
    """Log risk assessment."""
    log_event(session_id, "risk_assessed", assessment.model_dump())

    app = _applications.get(session_id)
    if app:
        app.risk_assessment = assessment


def log_offer_generated(session_id: str, offer: LoanOffer):
    """Log offer generation."""
    log_event(session_id, "offer_generated", offer.model_dump())

    app = _applications.get(session_id)
    if app:
        app.loan_offer = offer


def log_video_reference(session_id: str, video_path: str, duration_seconds: float):
    """Log reference to the recorded video file."""
    log_event(session_id, "video_recorded", {
        "video_path": video_path,
        "duration_seconds": duration_seconds,
    })


# ─── Retrieval ───────────────────────────────────────────────

def get_audit_trail(session_id: str) -> List[AuditEntry]:
    """Get complete audit trail for a session."""
    return _audit_store.get(session_id, [])


def get_audit_summary(session_id: str) -> Dict:
    """Get a summary of audit events for a session."""
    trail = get_audit_trail(session_id)
    app = get_application(session_id)

    if not trail:
        return {"error": "Session not found"}

    event_types = [e.event_type for e in trail]

    summary = {
        "session_id": session_id,
        "total_events": len(trail),
        "event_timeline": [
            {"type": e.event_type, "timestamp": e.timestamp}
            for e in trail
        ],
        "consents_captured": sum(1 for t in event_types if t == "consent_captured"),
        "transcripts_captured": sum(1 for t in event_types if t == "transcript_captured"),
        "face_verified": "face_analyzed" in event_types,
        "geo_verified": "geo_verified" in event_types,
        "risk_assessed": "risk_assessed" in event_types,
        "offer_generated": "offer_generated" in event_types,
        "session_start": trail[0].timestamp if trail else None,
        "session_end": trail[-1].timestamp if trail else None,
    }

    if app:
        summary["application_status"] = app.status.value
        summary["risk_level"] = app.risk_assessment.risk_level.value if app.risk_assessment else None

    return summary


# ─── Export (for regulatory submission) ──────────────────────

def export_session_json(session_id: str) -> Optional[str]:
    """Export complete session data as JSON for compliance."""
    app = get_application(session_id)
    trail = get_audit_trail(session_id)

    if not app:
        return None

    export = {
        "application": app.model_dump(),
        "audit_trail": [e.model_dump() for e in trail],
        "exported_at": datetime.now().isoformat(),
    }

    return json.dumps(export, indent=2, default=str)


def get_all_sessions() -> List[Dict]:
    """Get list of all sessions (for admin dashboard)."""
    sessions = []
    for sid, session in _sessions.items():
        app = _applications.get(sid)
        sessions.append({
            "session_id": sid,
            "status": session.status.value,
            "customer_name": session.customer_name,
            "created_at": session.created_at,
            "has_offer": app.loan_offer is not None if app else False,
        })
    return sessions
