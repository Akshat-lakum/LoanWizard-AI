/**
 * AuditPanel.jsx — Audit & Verification Panel
 * Shows real-time verification status, collected data, and audit trail.
 * This panel demonstrates the compliance/audit capabilities to judges.
 */

import React from 'react';

export default function AuditPanel({ entities, faceStatus, geoStatus, consents, auditEvents }) {
  const verifications = [
    {
      label: 'Face Detection',
      status: faceStatus?.face_detected ? 'verified' : 'pending',
      detail: faceStatus?.face_detected
        ? `Age ~${faceStatus.estimated_age || '?'}, Liveness: ${((faceStatus.liveness_score || 0) * 100).toFixed(0)}%`
        : 'Waiting for face...',
      icon: '👤',
    },
    {
      label: 'Geo-location',
      status: geoStatus ? 'verified' : 'pending',
      detail: geoStatus
        ? `${geoStatus.location?.city || 'Detected'} — ${geoStatus.is_within_serviceable_area ? 'Serviceable' : 'Outside area'}`
        : 'Waiting...',
      icon: '📍',
    },
    {
      label: 'Identity Consistency',
      status: faceStatus?.face_match_consistent !== false ? 'verified' : 'flagged',
      detail: faceStatus?.face_match_consistent !== false ? 'Same person throughout' : 'Face changed!',
      icon: '🔒',
    },
    {
      label: 'Age Verification',
      status: faceStatus?.age_mismatch_flag ? 'flagged' : (faceStatus?.estimated_age ? 'verified' : 'pending'),
      detail: faceStatus?.age_mismatch_flag
        ? `Mismatch: declared ${entities?.age_declared || '?'} vs estimated ${faceStatus.estimated_age}`
        : (faceStatus?.estimated_age ? 'Consistent' : 'Pending...'),
      icon: '🎂',
    },
  ];

  const statusColors = {
    verified: { bg: 'rgba(0,230,118,0.08)', border: 'rgba(0,230,118,0.2)', color: '#00E676', dot: '#00E676' },
    pending: { bg: 'rgba(255,183,77,0.06)', border: 'rgba(255,183,77,0.15)', color: '#FFB74D', dot: '#FFB74D' },
    flagged: { bg: 'rgba(255,82,82,0.08)', border: 'rgba(255,82,82,0.2)', color: '#FF5252', dot: '#FF5252' },
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span style={styles.headerIcon}>🛡️</span>
        <span style={styles.headerTitle}>Verification & Audit</span>
      </div>

      {/* Verification cards */}
      <div style={styles.verGrid}>
        {verifications.map((v, i) => {
          const c = statusColors[v.status];
          return (
            <div key={i} style={{ ...styles.verCard, backgroundColor: c.bg, borderColor: c.border }}>
              <div style={styles.verTop}>
                <span style={styles.verIcon}>{v.icon}</span>
                <div style={{ ...styles.verDot, backgroundColor: c.dot }} />
              </div>
              <span style={styles.verLabel}>{v.label}</span>
              <span style={{ ...styles.verDetail, color: c.color }}>{v.detail}</span>
            </div>
          );
        })}
      </div>

      {/* Collected data summary */}
      <div style={styles.section}>
        <span style={styles.sectionTitle}>Extracted Application Data</span>
        <div style={styles.dataGrid}>
          {entities && Object.entries(entities).map(([key, val]) => {
            if (val === null || val === undefined) return null;
            if (key === 'existing_loans' || key === 'education_level') return null;
            return (
              <div key={key} style={styles.dataRow}>
                <span style={styles.dataKey}>{key.replace(/_/g, ' ')}</span>
                <span style={styles.dataVal}>
                  {typeof val === 'number' && (key.includes('income') || key.includes('amount'))
                    ? `₹${val.toLocaleString('en-IN')}`
                    : String(val)
                  }
                </span>
              </div>
            );
          })}
          {(!entities || Object.values(entities).every(v => v === null)) && (
            <p style={styles.emptyText}>No data extracted yet</p>
          )}
        </div>
      </div>

      {/* Consents */}
      <div style={styles.section}>
        <span style={styles.sectionTitle}>Consent Trail</span>
        {consents?.length > 0 ? (
          consents.map((c, i) => (
            <div key={i} style={styles.consentRow}>
              <span style={{ color: c.granted ? '#00E676' : '#FF5252' }}>
                {c.granted ? '✓' : '✕'}
              </span>
              <span style={styles.consentType}>{c.consent_type?.replace(/_/g, ' ')}</span>
              {c.verbal_confirmation && (
                <span style={styles.consentQuote}>"{c.verbal_confirmation}"</span>
              )}
            </div>
          ))
        ) : (
          <p style={styles.emptyText}>No consents captured yet</p>
        )}
      </div>

      {/* Recent audit events */}
      <div style={styles.section}>
        <span style={styles.sectionTitle}>Audit Log</span>
        <div style={styles.auditList}>
          {(auditEvents || []).slice(-8).reverse().map((e, i) => (
            <div key={i} style={styles.auditRow}>
              <span style={styles.auditTime}>
                {new Date(e.timestamp).toLocaleTimeString()}
              </span>
              <span style={styles.auditEvent}>{e.event_type?.replace(/_/g, ' ')}</span>
            </div>
          ))}
          {(!auditEvents || auditEvents.length === 0) && (
            <p style={styles.emptyText}>No events yet</p>
          )}
        </div>
      </div>
    </div>
  );
}

