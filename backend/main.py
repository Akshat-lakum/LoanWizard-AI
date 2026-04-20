"""
main.py — LoanWizard AI Backend Server
FastAPI server with REST and WebSocket endpoints for the video call onboarding system.

Run: uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

import json
import logging
import asyncio
import base64
from typing import Optional, Dict, List
from datetime import datetime
from pathlib import Path

# Load .env file BEFORE anything else reads env vars
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse

from pydantic import BaseModel

from models import (
    SessionCreate, Session, SessionStatus, STTResult,
    ExtractedEntities, FaceAnalysisResult, GeoLocation, GeoVerification,
    ConsentRecord, ConsentType, RiskAssessment, LoanOffer,
    LoanApplication, WSMessage
)
from stt_engine import transcribe_audio, is_speech_present
from face_analyzer import analyze_face, analyze_frame_quick, clear_tracker
from ner_extractor import extract_entities, extract_employer_name
from llm_orchestrator import generate_agent_response, verify_consent, analyze_conversation_for_fraud
from risk_engine import assess_risk
from offer_generator import generate_offer
import audit_logger

# ─── Logging ─────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger("loanwizard")

# ─── App Setup ───────────────────────────────────────────────

app = FastAPI(
    title="LoanWizard AI",
    description="Agentic AI Video Call-Based Loan Onboarding System",
    version="1.0.0",
)

# CORS — allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # In production, restrict to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── In-Memory State (per session) ───────────────────────────

active_sessions: Dict[str, dict] = {}


def get_session_state(session_id: str) -> dict:
    """Get or create session state."""
    if session_id not in active_sessions:
        active_sessions[session_id] = {
            "entities": ExtractedEntities(),
            "conversation": [],
            "face_results": [],
            "consents": [],
            "status": SessionStatus.INITIATED,
        }
    return active_sessions[session_id]


# ═══════════════════════════════════════════════════════════════
# REST ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    """Serve the frontend HTML."""
    import os
    from pathlib import Path
    
    # Try multiple paths to find index.html
    candidates = [
        Path(__file__).parent.parent / "frontend" / "index.html",       # ../frontend/
        Path(__file__).parent / ".." / "frontend" / "index.html",       # relative
        Path.cwd().parent / "frontend" / "index.html",                  # from CWD
        Path.cwd() / "frontend" / "index.html",                        # frontend in CWD
        Path.cwd() / ".." / "frontend" / "index.html",                 # up one level
    ]
    
    for p in candidates:
        resolved = p.resolve()
        if resolved.exists():
            logger.info(f"Serving frontend from: {resolved}")
            return FileResponse(str(resolved), media_type='text/html')
    
    # Log what we tried so you can debug
    logger.warning(f"index.html not found. Tried: {[str(p.resolve()) for p in candidates]}")
    logger.warning(f"Current working directory: {Path.cwd()}")
    
    return {"service": "LoanWizard AI", "status": "running", "version": "1.0.0",
            "note": "Frontend index.html not found. Make sure frontend/index.html exists next to the backend/ folder."}


# ─── Session Management ──────────────────────────────────────

@app.post("/api/session/create", response_model=Session)
async def create_session(data: SessionCreate):
    """Create a new onboarding session (triggered when customer clicks campaign link)."""
    session = Session(
        customer_name=data.customer_name,
        phone=data.phone,
        source_campaign=data.source_campaign or "direct",
    )
    audit_logger.create_session(session)
    get_session_state(session.session_id)
    logger.info(f"New session: {session.session_id}")
    return session


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """Get session details and current application state."""
    session = audit_logger.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    app_data = audit_logger.get_application(session_id)
    state = get_session_state(session_id)

    return {
        "session": session.model_dump(),
        "entities": state["entities"].model_dump(),
        "status": state["status"].value,
        "conversation_length": len(state["conversation"]),
    }


# ─── Speech Processing ──────────────────────────────────────

@app.post("/api/stt/transcribe")
async def transcribe_endpoint(
    audio: UploadFile = File(...),
    session_id: str = ""
):
    """
    Transcribe an audio file/chunk.
    Accepts WAV or raw PCM audio.
    """
    audio_bytes = await audio.read()

    # Check for voice activity
    if not is_speech_present(audio_bytes):
        return {"text": "", "language": "en", "has_speech": False}

    result = await transcribe_audio(audio_bytes)

    if session_id and result.text:
        audit_logger.log_transcript(session_id, result)

    return {
        "text": result.text,
        "language": result.language,
        "confidence": result.confidence,
        "has_speech": True,
    }


# ─── Entity Extraction ──────────────────────────────────────

@app.post("/api/ner/extract")
async def extract_entities_endpoint(
    session_id: str,
    transcript: str,
):
    """Extract entities from a transcript and merge with existing data."""
    state = get_session_state(session_id)
    entities = await extract_entities(transcript, state["entities"])
    state["entities"] = entities
    audit_logger.log_entities_extracted(session_id, entities)

    return entities.model_dump()


# ─── Face Analysis ───────────────────────────────────────────

class FaceAnalyzeRequest(BaseModel):
    session_id: str
    frame_base64: str
    declared_age: Optional[int] = None

@app.post("/api/face/analyze")
async def analyze_face_endpoint(req: FaceAnalyzeRequest):
    """Analyze a video frame for face detection, age, and liveness."""
    result = await analyze_face(req.frame_base64, req.session_id, req.declared_age)
    audit_logger.log_face_analysis(req.session_id, result)
    return result.model_dump()


class QuickFaceRequest(BaseModel):
    frame_base64: str

@app.post("/api/face/quick")
async def quick_face_check(req: QuickFaceRequest):
    """Quick face detection — for real-time UI feedback."""
    return await analyze_frame_quick(req.frame_base64)


# ─── Geo-location ───────────────────────────────────────────

class GeoVerifyRequest(BaseModel):
    session_id: str
    location: GeoLocation

@app.post("/api/geo/verify")
async def verify_geo(req: GeoVerifyRequest):
    """Verify customer's geo-location."""
    verification = GeoVerification(
        location=req.location,
        is_within_serviceable_area=req.location.country in [None, "India", "IN"],
        location_mismatch_flag=False,
        vpn_detected=False,
    )

    state = get_session_state(req.session_id)
    entities = state["entities"]

    if entities.city and req.location.city:
        declared = entities.city.lower()
        geo = req.location.city.lower()
        if declared != geo and declared not in geo and geo not in declared:
            verification.location_mismatch_flag = True

    audit_logger.log_geo_verification(req.session_id, verification)
    return verification.model_dump()


