/**
 * api.js — Backend API communication layer
 * Handles REST calls and WebSocket connection to the FastAPI backend.
 */

const API_BASE = '/api';
const WS_BASE = `ws://${window.location.hostname}:8000/ws`;

// ─── REST API Calls ──────────────────────────────────────────

export async function createSession(data = {}) {
  const res = await fetch(`${API_BASE}/session/create`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      customer_name: data.name || null,
      phone: data.phone || null,
      source_campaign: data.campaign || 'direct',
    }),
  });
  return res.json();
}

export async function getSession(sessionId) {
  const res = await fetch(`${API_BASE}/session/${sessionId}`);
  return res.json();
}

export async function sendTextMessage(sessionId, message, language = 'en') {
  const res = await fetch(`${API_BASE}/agent/respond`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      customer_message: message,
      language,
    }),
  });
  return res.json();
}

export async function analyzeFace(sessionId, frameBase64, declaredAge = null) {
  const res = await fetch(`${API_BASE}/face/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      frame_base64: frameBase64,
      declared_age: declaredAge,
    }),
  });
  return res.json();
}

export async function verifyGeo(sessionId, location) {
  const res = await fetch(`${API_BASE}/geo/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      location,
    }),
  });
  return res.json();
}

export async function generateOffer(sessionId) {
  const res = await fetch(`${API_BASE}/offer/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  });
  return res.json();
}

export async function getAudit(sessionId) {
  const res = await fetch(`${API_BASE}/audit/${sessionId}`);
  return res.json();
}

// ─── WebSocket Connection ────────────────────────────────────

export class LoanWizardSocket {
  constructor(sessionId, handlers = {}) {
    this.sessionId = sessionId;
    this.handlers = handlers;
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnects = 3;
  }

  connect() {
    this.ws = new WebSocket(`${WS_BASE}/${this.sessionId}`);

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
      this.handlers.onConnect?.();
    };

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        const handler = this.handlers[msg.type];
        if (handler) handler(msg.data);
        this.handlers.onMessage?.(msg);
      } catch (e) {
        console.error('WS message parse error:', e);
      }
    };

    this.ws.onclose = () => {
      console.log('WebSocket closed');
      this.handlers.onDisconnect?.();
      if (this.reconnectAttempts < this.maxReconnects) {
        this.reconnectAttempts++;
        setTimeout(() => this.connect(), 2000);
      }
    };

    this.ws.onerror = (err) => {
      console.error('WebSocket error:', err);
      this.handlers.onError?.(err);
    };
  }

  send(type, data = {}) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, data, session_id: this.sessionId }));
    }
  }

  sendAudio(audioBase64) {
    this.send('audio_chunk', { audio: audioBase64 });
  }

  sendFrame(frameBase64) {
    this.send('video_frame', { frame: frameBase64 });
  }

  sendText(text) {
    this.send('text_input', { text });
  }

  sendGeo(location) {
    this.send('geo_update', location);
  }

  requestOffer() {
    this.send('generate_offer');
  }

  endSession() {
    this.send('end_session');
  }

  disconnect() {
    this.maxReconnects = 0;
    this.ws?.close();
  }
}