const styles = {
  container: {
    backgroundColor: 'rgba(11, 17, 32, 0.6)',
    borderRadius: 16,
    border: '1px solid rgba(0, 212, 255, 0.08)',
    overflow: 'hidden',
    fontFamily: '"DM Sans", sans-serif',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '12px 16px',
    backgroundColor: 'rgba(22, 32, 53, 0.8)',
    borderBottom: '1px solid rgba(255,255,255,0.04)',
  },
  headerIcon: { fontSize: 16 },
  headerTitle: {
    fontSize: 14,
    fontWeight: 600,
    color: '#B8C4D6',
  },
  verGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 8,
    padding: '12px 12px 0',
  },
  verCard: {
    padding: '10px 12px',
    borderRadius: 10,
    border: '1px solid',
    transition: 'all 0.3s',
  },
  verTop: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  verIcon: { fontSize: 16 },
  verDot: {
    width: 7,
    height: 7,
    borderRadius: '50%',
  },
  verLabel: {
    display: 'block',
    fontSize: 11,
    fontWeight: 600,
    color: '#B8C4D6',
    marginBottom: 2,
  },
  verDetail: {
    display: 'block',
    fontSize: 10,
    fontFamily: '"JetBrains Mono", monospace',
  },
  section: {
    padding: '12px 14px',
    borderTop: '1px solid rgba(255,255,255,0.04)',
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: 600,
    color: '#6B7FA3',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    display: 'block',
    marginBottom: 8,
  },
  dataGrid: {
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
  },
  dataRow: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: 12,
    padding: '3px 0',
  },
  dataKey: {
    color: '#6B7FA3',
    textTransform: 'capitalize',
  },
  dataVal: {
    color: '#D0D8E4',
    fontWeight: 500,
    fontFamily: '"JetBrains Mono", monospace',
    fontSize: 11,
  },
  consentRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    fontSize: 12,
    padding: '4px 0',
  },
  consentType: {
    color: '#B8C4D6',
    textTransform: 'capitalize',
  },
  consentQuote: {
    color: '#4A5F80',
    fontSize: 10,
    fontStyle: 'italic',
    fontFamily: '"JetBrains Mono", monospace',
  },
  auditList: {
    maxHeight: 150,
    overflowY: 'auto',
  },
  auditRow: {
    display: 'flex',
    gap: 10,
    fontSize: 11,
    padding: '3px 0',
    borderBottom: '1px solid rgba(255,255,255,0.02)',
  },
  auditTime: {
    color: '#4A5F80',
    fontFamily: '"JetBrains Mono", monospace',
    flexShrink: 0,
    fontSize: 10,
  },
  auditEvent: {
    color: '#8B9FC0',
    textTransform: 'capitalize',
  },
  emptyText: {
    fontSize: 12,
    color: '#3A4F6E',
    margin: '4px 0',
    fontStyle: 'italic',
  },
};
