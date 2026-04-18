/**
 * VideoCall.jsx — Video Call Component
 * Handles camera access, video display, periodic frame capture for face analysis,
 * and audio recording for STT.
 */

import React, { useRef, useEffect, useState, useCallback } from 'react';

export default function VideoCall({ sessionId, onFrame, onFaceStatus, isActive }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const frameIntervalRef = useRef(null);
  const [cameraReady, setCameraReady] = useState(false);
  const [faceDetected, setFaceDetected] = useState(false);
  const [error, setError] = useState(null);

  // Start camera
  useEffect(() => {
    if (!isActive) return;

    async function startCamera() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 640, height: 480, facingMode: 'user' },
          audio: false, // Audio handled separately
        });
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          setCameraReady(true);
        }
      } catch (err) {
        console.error('Camera error:', err);
        setError('Camera access denied. Please allow camera permissions.');
      }
    }

    startCamera();

    return () => {
      streamRef.current?.getTracks().forEach(t => t.stop());
      if (frameIntervalRef.current) clearInterval(frameIntervalRef.current);
    };
  }, [isActive]);

  // Periodic frame capture for face analysis (every 3 seconds)
  useEffect(() => {
    if (!cameraReady || !isActive) return;

    frameIntervalRef.current = setInterval(() => {
      captureFrame();
    }, 3000);

    return () => {
      if (frameIntervalRef.current) clearInterval(frameIntervalRef.current);
    };
  }, [cameraReady, isActive]);

  const captureFrame = useCallback(() => {
    if (!videoRef.current || !canvasRef.current) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');

    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    // Get base64 JPEG
    const dataUrl = canvas.toDataURL('image/jpeg', 0.7);
    const base64 = dataUrl.split(',')[1];

    onFrame?.(base64);
  }, [onFrame]);

  // Update face status from parent
  useEffect(() => {
    if (onFaceStatus) {
      setFaceDetected(onFaceStatus.face_detected);
    }
  }, [onFaceStatus]);

  if (error) {
    return (
      <div style={styles.errorContainer}>
        <div style={styles.errorIcon}>📷</div>
        <p style={styles.errorText}>{error}</p>
        <button
          style={styles.retryBtn}
          onClick={() => { setError(null); setCameraReady(false); }}
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      {/* Video Feed */}
      <div style={styles.videoWrapper}>
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          style={styles.video}
        />

        {/* Face detection indicator */}
        <div style={{
          ...styles.faceIndicator,
          backgroundColor: faceDetected ? 'rgba(0, 230, 118, 0.15)' : 'rgba(255, 82, 82, 0.15)',
          borderColor: faceDetected ? '#00E676' : '#FF5252',
        }}>
          <div style={{
            ...styles.faceDot,
            backgroundColor: faceDetected ? '#00E676' : '#FF5252',
          }} />
          <span style={styles.faceText}>
            {faceDetected ? 'Face detected' : 'Position your face'}
          </span>
        </div>

        {/* Recording indicator */}
        {isActive && (
          <div style={styles.recIndicator}>
            <div style={styles.recDot} />
            <span style={styles.recText}>LIVE</span>
          </div>
        )}

        {/* Camera loading */}
        {!cameraReady && isActive && (
          <div style={styles.loading}>
            <div style={styles.spinner} />
            <p style={{ color: '#8B9FC0', marginTop: 12 }}>Starting camera...</p>
          </div>
        )}
      </div>

      {/* Hidden canvas for frame capture */}
      <canvas ref={canvasRef} style={{ display: 'none' }} />
    </div>
  );
}

const styles = {
  container: {
    position: 'relative',
    width: '100%',
  },
  videoWrapper: {
    position: 'relative',
    width: '100%',
    aspectRatio: '4/3',
    backgroundColor: '#0B1120',
    borderRadius: 16,
    overflow: 'hidden',
    border: '1px solid rgba(0, 212, 255, 0.15)',
  },
  video: {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
    transform: 'scaleX(-1)', // Mirror
  },
  faceIndicator: {
    position: 'absolute',
    bottom: 12,
    left: 12,
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '6px 14px',
    borderRadius: 20,
    border: '1px solid',
    backdropFilter: 'blur(8px)',
    transition: 'all 0.3s ease',
  },
  faceDot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
    transition: 'background-color 0.3s',
  },
  faceText: {
    fontSize: 12,
    fontWeight: 500,
    color: '#E0E6ED',
    fontFamily: '"DM Sans", sans-serif',
  },
  recIndicator: {
    position: 'absolute',
    top: 12,
    right: 12,
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: '4px 12px',
    borderRadius: 12,
    backgroundColor: 'rgba(255, 82, 82, 0.2)',
  },
  recDot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
    backgroundColor: '#FF5252',
    animation: 'pulse 1.5s infinite',
  },
  recText: {
    fontSize: 11,
    fontWeight: 600,
    color: '#FF5252',
    letterSpacing: 1,
    fontFamily: '"JetBrains Mono", monospace',
  },
  loading: {
    position: 'absolute',
    inset: 0,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(11, 17, 32, 0.9)',
  },
  spinner: {
    width: 36,
    height: 36,
    border: '3px solid rgba(0, 212, 255, 0.2)',
    borderTopColor: '#00D4FF',
    borderRadius: '50%',
    animation: 'spin 1s linear infinite',
  },
  errorContainer: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 40,
    backgroundColor: 'rgba(255, 82, 82, 0.05)',
    borderRadius: 16,
    border: '1px solid rgba(255, 82, 82, 0.2)',
  },
  errorIcon: { fontSize: 48, marginBottom: 12 },
  errorText: { color: '#FF8A80', fontSize: 14, textAlign: 'center', fontFamily: '"DM Sans", sans-serif' },
  retryBtn: {
    marginTop: 16,
    padding: '8px 24px',
    backgroundColor: '#00D4FF',
    color: '#0B1120',
    border: 'none',
    borderRadius: 8,
    fontWeight: 600,
    cursor: 'pointer',
    fontFamily: '"DM Sans", sans-serif',
  },
};