# ─── Consent Capture ─────────────────────────────────────────

class ConsentCaptureRequest(BaseModel):
    session_id: str
    consent_type: str
    verbal_response: str

@app.post("/api/consent/capture")
async def capture_consent(req: ConsentCaptureRequest):
    """Capture and verify customer consent."""
    granted = await verify_consent(req.verbal_response)

    consent = ConsentRecord(
        consent_type=ConsentType(req.consent_type),
        granted=granted,
        verbal_confirmation=req.verbal_response,
    )

    audit_logger.log_consent(req.session_id, consent)

    state = get_session_state(req.session_id)
    state["consents"].append(consent)

    return {
        "consent_type": req.consent_type,
        "granted": granted,
        "verbal_response": req.verbal_response,
    }


# ─── LLM Agent Response ─────────────────────────────────────

class AgentRespondRequest(BaseModel):
    session_id: str
    customer_message: str
    language: str = "en"

@app.post("/api/agent/respond")
async def agent_respond(req: AgentRespondRequest):
    """
    Generate the AI agent's next response.
    This is the core conversation engine endpoint.
    """
    state = get_session_state(req.session_id)

    # First, extract entities from what the customer said
    state["entities"] = await extract_entities(req.customer_message, state["entities"])

    # Generate agent response
    response = await generate_agent_response(
        transcript=req.customer_message,
        entities=state["entities"],
        conversation_history=state["conversation"],
        language=req.language,
    )

    # Update conversation history
    state["conversation"].append({"role": "user", "content": req.customer_message})
    state["conversation"].append({"role": "assistant", "content": response})

    # Log
    audit_logger.log_event(req.session_id, "agent_responded", {
        "customer_said": req.customer_message,
        "agent_said": response,
    })

    return {
        "response": response,
        "entities": state["entities"].model_dump(),
        "conversation_step": len(state["conversation"]) // 2,
    }


