/**
 * LoanOffer.jsx — Loan Offer Display
 * Shows the generated loan offer with amount, rate, EMI, and conditions.
 */

import React, { useState } from 'react';

export default function LoanOffer({ offer, risk, onAccept }) {
  const [selectedTenure, setSelectedTenure] = useState(null);

  if (!offer) return null;

  const isEligible = offer.eligible;

  // Calculate EMI for different tenures
  const calculateEMI = (principal, rate, months) => {
    const r = rate / (12 * 100);
    if (r <= 0 || months <= 0) return 0;
    return principal * r * Math.pow(1 + r, months) / (Math.pow(1 + r, months) - 1);
  };

  const defaultAmount = (offer.loan_amount_min + offer.loan_amount_max) / 2;

  return (
    <div style={styles.container}>
      {isEligible ? (
        <>
          {/* Success header */}
          <div style={styles.successHeader}>
            <div style={styles.checkmark}>✓</div>
            <h2 style={styles.title}>You're Pre-Approved!</h2>
            <p style={styles.subtitle}>Here's your personalized loan offer</p>
          </div>

          {/* Main offer card */}
          <div style={styles.offerCard}>
            {/* Amount range */}
            <div style={styles.amountSection}>
              <span style={styles.amountLabel}>Loan Amount</span>
              <div style={styles.amountRange}>
                <span style={styles.amountValue}>
                  ₹{Number(offer.loan_amount_min).toLocaleString('en-IN')}
                </span>
                <span style={styles.amountDash}>—</span>
                <span style={styles.amountValue}>
                  ₹{Number(offer.loan_amount_max).toLocaleString('en-IN')}
                </span>
              </div>
            </div>

            {/* Key metrics */}
            <div style={styles.metricsRow}>
              <div style={styles.metric}>
                <span style={styles.metricValue}>{offer.interest_rate}%</span>
                <span style={styles.metricLabel}>Interest Rate p.a.</span>
              </div>
              <div style={styles.metricDivider} />
              <div style={styles.metric}>
                <span style={styles.metricValue}>
                  ₹{Math.round(offer.emi_estimate).toLocaleString('en-IN')}
                </span>
                <span style={styles.metricLabel}>Est. Monthly EMI</span>
              </div>
              <div style={styles.metricDivider} />
              <div style={styles.metric}>
                <span style={styles.metricValue}>{offer.processing_fee_percent}%</span>
                <span style={styles.metricLabel}>Processing Fee</span>
              </div>
            </div>

            {/* Tenure options */}
            <div style={styles.tenureSection}>
              <span style={styles.tenureLabel}>Select Tenure</span>
              <div style={styles.tenureOptions}>
                {offer.tenure_months?.map(t => (
                  <button
                    key={t}
                    onClick={() => setSelectedTenure(t)}
                    style={{
                      ...styles.tenureBtn,
                      ...(selectedTenure === t ? styles.tenureBtnActive : {}),
                    }}
                  >
                    {t < 12 ? `${t}M` : `${t / 12}Y`}
                    <span style={styles.tenureEmi}>
                      ₹{Math.round(calculateEMI(defaultAmount, offer.interest_rate, t)).toLocaleString('en-IN')}/mo
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Risk assessment summary */}
          {risk && (
            <div style={styles.riskCard}>
              <div style={styles.riskHeader}>
                <span style={styles.riskTitle}>Risk Assessment</span>
                <span style={{
                  ...styles.riskBadge,
                  backgroundColor: risk.risk_level === 'low' ? 'rgba(0,230,118,0.15)' :
                    risk.risk_level === 'medium' ? 'rgba(255,183,77,0.15)' : 'rgba(255,82,82,0.15)',
                  color: risk.risk_level === 'low' ? '#00E676' :
                    risk.risk_level === 'medium' ? '#FFB74D' : '#FF5252',
                }}>
                  {risk.risk_level.toUpperCase()}
                </span>
              </div>

              {risk.factors?.length > 0 && (
                <div style={styles.riskFactors}>
                  {risk.factors.slice(0, 4).map((f, i) => (
                    <span key={i} style={styles.factorChip}>✓ {f.replace(/_/g, ' ')}</span>
                  ))}
                </div>
              )}

              {risk.red_flags?.length > 0 && (
                <div style={styles.riskFlags}>
                  {risk.red_flags.map((f, i) => (
                    <span key={i} style={styles.flagChip}>⚠ {f.replace(/_/g, ' ')}</span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Conditions */}
          {offer.special_conditions?.length > 0 && (
            <div style={styles.conditions}>
              {offer.special_conditions.map((c, i) => (
                <p key={i} style={styles.conditionText}>• {c}</p>
              ))}
            </div>
          )}

          {/* Accept button */}
          <button style={styles.acceptBtn} onClick={onAccept}>
            Accept & Proceed
          </button>
        </>
      ) : (
        /* Rejection display */
        <div style={styles.rejectionCard}>
          <div style={styles.rejectIcon}>✕</div>
          <h2 style={{ ...styles.title, color: '#FF8A80' }}>Application Not Approved</h2>
          <p style={styles.rejectionReason}>
            {offer.rejection_reason || 'Your application could not be approved at this time.'}
          </p>
          <p style={styles.rejectionHelp}>
            Please visit your nearest Poonawalla Fincorp branch for further assistance.
          </p>
        </div>
      )}
    </div>
  );
}

const styles = {
  container: {
    padding: 24,
    fontFamily: '"DM Sans", sans-serif',
  },
  successHeader: {
    textAlign: 'center',
    marginBottom: 24,
  },
  checkmark: {
    width: 56,
    height: 56,
    borderRadius: '50%',
    backgroundColor: 'rgba(0, 230, 118, 0.15)',
    color: '#00E676',
    fontSize: 28,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    margin: '0 auto 14px',
    border: '2px solid rgba(0, 230, 118, 0.3)',
  },
  title: {
    fontSize: 22,
    fontWeight: 700,
    color: '#E0E6ED',
    margin: '0 0 6px',
  },
  subtitle: {
    fontSize: 14,
    color: '#6B7FA3',
    margin: 0,
  },
  offerCard: {
    backgroundColor: 'rgba(0, 212, 255, 0.04)',
    border: '1px solid rgba(0, 212, 255, 0.15)',
    borderRadius: 16,
    padding: 24,
    marginBottom: 16,
  },
  amountSection: {
    textAlign: 'center',
    marginBottom: 20,
  },
  amountLabel: {
    fontSize: 12,
    fontWeight: 600,
    color: '#6B7FA3',
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  amountRange: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
    marginTop: 8,
  },
  amountValue: {
    fontSize: 26,
    fontWeight: 700,
    color: '#00D4FF',
    fontFamily: '"JetBrains Mono", monospace',
  },
  amountDash: {
    fontSize: 20,
    color: '#4A5F80',
  },
  metricsRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '16px 0',
    borderTop: '1px solid rgba(255,255,255,0.06)',
    borderBottom: '1px solid rgba(255,255,255,0.06)',
  },
  metric: {
    flex: 1,
    textAlign: 'center',
  },
  metricValue: {
    display: 'block',
    fontSize: 18,
    fontWeight: 700,
    color: '#E0E6ED',
    fontFamily: '"JetBrains Mono", monospace',
  },
  metricLabel: {
    display: 'block',
    fontSize: 11,
    color: '#6B7FA3',
    marginTop: 4,
  },
  metricDivider: {
    width: 1,
    height: 36,
    backgroundColor: 'rgba(255,255,255,0.08)',
  },
  tenureSection: {
    marginTop: 18,
  },
  tenureLabel: {
    fontSize: 12,
    fontWeight: 600,
    color: '#6B7FA3',
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  tenureOptions: {
    display: 'flex',
    gap: 8,
    marginTop: 10,
    flexWrap: 'wrap',
  },
  tenureBtn: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    padding: '10px 16px',
    backgroundColor: 'rgba(255,255,255,0.04)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: 10,
    color: '#B8C4D6',
    cursor: 'pointer',
    fontSize: 14,
    fontWeight: 600,
    fontFamily: '"DM Sans", sans-serif',
    transition: 'all 0.2s',
  },
  tenureBtnActive: {
    backgroundColor: 'rgba(0, 212, 255, 0.15)',
    borderColor: '#00D4FF',
    color: '#00D4FF',
  },
  tenureEmi: {
    fontSize: 10,
    fontWeight: 400,
    color: '#6B7FA3',
    marginTop: 3,
    fontFamily: '"JetBrains Mono", monospace',
  },
  riskCard: {
    backgroundColor: 'rgba(255,255,255,0.02)',
    border: '1px solid rgba(255,255,255,0.06)',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  riskHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  riskTitle: {
    fontSize: 13,
    fontWeight: 600,
    color: '#B8C4D6',
  },
  riskBadge: {
    padding: '3px 10px',
    borderRadius: 6,
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: 0.5,
    fontFamily: '"JetBrains Mono", monospace',
  },
  riskFactors: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 6,
  },
  factorChip: {
    fontSize: 11,
    padding: '2px 8px',
    borderRadius: 5,
    backgroundColor: 'rgba(0, 230, 118, 0.08)',
    color: '#80E8A8',
    fontFamily: '"JetBrains Mono", monospace',
  },
  riskFlags: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 6,
  },
  flagChip: {
    fontSize: 11,
    padding: '2px 8px',
    borderRadius: 5,
    backgroundColor: 'rgba(255, 183, 77, 0.08)',
    color: '#FFB74D',
    fontFamily: '"JetBrains Mono", monospace',
  },
  conditions: {
    marginBottom: 16,
    padding: '12px 16px',
    backgroundColor: 'rgba(255,255,255,0.02)',
    borderRadius: 10,
  },
  conditionText: {
    fontSize: 12,
    color: '#8B9FC0',
    margin: '4px 0',
  },
  acceptBtn: {
    width: '100%',
    padding: '14px 24px',
    background: 'linear-gradient(135deg, #00D4FF 0%, #00E676 100%)',
    color: '#0B1120',
    border: 'none',
    borderRadius: 12,
    fontSize: 16,
    fontWeight: 700,
    cursor: 'pointer',
    fontFamily: '"DM Sans", sans-serif',
    transition: 'transform 0.2s, box-shadow 0.2s',
  },
  rejectionCard: {
    textAlign: 'center',
    padding: 32,
  },
  rejectIcon: {
    width: 56,
    height: 56,
    borderRadius: '50%',
    backgroundColor: 'rgba(255, 82, 82, 0.15)',
    color: '#FF5252',
    fontSize: 28,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    margin: '0 auto 14px',
    border: '2px solid rgba(255, 82, 82, 0.3)',
  },
  rejectionReason: {
    fontSize: 14,
    color: '#FF8A80',
    margin: '12px 0',
  },
  rejectionHelp: {
    fontSize: 13,
    color: '#6B7FA3',
    margin: 0,
  },
};
