"""
models.py — Data models for LoanWizard AI
All Pydantic models that define the shape of data flowing through the system.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime
import uuid


# ─── Enums ────────────────────────────────────────────────────

class LoanPurpose(str, Enum):
    EDUCATION = "education"
    PERSONAL = "personal"
    BUSINESS = "business"
    GOLD = "gold"
    HOME = "home"
    OTHER = "other"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    REJECTED = "rejected"


class SessionStatus(str, Enum):
    INITIATED = "initiated"
    IN_PROGRESS = "in_progress"
    CONSENT_CAPTURED = "consent_captured"
    VERIFICATION_DONE = "verification_done"
    OFFER_GENERATED = "offer_generated"
    COMPLETED = "completed"
    DROPPED = "dropped"


class ConsentType(str, Enum):
    DATA_PROCESSING = "data_processing"
    CREDIT_CHECK = "credit_check"
    VIDEO_RECORDING = "video_recording"
    TERMS_AND_CONDITIONS = "terms_and_conditions"


# ─── Session ──────────────────────────────────────────────────

class SessionCreate(BaseModel):
    """Created when customer clicks the campaign link."""
    customer_name: Optional[str] = None
    phone: Optional[str] = None
    source_campaign: Optional[str] = "direct"


class Session(BaseModel):
    """Full session object stored in DB."""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: SessionStatus = SessionStatus.INITIATED
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    customer_name: Optional[str] = None
    phone: Optional[str] = None
    source_campaign: str = "direct"
    geo_location: Optional[dict] = None
    device_info: Optional[dict] = None


# ─── Speech-to-Text ──────────────────────────────────────────

class STTResult(BaseModel):
    """Result from Whisper transcription."""
    text: str
    language: str = "en"
    confidence: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# ─── NER Extraction ──────────────────────────────────────────

class ExtractedEntities(BaseModel):
    """Entities extracted from customer speech via NER + LLM."""
    full_name: Optional[str] = None
    age_declared: Optional[int] = None
    employment_type: Optional[str] = None       # salaried / self-employed / student
    employer_name: Optional[str] = None
    monthly_income: Optional[float] = None
    loan_purpose: Optional[LoanPurpose] = None
    loan_amount_requested: Optional[float] = None
    city: Optional[str] = None
    education_level: Optional[str] = None
    existing_loans: Optional[int] = None


# ─── Face Analysis ───────────────────────────────────────────

class FaceAnalysisResult(BaseModel):
    """Result from face detection + age estimation."""
    face_detected: bool = False
    estimated_age: Optional[int] = None
    age_confidence: float = 0.0
    liveness_score: float = 0.0         # 0-1, higher = more likely real
    face_match_consistent: bool = True  # face stays same throughout call
    age_mismatch_flag: bool = False     # declared age vs estimated age differ


# ─── Geo-location ────────────────────────────────────────────

class GeoLocation(BaseModel):
    """Customer's geo-location from browser."""
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    ip_address: Optional[str] = None


class GeoVerification(BaseModel):
    """Result of geo-location verification."""
    location: GeoLocation
    is_within_serviceable_area: bool = True
    location_mismatch_flag: bool = False   # declared city != geo city
    vpn_detected: bool = False


# ─── Consent ─────────────────────────────────────────────────

class ConsentRecord(BaseModel):
    """A single consent captured during the call."""
    consent_type: ConsentType
    granted: bool = False
    verbal_confirmation: Optional[str] = None   # exact words spoken
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# ─── Risk Assessment ─────────────────────────────────────────

class RiskAssessment(BaseModel):
    """Output of the risk engine."""
    risk_level: RiskLevel = RiskLevel.MEDIUM
    risk_score: float = 0.5             # 0-1, lower = less risky
    factors: List[str] = []             # ["stable_employment", "high_income"]
    red_flags: List[str] = []           # ["age_mismatch", "vpn_detected"]
    confidence: float = 0.5


# ─── Loan Offer ──────────────────────────────────────────────

class LoanOffer(BaseModel):
    """Personalized loan offer generated for the customer."""
    eligible: bool = True
    loan_amount_min: float = 0
    loan_amount_max: float = 0
    interest_rate: float = 0            # annual percentage
    tenure_months: List[int] = []       # e.g. [12, 24, 36, 48]
    emi_estimate: float = 0             # monthly EMI for default tenure
    processing_fee_percent: float = 1.0
    special_conditions: List[str] = []
    rejection_reason: Optional[str] = None


# ─── Audit Log ───────────────────────────────────────────────

class AuditEntry(BaseModel):
    """A single audit log entry."""
    entry_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    event_type: str               # "consent_captured", "face_verified", etc.
    event_data: dict = {}
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# ─── Full Application (auto-filled) ─────────────────────────

class LoanApplication(BaseModel):
    """The complete auto-filled loan application form."""
    session_id: str
    applicant: ExtractedEntities = ExtractedEntities()
    face_analysis: FaceAnalysisResult = FaceAnalysisResult()
    geo_verification: GeoVerification = GeoVerification(
        location=GeoLocation(latitude=0, longitude=0)
    )
    consents: List[ConsentRecord] = []
    risk_assessment: RiskAssessment = RiskAssessment()
    loan_offer: Optional[LoanOffer] = None
    conversation_transcript: List[STTResult] = []
    status: SessionStatus = SessionStatus.INITIATED
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ─── WebSocket Messages ──────────────────────────────────────

class WSMessage(BaseModel):
    """Message format for WebSocket communication."""
    type: str                     # "audio_chunk", "face_frame", "agent_response", etc.
    data: dict = {}
    session_id: Optional[str] = None