# ─── Risk & Offer ───────────────────────────────────────────

class SessionRequest(BaseModel):
    session_id: str

@app.post("/api/risk/assess")
async def assess_risk_endpoint(req: SessionRequest):
    """Run full risk assessment for the session."""
    state = get_session_state(req.session_id)
    app_data = audit_logger.get_application(req.session_id)

    face_result = app_data.face_analysis if app_data else FaceAnalysisResult()
    geo_result = app_data.geo_verification if app_data else GeoVerification(
        location=GeoLocation(latitude=0, longitude=0)
    )

    fraud_flags = await analyze_conversation_for_fraud(
        state["conversation"], state["entities"]
    )

    assessment = await assess_risk(
        entities=state["entities"],
        face_result=face_result,
        geo_result=geo_result,
        consents=state["consents"],
        fraud_flags=fraud_flags,
    )

    audit_logger.log_risk_assessment(req.session_id, assessment)
    return assessment.model_dump()


@app.post("/api/offer/generate")
async def generate_offer_endpoint(req: SessionRequest):
    """Generate personalized loan offer."""
    state = get_session_state(req.session_id)
    app_data = audit_logger.get_application(req.session_id)

    face_result = app_data.face_analysis if app_data else FaceAnalysisResult()
    geo_result = app_data.geo_verification if app_data else GeoVerification(
        location=GeoLocation(latitude=0, longitude=0)
    )
    fraud_flags = await analyze_conversation_for_fraud(
        state["conversation"], state["entities"]
    )
    risk = await assess_risk(
        state["entities"], face_result, geo_result,
        state["consents"], fraud_flags
    )

    offer = await generate_offer(state["entities"], risk)

    audit_logger.log_risk_assessment(req.session_id, risk)
    audit_logger.log_offer_generated(req.session_id, offer)

    state["status"] = SessionStatus.OFFER_GENERATED

    return {
        "offer": offer.model_dump(),
        "risk": risk.model_dump(),
    }


# ─── Audit & Admin ──────────────────────────────────────────

@app.get("/api/audit/{session_id}")
async def get_audit(session_id: str):
    """Get complete audit trail for a session."""
    return audit_logger.get_audit_summary(session_id)


