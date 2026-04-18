/**
 * App.jsx — LoanWizard AI Main Application
 * Orchestrates the entire video call onboarding flow:
 * Landing → Video Call → Conversation → Offer → Complete
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import VideoCall from './components/VideoCall';
import AIAvatar from './components/AIAvatar';
import LoanOffer from './components/LoanOffer';
import AuditPanel from './components/AuditPanel';
import { createSession, sendTextMessage, analyzeFace, generateOffer, getAudit } from './utils/api';

// ─── App States ─────────────────────────────────────────────
const SCREENS = {
  LANDING: 'landing',
  CALL: 'call',
  OFFER: 'offer',
  COMPLETE: 'complete',
};

export default function App() {
  const [screen, setScreen] = useState(SCREENS.LANDING);
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [entities, setEntities] = useState({});
  const [faceStatus, setFaceStatus] = useState(null);
  const [geoStatus, setGeoStatus] = useState(null);
  const [offer, setOffer] = useState(null);
  const [risk, setRisk] = useState(null);
  const [consents, setConsents] = useState([]);
  const [auditEvents, setAuditEvents] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [showAudit, setShowAudit] = useState(true);
  const messageCountRef = useRef(0);

  // ─── Start Session ──────────────────────────────────────────
  const startSession = async () => {
    try {
      const session = await createSession({ campaign: 'tenzorx_hackathon' });
      setSessionId(session.session_id);
      setScreen(SCREENS.CALL);

      // Get geo-location
      if ('geolocation' in navigator) {
        navigator.geolocation.getCurrentPosition((pos) => {
          setGeoStatus({
            location: {
              latitude: pos.coords.latitude,
              longitude: pos.coords.longitude,
              accuracy: pos.coords.accuracy,
            },
            is_within_serviceable_area: true,
          });
        });
      }

      // Send initial greeting
      setIsProcessing(true);
      const res = await sendTextMessage(session.session_id, 'Hello, I want to apply for a loan.', 'en');
      addMessage('assistant', res.response);
      if (res.entities) setEntities(res.entities);
      setIsProcessing(false);
    } catch (err) {
      console.error('Session start error:', err);
      // Fallback: start anyway with mock greeting
      setSessionId('demo-session');
      setScreen(SCREENS.CALL);
      addMessage('assistant', 'Welcome to Poonawalla Fincorp! I\'m LoanWizard, your AI loan assistant. I\'ll help you with your loan application today. Could you please tell me your name?');
    }
  };

  // ─── Message Handling ────────────────────────────────────────
  const addMessage = (role, text) => {
    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    setMessages(prev => [...prev, { role, text, timestamp }]);
    messageCountRef.current++;

    // Add to audit
    setAuditEvents(prev => [...prev, {
      event_type: role === 'user' ? 'customer_spoke' : 'agent_responded',
      timestamp: new Date().toISOString(),
    }]);
  };

  const handleSendMessage = async (text) => {
    if (!text.trim() || isProcessing) return;

    addMessage('user', text);
    setIsProcessing(true);

    try {
      if (sessionId && sessionId !== 'demo-session') {
        const res = await sendTextMessage(sessionId, text, 'en');
        addMessage('assistant', res.response);
        if (res.entities) setEntities(res.entities);

        // Check if we should generate offer (after ~8 exchanges)
        if (res.conversation_step >= 8 || messageCountRef.current >= 16) {
          // Auto-generate offer
          setTimeout(() => handleGenerateOffer(), 2000);
        }
      } else {
        // Demo mode — simulate responses
        const demoResponse = getDemoResponse(text, entities, messageCountRef.current);
        setTimeout(() => {
          addMessage('assistant', demoResponse.response);
          setEntities(prev => ({ ...prev, ...demoResponse.entities }));
          if (demoResponse.triggerOffer) {
            setTimeout(() => handleGenerateOffer(), 1500);
          }
        }, 1000);
      }
    } catch (err) {
      console.error('Send error:', err);
      addMessage('assistant', 'I apologize for the brief pause. Could you please repeat that?');
    }

    setIsProcessing(false);
  };

  // ─── Face Analysis ──────────────────────────────────────────
  const handleFrame = useCallback(async (frameBase64) => {
    if (!sessionId) return;

    try {
      if (sessionId !== 'demo-session') {
        const result = await analyzeFace(sessionId, frameBase64, entities.age_declared);
        setFaceStatus(result);
      } else {
        // Demo mode
        setFaceStatus({
          face_detected: true,
          estimated_age: 24,
          age_confidence: 0.7,
          liveness_score: 0.85,
          face_match_consistent: true,
          age_mismatch_flag: false,
        });
      }
    } catch (err) {
      // Silently fail for face analysis
    }
  }, [sessionId, entities.age_declared]);

  // ─── Offer Generation ────────────────────────────────────────
  const handleGenerateOffer = async () => {
    addMessage('assistant', 'Excellent! Thank you for all the details. I\'m now generating your personalized loan offer. Please hold on for just a moment...');

    setIsProcessing(true);

    try {
      if (sessionId && sessionId !== 'demo-session') {
        const res = await generateOffer(sessionId);
        setOffer(res.offer);
        setRisk(res.risk);
      } else {
        // Demo offer
        await new Promise(r => setTimeout(r, 2000));
        setOffer(getDemoOffer(entities));
        setRisk({
          risk_level: 'low',
          risk_score: 0.22,
          factors: ['age_within_range', 'income_meets_threshold', 'salaried_employment', 'strong_liveness_verified', 'location_verified'],
          red_flags: [],
          confidence: 0.85,
        });
      }

      setScreen(SCREENS.OFFER);
    } catch (err) {
      console.error('Offer error:', err);
      addMessage('assistant', 'I\'m having trouble generating your offer. Let me try again...');
    }

    setIsProcessing(false);
  };

  const handleAcceptOffer = () => {
    setScreen(SCREENS.COMPLETE);
    setAuditEvents(prev => [...prev, {
      event_type: 'offer_accepted',
      timestamp: new Date().toISOString(),
    }]);
  };

  // ─── Render ───────────────────────────────────────────────────
  return (
    <div style={styles.app}>
      <style>{globalCSS}</style>

      {/* Header */}
      <header style={styles.header}>
        <div style={styles.logo}>
          <span style={styles.logoIcon}>🤖</span>
          <span style={styles.logoText}>LoanWizard AI</span>
        </div>
        <span style={styles.brandText}>Poonawalla Fincorp</span>
        {sessionId && (
          <button
            style={styles.auditToggle}
            onClick={() => setShowAudit(!showAudit)}
          >
            🛡️ {showAudit ? 'Hide' : 'Show'} Audit
          </button>
        )}
      </header>

      {/* ── LANDING SCREEN ── */}
      {screen === SCREENS.LANDING && (
        <div style={styles.landing}>
          <div style={styles.landingContent}>
            <div style={styles.landingIcon}>🤖</div>
            <h1 style={styles.landingTitle}>LoanWizard AI</h1>
            <p style={styles.landingSubtitle}>
              Your AI-powered loan assistant from Poonawalla Fincorp
            </p>
            <p style={styles.landingDesc}>
              Apply for a loan through a simple video conversation.
              No forms, no paperwork — just talk to our AI agent and get
              a personalized loan offer in minutes.
            </p>

            <div style={styles.features}>
              {[
                { icon: '🎥', text: 'Live Video Call' },
                { icon: '🔒', text: 'Secure & Private' },
                { icon: '🌐', text: 'Multilingual' },
                { icon: '⚡', text: '5-Minute Process' },
              ].map((f, i) => (
                <div key={i} style={styles.featureChip}>
                  <span>{f.icon}</span>
                  <span style={styles.featureText}>{f.text}</span>
                </div>
              ))}
            </div>

            <button style={styles.startBtn} onClick={startSession}>
              Start Video Call
            </button>

            <p style={styles.disclaimer}>
              By proceeding, you consent to video recording and AI-assisted processing
              of your loan application. Your data is encrypted and handled per RBI guidelines.
            </p>
          </div>
        </div>
      )}

      {/* ── VIDEO CALL SCREEN ── */}
      {screen === SCREENS.CALL && (
        <div style={styles.callLayout}>
          <div style={styles.callMain}>
            {/* Video */}
            <div style={styles.videoSection}>
              <VideoCall
                sessionId={sessionId}
                onFrame={handleFrame}
                onFaceStatus={faceStatus}
                isActive={true}
              />
            </div>

            {/* Chat */}
            <div style={styles.chatSection}>
              <AIAvatar
                messages={messages}
                onSendMessage={handleSendMessage}
                isProcessing={isProcessing}
                entities={entities}
              />
            </div>
          </div>

          {/* Audit panel */}
          {showAudit && (
            <div style={styles.auditSection}>
              <AuditPanel
                entities={entities}
                faceStatus={faceStatus}
                geoStatus={geoStatus}
                consents={consents}
                auditEvents={auditEvents}
              />
            </div>
          )}
        </div>
      )}

      {/* ── OFFER SCREEN ── */}
      {screen === SCREENS.OFFER && (
        <div style={styles.offerLayout}>
          <div style={styles.offerMain}>
            <LoanOffer
              offer={offer}
              risk={risk}
              onAccept={handleAcceptOffer}
            />
          </div>
          {showAudit && (
            <div style={styles.auditSection}>
              <AuditPanel
                entities={entities}
                faceStatus={faceStatus}
                geoStatus={geoStatus}
                consents={consents}
                auditEvents={auditEvents}
              />
            </div>
          )}
        </div>
      )}

      {/* ── COMPLETE SCREEN ── */}
      {screen === SCREENS.COMPLETE && (
        <div style={styles.completeScreen}>
          <div style={styles.completeCard}>
            <div style={styles.completeIcon}>🎉</div>
            <h1 style={styles.completeTitle}>Application Submitted!</h1>
            <p style={styles.completeText}>
              Your loan application has been submitted successfully.
              Our team will review and contact you within 24 hours.
            </p>
            <div style={styles.refBox}>
              <span style={styles.refLabel}>Reference ID</span>
              <span style={styles.refId}>{sessionId?.slice(0, 8)?.toUpperCase() || 'DEMO1234'}</span>
            </div>
            <p style={styles.completeNote}>
              A complete audit trail of your video call, verification, and consent
              has been securely stored for compliance.
            </p>
            <button
              style={styles.newBtn}
              onClick={() => {
                setScreen(SCREENS.LANDING);
                setMessages([]);
                setEntities({});
                setOffer(null);
                setRisk(null);
                setSessionId(null);
                setFaceStatus(null);
                setConsents([]);
                setAuditEvents([]);
                messageCountRef.current = 0;
              }}
            >
              Start New Application
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Demo Mode Helpers ────────────────────────────────────────

function getDemoResponse(text, entities, msgCount) {
  const lower = text.toLowerCase();
  let response = '';
  let newEntities = {};
  let triggerOffer = false;

  // Simple pattern matching for demo
  if (msgCount <= 2) {
    // Extract name
    const words = text.trim().split(/\s+/);
    const name = words.length <= 3 ? text.trim() : words.slice(0, 2).join(' ');
    newEntities.full_name = name;
    response = `Nice to meet you, ${name}! Could you tell me your age please?`;
  } else if (!entities.age_declared) {
    const age = parseInt(text.match(/\d+/)?.[0]);
    if (age) newEntities.age_declared = age;
    response = 'Great, thank you! Which city are you currently based in?';
  } else if (!entities.city) {
    newEntities.city = text.trim();
    response = 'Got it! Are you currently salaried, self-employed, or a student?';
  } else if (!entities.employment_type) {
    if (lower.includes('salar')) newEntities.employment_type = 'salaried';
    else if (lower.includes('self') || lower.includes('business')) newEntities.employment_type = 'self_employed';
    else if (lower.includes('student')) newEntities.employment_type = 'student';
    else newEntities.employment_type = 'salaried';
    response = newEntities.employment_type === 'salaried'
      ? 'Could you tell me which company you work with?'
      : 'Thank you! Could you share your approximate monthly income?';
  } else if (!entities.employer_name && entities.employment_type === 'salaried') {
    newEntities.employer_name = text.trim();
    response = 'Thank you! Could you share your approximate monthly or annual income?';
  } else if (!entities.monthly_income) {
    const num = parseFloat(text.replace(/[,₹\s]/g, '').match(/[\d.]+/)?.[0] || '0');
    newEntities.monthly_income = num > 0 ? (num < 1000 ? num * 1000 : num) : 50000;
    response = 'Perfect! What would you like the loan for? Education, personal needs, business, or something else?';
  } else if (!entities.loan_purpose) {
    if (lower.includes('educ')) newEntities.loan_purpose = 'education';
    else if (lower.includes('personal')) newEntities.loan_purpose = 'personal';
    else if (lower.includes('business')) newEntities.loan_purpose = 'business';
    else if (lower.includes('home') || lower.includes('house')) newEntities.loan_purpose = 'home';
    else newEntities.loan_purpose = 'personal';
    response = 'I see! And approximately how much loan amount are you looking for?';
  } else if (!entities.loan_amount_requested) {
    const num = parseFloat(text.replace(/[,₹\s]/g, '').match(/[\d.]+/)?.[0] || '0');
    let amount = num;
    if (lower.includes('lakh')) amount = num * 100000;
    else if (num < 10000) amount = num * 100000;
    newEntities.loan_amount_requested = amount > 0 ? amount : 500000;
    response = `Thank you! Let me confirm: ${entities.full_name || 'you'} are looking for a ₹${(amount || 500000).toLocaleString('en-IN')} ${entities.loan_purpose || 'personal'} loan. Do I have your consent to proceed with the application and credit check?`;
  } else {
    triggerOffer = true;
    response = '';
  }

  return { response, entities: newEntities, triggerOffer };
}

function getDemoOffer(entities) {
  const income = entities.monthly_income || 50000;
  const requested = entities.loan_amount_requested || 500000;
  const maxEligible = income * 12 * 3;
  const maxAmount = Math.min(requested * 1.2, maxEligible);
  const rate = 11.5;
  const months = 36;
  const r = rate / (12 * 100);
  const emi = maxAmount * r * Math.pow(1 + r, months) / (Math.pow(1 + r, months) - 1);

  return {
    eligible: true,
    loan_amount_min: Math.round(maxAmount * 0.4),
    loan_amount_max: Math.round(maxAmount),
    interest_rate: rate,
    tenure_months: [12, 24, 36, 48, 60],
    emi_estimate: Math.round(emi),
    processing_fee_percent: 1.0,
    special_conditions: [
      'Pre-approved — minimal documentation required',
      'Subject to income proof verification',
    ],
  };
}

// ─── Styles ─────────────────────────────────────────────────

const globalCSS = `
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #060B18; color: #E0E6ED; font-family: 'DM Sans', sans-serif; }
  @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
  @keyframes spin { to { transform: rotate(360deg); } }
  @keyframes bounce { 0%, 80%, 100% { transform: translateY(0); } 40% { transform: translateY(-6px); } }
  @keyframes fadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: rgba(0,212,255,0.2); border-radius: 4px; }
`;

const styles = {
  app: {
    minHeight: '100vh',
    background: 'linear-gradient(180deg, #060B18 0%, #0B1120 50%, #0D1527 100%)',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    padding: '12px 24px',
    borderBottom: '1px solid rgba(0, 212, 255, 0.08)',
    backgroundColor: 'rgba(11, 17, 32, 0.9)',
    backdropFilter: 'blur(10px)',
    position: 'sticky',
    top: 0,
    zIndex: 100,
  },
  logo: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  logoIcon: { fontSize: 24 },
  logoText: {
    fontSize: 18,
    fontWeight: 700,
    color: '#00D4FF',
    fontFamily: '"DM Sans", sans-serif',
  },
  brandText: {
    marginLeft: 16,
    fontSize: 13,
    color: '#4A5F80',
    fontFamily: '"DM Sans", sans-serif',
    paddingLeft: 16,
    borderLeft: '1px solid rgba(255,255,255,0.08)',
  },
  auditToggle: {
    marginLeft: 'auto',
    padding: '6px 14px',
    backgroundColor: 'rgba(255,255,255,0.05)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: 8,
    color: '#B8C4D6',
    fontSize: 12,
    cursor: 'pointer',
    fontFamily: '"DM Sans", sans-serif',
  },

  // Landing
  landing: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: 'calc(100vh - 60px)',
    padding: 24,
  },
  landingContent: {
    maxWidth: 520,
    textAlign: 'center',
    animation: 'fadeIn 0.8s ease-out',
  },
  landingIcon: { fontSize: 64, marginBottom: 16 },
  landingTitle: {
    fontSize: 42,
    fontWeight: 700,
    color: '#00D4FF',
    marginBottom: 8,
  },
  landingSubtitle: {
    fontSize: 18,
    color: '#B8C4D6',
    marginBottom: 20,
  },
  landingDesc: {
    fontSize: 15,
    color: '#6B7FA3',
    lineHeight: 1.6,
    marginBottom: 28,
  },
  features: {
    display: 'flex',
    justifyContent: 'center',
    gap: 12,
    marginBottom: 32,
    flexWrap: 'wrap',
  },
  featureChip: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: '8px 16px',
    backgroundColor: 'rgba(0, 212, 255, 0.06)',
    border: '1px solid rgba(0, 212, 255, 0.15)',
    borderRadius: 20,
  },
  featureText: {
    fontSize: 13,
    color: '#B8C4D6',
  },
  startBtn: {
    padding: '16px 48px',
    background: 'linear-gradient(135deg, #00D4FF 0%, #00E676 100%)',
    color: '#0B1120',
    border: 'none',
    borderRadius: 14,
    fontSize: 18,
    fontWeight: 700,
    cursor: 'pointer',
    fontFamily: '"DM Sans", sans-serif',
    transition: 'transform 0.2s, box-shadow 0.2s',
    boxShadow: '0 4px 24px rgba(0, 212, 255, 0.3)',
  },
  disclaimer: {
    fontSize: 11,
    color: '#3A4F6E',
    marginTop: 20,
    lineHeight: 1.5,
    maxWidth: 400,
    margin: '20px auto 0',
  },

  // Call layout
  callLayout: {
    display: 'flex',
    gap: 16,
    padding: 16,
    height: 'calc(100vh - 60px)',
    overflow: 'hidden',
  },
  callMain: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
    minWidth: 0,
  },
  videoSection: {
    flex: '0 0 auto',
  },
  chatSection: {
    flex: 1,
    minHeight: 0,
  },
  auditSection: {
    width: 320,
    flexShrink: 0,
    overflowY: 'auto',
  },

  // Offer layout
  offerLayout: {
    display: 'flex',
    gap: 16,
    padding: 16,
    minHeight: 'calc(100vh - 60px)',
  },
  offerMain: {
    flex: 1,
    maxWidth: 600,
    margin: '0 auto',
  },

  // Complete screen
  completeScreen: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: 'calc(100vh - 60px)',
    padding: 24,
  },
  completeCard: {
    maxWidth: 480,
    textAlign: 'center',
    animation: 'fadeIn 0.8s ease-out',
    padding: 40,
    backgroundColor: 'rgba(11, 17, 32, 0.6)',
    borderRadius: 20,
    border: '1px solid rgba(0, 230, 118, 0.15)',
  },
  completeIcon: { fontSize: 64, marginBottom: 16 },
  completeTitle: {
    fontSize: 28,
    fontWeight: 700,
    color: '#00E676',
    marginBottom: 12,
  },
  completeText: {
    fontSize: 15,
    color: '#B8C4D6',
    lineHeight: 1.6,
    marginBottom: 24,
  },
  refBox: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 4,
    padding: '16px 24px',
    backgroundColor: 'rgba(0, 212, 255, 0.06)',
    borderRadius: 12,
    border: '1px solid rgba(0, 212, 255, 0.15)',
    marginBottom: 20,
  },
  refLabel: {
    fontSize: 11,
    fontWeight: 600,
    color: '#6B7FA3',
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  refId: {
    fontSize: 24,
    fontWeight: 700,
    color: '#00D4FF',
    fontFamily: '"JetBrains Mono", monospace',
    letterSpacing: 2,
  },
  completeNote: {
    fontSize: 12,
    color: '#4A5F80',
    lineHeight: 1.5,
    marginBottom: 24,
  },
  newBtn: {
    padding: '12px 32px',
    backgroundColor: 'rgba(0, 212, 255, 0.1)',
    color: '#00D4FF',
    border: '1px solid rgba(0, 212, 255, 0.3)',
    borderRadius: 10,
    fontSize: 14,
    fontWeight: 600,
    cursor: 'pointer',
    fontFamily: '"DM Sans", sans-serif',
  },
};
