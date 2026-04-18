/**
 * AIAvatar.jsx — AI Agent Display
 * Shows the AI agent's avatar, conversation messages,
 * handles TTS (text-to-speech), and provides text input fallback.
 */

import React, { useState, useRef, useEffect } from 'react';

export default function AIAvatar({ messages, onSendMessage, isProcessing, entities }) {
  const [inputText, setInputText] = useState('');
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const chatEndRef = useRef(null);

  // Auto-scroll to latest message
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // TTS: Speak agent messages
  useEffect(() => {
    if (!ttsEnabled || messages.length === 0) return;
    const last = messages[messages.length - 1];
    if (last.role === 'assistant' && last.text) {
      speak(last.text);
    }
  }, [messages, ttsEnabled]);

  const speak = (text) => {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.lang = 'en-IN';

    // Try to find a good voice
    const voices = window.speechSynthesis.getVoices();
    const preferred = voices.find(v =>
      v.name.includes('Google') && v.lang.includes('en')
    ) || voices.find(v => v.lang.includes('en'));
    if (preferred) utterance.voice = preferred;

    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);

    window.speechSynthesis.speak(utterance);
  };

  const handleSend = () => {
    if (!inputText.trim() || isProcessing) return;
    onSendMessage(inputText.trim());
    setInputText('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Compute filled entities count
  const entityFields = entities ? Object.entries(entities).filter(([k, v]) => v !== null && v !== undefined && k !== 'existing_loans' && k !== 'education_level') : [];
  const filledCount = entityFields.length;

  return (
    <div style={styles.container}>
      {/* Agent header */}
      <div style={styles.header}>
        <div style={styles.avatarWrapper}>
          <div style={{
            ...styles.avatar,
            boxShadow: isSpeaking ? '0 0 20px rgba(0, 212, 255, 0.5)' : 'none',
          }}>
            <span style={styles.avatarIcon}>🤖</span>
          </div>
          {isSpeaking && <div style={styles.speakingRing} />}
        </div>
        <div>
          <div style={styles.agentName}>LoanWizard AI</div>
          <div style={styles.agentSub}>
            {isProcessing ? 'Thinking...' : isSpeaking ? 'Speaking...' : 'Listening'}
          </div>
        </div>
        <button
          style={{
            ...styles.ttsToggle,
            backgroundColor: ttsEnabled ? 'rgba(0, 212, 255, 0.15)' : 'rgba(255, 255, 255, 0.05)',
          }}
          onClick={() => {
            setTtsEnabled(!ttsEnabled);
            if (!ttsEnabled === false) window.speechSynthesis.cancel();
          }}
          title={ttsEnabled ? 'Mute agent voice' : 'Unmute agent voice'}
        >
          {ttsEnabled ? '🔊' : '🔇'}
        </button>
      </div>

      {/* Chat messages */}
      <div style={styles.chatArea}>
        {messages.length === 0 && (
          <div style={styles.emptyState}>
            <p style={styles.emptyText}>Starting video call...</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              ...styles.messageBubble,
              ...(msg.role === 'assistant' ? styles.agentMsg : styles.userMsg),
            }}
          >
            {msg.role === 'assistant' && <span style={styles.msgIcon}>🤖</span>}
            <div style={styles.msgContent}>
              <p style={styles.msgText}>{msg.text}</p>
              {msg.timestamp && (
                <span style={styles.msgTime}>{msg.timestamp}</span>
              )}
            </div>
            {msg.role === 'user' && <span style={styles.msgIcon}>👤</span>}
          </div>
        ))}

        {isProcessing && (
          <div style={{ ...styles.messageBubble, ...styles.agentMsg }}>
            <span style={styles.msgIcon}>🤖</span>
            <div style={styles.typingDots}>
              <span style={{ ...styles.dot, animationDelay: '0s' }} />
              <span style={{ ...styles.dot, animationDelay: '0.2s' }} />
              <span style={{ ...styles.dot, animationDelay: '0.4s' }} />
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Extracted entities summary bar */}
      {filledCount > 0 && (
        <div style={styles.entitiesBar}>
          <span style={styles.entitiesLabel}>Captured:</span>
          {entityFields.map(([key, val]) => (
            <span key={key} style={styles.entityChip}>
              {formatKey(key)}: {formatValue(key, val)}
            </span>
          ))}
        </div>
      )}

      {/* Text input */}
      <div style={styles.inputArea}>
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type your response (or speak)..."
          style={styles.input}
          disabled={isProcessing}
        />
        <button
          onClick={handleSend}
          disabled={isProcessing || !inputText.trim()}
          style={{
            ...styles.sendBtn,
            opacity: isProcessing || !inputText.trim() ? 0.4 : 1,
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}

function formatKey(key) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
    .replace('Full Name', 'Name')
    .replace('Age Declared', 'Age')
    .replace('Monthly Income', 'Income')
    .replace('Loan Amount Requested', 'Amount')
    .replace('Employment Type', 'Employment')
    .replace('Loan Purpose', 'Purpose')
    .replace('Employer Name', 'Employer');
}

function formatValue(key, val) {
  if (key === 'monthly_income' || key === 'loan_amount_requested') {
    return `₹${Number(val).toLocaleString('en-IN')}`;
  }
  return String(val);
}

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    backgroundColor: 'rgba(11, 17, 32, 0.6)',
    borderRadius: 16,
    border: '1px solid rgba(0, 212, 255, 0.1)',
    overflow: 'hidden',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    padding: '14px 18px',
    borderBottom: '1px solid rgba(255,255,255,0.06)',
    backgroundColor: 'rgba(22, 32, 53, 0.8)',
  },
  avatarWrapper: { position: 'relative' },
  avatar: {
    width: 44,
    height: 44,
    borderRadius: '50%',
    backgroundColor: 'rgba(0, 212, 255, 0.15)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'box-shadow 0.3s',
  },
  avatarIcon: { fontSize: 22 },
  speakingRing: {
    position: 'absolute',
    inset: -4,
    borderRadius: '50%',
    border: '2px solid rgba(0, 212, 255, 0.4)',
    animation: 'pulse 1.5s ease-in-out infinite',
  },
  agentName: {
    fontSize: 15,
    fontWeight: 600,
    color: '#E0E6ED',
    fontFamily: '"DM Sans", sans-serif',
  },
  agentSub: {
    fontSize: 12,
    color: '#6B7FA3',
    fontFamily: '"DM Sans", sans-serif',
  },
  ttsToggle: {
    marginLeft: 'auto',
    width: 36,
    height: 36,
    borderRadius: '50%',
    border: '1px solid rgba(255,255,255,0.1)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    fontSize: 16,
    transition: 'background 0.2s',
  },
  chatArea: {
    flex: 1,
    overflowY: 'auto',
    padding: '16px 14px',
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
    minHeight: 200,
    maxHeight: 340,
  },
  emptyState: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flex: 1,
  },
  emptyText: { color: '#4A5F80', fontSize: 14, fontFamily: '"DM Sans", sans-serif' },
  messageBubble: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: 8,
    maxWidth: '92%',
  },
  agentMsg: { alignSelf: 'flex-start' },
  userMsg: { alignSelf: 'flex-end', flexDirection: 'row-reverse' },
  msgIcon: { fontSize: 18, marginTop: 2 },
  msgContent: {
    padding: '10px 14px',
    borderRadius: 12,
    backgroundColor: 'rgba(0, 212, 255, 0.08)',
    border: '1px solid rgba(0, 212, 255, 0.1)',
  },
  msgText: {
    fontSize: 13.5,
    lineHeight: 1.5,
    color: '#D0D8E4',
    margin: 0,
    fontFamily: '"DM Sans", sans-serif',
  },
  msgTime: {
    fontSize: 10,
    color: '#4A5F80',
    marginTop: 4,
    display: 'block',
    fontFamily: '"JetBrains Mono", monospace',
  },
  typingDots: {
    display: 'flex',
    gap: 4,
    padding: '12px 16px',
    backgroundColor: 'rgba(0, 212, 255, 0.08)',
    borderRadius: 12,
  },
  dot: {
    width: 7,
    height: 7,
    borderRadius: '50%',
    backgroundColor: '#00D4FF',
    animation: 'bounce 1.2s infinite',
  },
  entitiesBar: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 6,
    padding: '8px 14px',
    borderTop: '1px solid rgba(255,255,255,0.04)',
    backgroundColor: 'rgba(0, 230, 118, 0.03)',
  },
  entitiesLabel: {
    fontSize: 11,
    fontWeight: 600,
    color: '#00E676',
    fontFamily: '"DM Sans", sans-serif',
    marginRight: 4,
  },
  entityChip: {
    fontSize: 11,
    padding: '2px 8px',
    borderRadius: 6,
    backgroundColor: 'rgba(0, 230, 118, 0.1)',
    color: '#80E8A8',
    fontFamily: '"JetBrains Mono", monospace',
  },
  inputArea: {
    display: 'flex',
    gap: 8,
    padding: '12px 14px',
    borderTop: '1px solid rgba(255,255,255,0.06)',
    backgroundColor: 'rgba(22, 32, 53, 0.5)',
  },
  input: {
    flex: 1,
    padding: '10px 14px',
    backgroundColor: 'rgba(255,255,255,0.05)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: 10,
    color: '#E0E6ED',
    fontSize: 13.5,
    outline: 'none',
    fontFamily: '"DM Sans", sans-serif',
  },
  sendBtn: {
    padding: '10px 20px',
    backgroundColor: '#00D4FF',
    color: '#0B1120',
    border: 'none',
    borderRadius: 10,
    fontWeight: 600,
    fontSize: 13,
    cursor: 'pointer',
    fontFamily: '"DM Sans", sans-serif',
    transition: 'opacity 0.2s',
  },
};