@app.get("/api/audit/{session_id}/export")
async def export_audit(session_id: str):
    """Export full session data as JSON."""
    data = audit_logger.export_session_json(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found")
    return JSONResponse(content=json.loads(data))


@app.get("/api/sessions")
async def list_sessions():
    """List all sessions (admin endpoint)."""
    return audit_logger.get_all_sessions()


# ═══════════════════════════════════════════════════════════════
# WEBSOCKET — Real-time video call communication
# ═══════════════════════════════════════════════════════════════

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket for real-time bidirectional communication during the video call.
    
    Message types from client:
    - audio_chunk: Raw audio for STT
    - video_frame: Base64 frame for face analysis
    - geo_update: Geo-location update
    - text_input: Text fallback (if mic fails)
    - consent_response: Consent verbal confirmation
    
    Message types to client:
    - agent_response: AI agent's text response (for TTS)
    - face_status: Real-time face detection feedback
    - entities_update: Currently extracted entities
    - offer_ready: Loan offer generated
    - error: Error message
    """
    await websocket.accept()
    logger.info(f"WebSocket connected: {session_id}")

    state = get_session_state(session_id)
    state["status"] = SessionStatus.IN_PROGRESS
    audit_logger.log_event(session_id, "video_call_started")

    # Send initial greeting
    greeting = await generate_agent_response(
        transcript="",
        entities=state["entities"],
        conversation_history=[],
        language="en",
    )
    await websocket.send_json({
        "type": "agent_response",
        "data": {"text": greeting, "step": 0}
    })
    state["conversation"].append({"role": "assistant", "content": greeting})

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type", "")

            # ── Audio Chunk (STT) ──
            if msg_type == "audio_chunk":
                audio_b64 = msg["data"].get("audio", "")
                audio_bytes = base64.b64decode(audio_b64)

                if is_speech_present(audio_bytes):
                    stt_result = await transcribe_audio(audio_bytes)

                    if stt_result.text.strip():
                        audit_logger.log_transcript(session_id, stt_result)

                        # Extract entities
                        state["entities"] = await extract_entities(
                            stt_result.text, state["entities"]
                        )

                        # Generate agent response
                        response = await generate_agent_response(
                            transcript=stt_result.text,
                            entities=state["entities"],
                            conversation_history=state["conversation"],
                            language=stt_result.language,
                        )

                        state["conversation"].append({"role": "user", "content": stt_result.text})
                        state["conversation"].append({"role": "assistant", "content": response})

                        await websocket.send_json({
                            "type": "agent_response",
                            "data": {
                                "text": response,
                                "customer_said": stt_result.text,
                                "step": len(state["conversation"]) // 2,
                            }
                        })

                        # Send updated entities
                        await websocket.send_json({
                            "type": "entities_update",
                            "data": state["entities"].model_dump()
                        })

            # ── Text Input (fallback) ──
            elif msg_type == "text_input":
                text = msg["data"].get("text", "")
                if text.strip():
                    state["entities"] = await extract_entities(text, state["entities"])

                    response = await generate_agent_response(
                        transcript=text,
                        entities=state["entities"],
                        conversation_history=state["conversation"],
                        language="en",
                    )

                    state["conversation"].append({"role": "user", "content": text})
                    state["conversation"].append({"role": "assistant", "content": response})

                    await websocket.send_json({
                        "type": "agent_response",
                        "data": {"text": response, "step": len(state["conversation"]) // 2}
                    })
                    await websocket.send_json({
                        "type": "entities_update",
                        "data": state["entities"].model_dump()
                    })

            # ── Video Frame (Face Analysis) ──
            elif msg_type == "video_frame":
                frame_b64 = msg["data"].get("frame", "")
                declared_age = state["entities"].age_declared

                result = await analyze_face(frame_b64, session_id, declared_age)
                audit_logger.log_face_analysis(session_id, result)

                await websocket.send_json({
                    "type": "face_status",
                    "data": result.model_dump()
                })

            # ── Geo-location ──
            elif msg_type == "geo_update":
                geo = GeoLocation(**msg["data"])
                verification = GeoVerification(
                    location=geo,
                    is_within_serviceable_area=True,
                )
                audit_logger.log_geo_verification(session_id, verification)

                await websocket.send_json({
                    "type": "geo_verified",
                    "data": verification.model_dump()
                })

            # ── Generate Offer ──
            elif msg_type == "generate_offer":
                app_data = audit_logger.get_application(session_id)
                face_result = app_data.face_analysis if app_data else FaceAnalysisResult()
                geo_result = app_data.geo_verification if app_data else GeoVerification(
                    location=GeoLocation(latitude=0, longitude=0)
                )

                fraud_flags = await analyze_conversation_for_fraud(
                    state["conversation"], state["entities"]
                )
                risk = await assess_risk(
                    state["entities"], face_result, geo_result,
                    state["consents"], fraud_flags
                )
                offer = await generate_offer(state["entities"], risk)

                audit_logger.log_risk_assessment(session_id, risk)
                audit_logger.log_offer_generated(session_id, offer)

                await websocket.send_json({
                    "type": "offer_ready",
                    "data": {
                        "offer": offer.model_dump(),
                        "risk": risk.model_dump(),
                    }
                })

            # ── End Session ──
            elif msg_type == "end_session":
                state["status"] = SessionStatus.COMPLETED
                audit_logger.log_event(session_id, "session_completed")
                await websocket.send_json({
                    "type": "session_ended",
                    "data": {"message": "Session completed successfully."}
                })
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
        state["status"] = SessionStatus.DROPPED
        audit_logger.log_event(session_id, "session_dropped", {"reason": "disconnected"})
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "data": {"message": str(e)}})
        except Exception:
            pass
    finally:
        clear_tracker(session_id)


# ─── Startup ─────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    logger.info("=" * 50)
    logger.info("  LoanWizard AI Server Starting")
    logger.info("=" * 50)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)