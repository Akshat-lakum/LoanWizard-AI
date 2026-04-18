# 🤖 LoanWizard AI — Agentic Video Call-Based Loan Onboarding

**TenzorX National AI Hackathon 2026 | Problem Statement 3**  
**Team:** Akshat Lakum | NIT Surat | B.Tech ECE

---

## 🎯 What is LoanWizard AI?

LoanWizard AI is an intelligent video call-based loan onboarding system that replaces traditional form-based applications with a conversational AI agent. The AI agent conducts a live video call, captures customer information through natural conversation, verifies identity, detects fraud, and generates personalized loan offers — all in under 5 minutes.

## ✨ Key Features

- **AI Video Agent** — Conducts human-like conversations via video call with multilingual support
- **Speech-to-Text** — Real-time transcription using OpenAI Whisper (supports Hindi, English, and 90+ languages)
- **Face Analysis** — MediaPipe-based age estimation, liveness detection, and face consistency checking
- **NER Extraction** — Automatically extracts name, income, employment, loan purpose from speech
- **LLM Intelligence** — Claude/GPT-powered contextual understanding and conversation flow
- **Fraud Detection** — Geo-fencing, age mismatch detection, VPN detection, conversation analysis
- **Risk Engine** — Policy rules + ML-based scoring for eligibility and risk assessment
- **Dynamic Offers** — Personalized loan offers with EMI calculation based on customer profile
- **Audit Trail** — Complete regulatory-compliant logging of video, transcripts, consents, and decisions

## 🏗️ Architecture

```
┌──────────────────────────────────────────┐
│  Frontend (React + WebRTC + MediaPipe)   │  ← Customer video feed
├──────────────────────────────────────────┤
│  Processing (Whisper STT + OpenCV + NER) │  ← Audio → Text → Entities
├──────────────────────────────────────────┤
│  Intelligence (Claude/GPT LLM)           │  ← Context + Risk classification
├──────────────────────────────────────────┤
│  Decision (Policy + Risk + Offer Engine) │  ← Eligibility + Personalized offer
├──────────────────────────────────────────┤
│  Storage (Audit logs + Transcripts)      │  ← Compliance trail
└──────────────────────────────────────────┘
```

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, WebRTC, MediaPipe Face Mesh, Web Speech API |
| Backend | Python 3.10+, FastAPI, WebSocket |
| STT | faster-whisper (CTranslate2 backend, base model) |
| Face Analysis | MediaPipe, OpenCV |
| NER | spaCy (en_core_web_sm) + rule-based extractors |
| LLM | Anthropic Claude / OpenAI GPT |
| TTS | Web Speech API (browser-native) |
| Database | In-memory (SQLite for production) |

## 🚀 Quick Start

### Prerequisites
- Python 3.12+ (tested on 3.14)
- Node.js 18+
- (Optional) Anthropic or OpenAI API key for LLM features

### Backend Setup
```bash
cd backend
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Optional: Set API key for LLM features
export ANTHROPIC_API_KEY="your-key-here"
# OR
export OPENAI_API_KEY="your-key-here"

# Start server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

### Demo Mode
The system works **without API keys** using template-based responses. This lets you demo the full flow including video capture, face analysis, entity extraction, and offer generation — the LLM just uses pre-written templates instead of generating responses.

## 📁 Project Structure

```
LoanWizard-AI/
├── backend/
│   ├── main.py              # FastAPI server (REST + WebSocket)
│   ├── models.py            # Pydantic data models
│   ├── stt_engine.py        # Whisper speech-to-text
│   ├── face_analyzer.py     # MediaPipe face analysis + age estimation
│   ├── ner_extractor.py     # Entity extraction (NER + regex)
│   ├── llm_orchestrator.py  # LLM conversation engine
│   ├── risk_engine.py       # Policy rules + risk scoring
│   ├── offer_generator.py   # Dynamic loan offer generation
│   ├── audit_logger.py      # Compliance audit trail
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── VideoCall.jsx
│   │   │   ├── AIAvatar.jsx
│   │   │   ├── ConsentCapture.jsx
│   │   │   ├── LoanOffer.jsx
│   │   │   └── AuditPanel.jsx
│   │   └── utils/
│   │       ├── webrtc.js
│   │       └── api.js
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## 🎬 Demo Flow

1. Customer clicks campaign link → lands on video call page
2. AI agent greets and starts conversational onboarding
3. Real-time: face detection, liveness check, geo-location capture
4. Agent asks: name → age → city → employment → income → loan purpose → amount
5. NER extracts entities automatically from speech
6. Customer gives verbal consent
7. Risk engine evaluates: policy rules + ML scoring + fraud signals
8. Personalized loan offer generated and displayed
9. Complete audit trail available for compliance

## 📊 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/session/create` | Create new onboarding session |
| POST | `/api/agent/respond` | Get AI agent response |
| POST | `/api/stt/transcribe` | Transcribe audio |
| POST | `/api/face/analyze` | Analyze video frame |
| POST | `/api/geo/verify` | Verify geo-location |
| POST | `/api/consent/capture` | Capture consent |
| POST | `/api/offer/generate` | Generate loan offer |
| GET | `/api/audit/{id}` | Get audit trail |
| WS | `/ws/{session_id}` | Real-time video call |

## 🏆 Innovation Highlights

1. **Zero-form onboarding** — Entire application via natural conversation
2. **Multimodal verification** — Face + Voice + Location + Behavior
3. **LipNet-inspired pipeline** — Leverages real-time video processing expertise
4. **Explainable risk scoring** — Transparent factors and red flags
5. **Regulatory-ready audit** — Every event logged with timestamps

## 📄 License

Built for TenzorX National AI Hackathon 2026 by Poonawalla Fincorp.
