"""
face_analyzer.py — Face Analysis Engine
Uses MediaPipe Face Mesh for face detection and landmark extraction.
Implements age estimation via facial proportions + texture analysis.
Includes liveness detection (blink, head movement) and face consistency checks.
"""

import cv2
import numpy as np
import logging
import base64
from typing import Optional, Tuple, List
from models import FaceAnalysisResult
import mediapipe as mp   

logger = logging.getLogger(__name__)

# ─── MediaPipe Setup (lazy load) ─────────────────────────────

_face_mesh = None
_face_detection = None

def _init_mediapipe():
    """Initialize MediaPipe models using new Tasks API (0.10.x+)."""
    global _face_mesh, _face_detection
    if _face_mesh is not None:
        return
    try:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision

        # New Tasks API — FaceLandmarker replaces FaceMesh
        face_mesh_options = mp_vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=None),
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            running_mode=mp_vision.RunningMode.IMAGE
        )
        _face_mesh = mp_vision.FaceLandmarker.create_from_options(face_mesh_options)

        face_det_options = mp_vision.FaceDetectorOptions(
            base_options=mp_python.BaseOptions(model_asset_path=None),
            min_detection_confidence=0.5,
            running_mode=mp_vision.RunningMode.IMAGE
        )
        _face_detection = mp_vision.FaceDetector.create_from_options(face_det_options)

        logger.info("MediaPipe FaceLandmarker + FaceDetector initialized (Tasks API).")
    except Exception as e:
        logger.error(f"Failed to init MediaPipe: {e}")


# ─── Face History (for consistency checks) ───────────────────

class FaceTracker:
    """Tracks face embeddings across frames for consistency."""

    def __init__(self, max_history: int = 30):
        self.landmarks_history: List[np.ndarray] = []
        self.blink_count: int = 0
        self.head_movement_score: float = 0.0
        self.max_history = max_history
        self._prev_ear: float = 0.3     # eye aspect ratio for blink detection

    def update(self, landmarks: np.ndarray):
        """Add a new set of face landmarks."""
        if len(self.landmarks_history) >= self.max_history:
            self.landmarks_history.pop(0)
        self.landmarks_history.append(landmarks)

        # Detect blinks via Eye Aspect Ratio (EAR)
        ear = self._compute_ear(landmarks)
        if self._prev_ear > 0.2 and ear < 0.18:
            self.blink_count += 1
        self._prev_ear = ear

        # Compute head movement from nose tip displacement
        if len(self.landmarks_history) >= 2:
            prev_nose = self.landmarks_history[-2][1]   # landmark 1 = nose tip
            curr_nose = landmarks[1]
            movement = np.linalg.norm(curr_nose - prev_nose)
            # Exponential moving average
            self.head_movement_score = float(0.9 * self.head_movement_score + 0.1 * movement)

    def _compute_ear(self, landmarks: np.ndarray) -> float:
        """
        Eye Aspect Ratio — ratio of eye height to width.
        Drops below ~0.18 during a blink.
        MediaPipe landmarks: left eye = 33,160,158,133,153,144
                              right eye = 362,385,387,263,373,380
        """
        try:
            # Right eye landmarks (using indices from MediaPipe face mesh)
            p1 = landmarks[33]    # outer corner
            p2 = landmarks[133]   # inner corner
            p3 = landmarks[160]   # upper lid top
            p4 = landmarks[144]   # lower lid bottom
            p5 = landmarks[158]   # upper lid top 2
            p6 = landmarks[153]   # lower lid bottom 2

            # Horizontal distance
            horizontal = np.linalg.norm(p1 - p2)
            # Vertical distances
            vertical1 = np.linalg.norm(p3 - p4)
            vertical2 = np.linalg.norm(p5 - p6)

            if horizontal < 1e-6:
                return 0.3

            ear = (vertical1 + vertical2) / (2.0 * horizontal)
            return float(ear)
        except (IndexError, ValueError):
            return float(0.3)

    def get_liveness_score(self) -> float:
        """
        Compute liveness score based on:
        - Blink detection (real faces blink, photos don't)
        - Head micro-movements (real faces have subtle motion)
        Returns 0-1, higher = more likely a real person.
        """
        score = 0.0

        # Blink component (0-0.4) — at least 1 blink in 30 frames = good
        if self.blink_count >= 2:
            score += 0.4
        elif self.blink_count >= 1:
            score += 0.25

        # Head movement component (0-0.3)
        if self.head_movement_score > 0.002:
            score += 0.3
        elif self.head_movement_score > 0.001:
            score += 0.15

        # Frame count component (0-0.3) — more frames analyzed = more confident
        frame_ratio = min(len(self.landmarks_history) / self.max_history, 1.0)
        score += frame_ratio * 0.3

        return min(score, 1.0)

    def is_same_person(self) -> bool:
        """Check if the face has been consistent across frames."""
        if len(self.landmarks_history) < 5:
            return True   # Not enough data to judge

        # Compare first and last face — nose-to-eye ratio should be stable
        try:
            first = self.landmarks_history[0]
            last = self.landmarks_history[-1]

            # Inter-pupillary distance ratio to nose length
            def face_signature(lm):
                left_eye = lm[33]
                right_eye = lm[263]
                nose = lm[1]
                chin = lm[152]
                ipd = np.linalg.norm(left_eye - right_eye)
                nose_len = np.linalg.norm(nose - chin)
                return ipd / (nose_len + 1e-6)

            sig_first = face_signature(first)
            sig_last = face_signature(last)
            diff = abs(sig_first - sig_last)

            # If ratio changes by more than 20%, likely a different person
            return bool(diff < 0.2)
        except (IndexError, ValueError):
            return True


# ─── Module-level tracker ────────────────────────────────────
# In production, you'd have one tracker per session
_trackers: dict = {}


def get_tracker(session_id: str) -> FaceTracker:
    """Get or create a face tracker for a session."""
    if session_id not in _trackers:
        _trackers[session_id] = FaceTracker()
    return _trackers[session_id]


def clear_tracker(session_id: str):
    """Clean up tracker when session ends."""
    _trackers.pop(session_id, None)


# ─── Age Estimation ──────────────────────────────────────────

def estimate_age_from_landmarks(landmarks: np.ndarray, frame: np.ndarray) -> Tuple[int, float]:
    """
    Estimate age using facial landmark ratios + skin texture analysis.
    
    This is a simplified heuristic model:
    - Facial proportion ratios change with age
    - Skin texture (wrinkle density via Laplacian variance) correlates with age
    - Combined gives a rough estimate
    
    Returns: (estimated_age, confidence)
    """
    try:
        # 1. Facial proportion features
        left_eye = landmarks[33]
        right_eye = landmarks[263]
        nose_tip = landmarks[1]
        chin = landmarks[152]
        forehead = landmarks[10]
        left_mouth = landmarks[61]
        right_mouth = landmarks[291]

        # Inter-pupillary distance
        ipd = np.linalg.norm(left_eye - right_eye)
        # Face height (forehead to chin)
        face_height = np.linalg.norm(forehead - chin)
        # Nose to chin ratio
        nose_chin = np.linalg.norm(nose_tip - chin)
        # Mouth width
        mouth_width = np.linalg.norm(left_mouth - right_mouth)

        # Ratios (these shift with age)
        ratio_ipd_height = ipd / (face_height + 1e-6)
        ratio_nose_chin = nose_chin / (face_height + 1e-6)
        ratio_mouth_ipd = mouth_width / (ipd + 1e-6)

        # 2. Skin texture analysis (wrinkle proxy)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        h, w = gray.shape

        # Get forehead region for texture analysis
        fh_x = int(forehead[0] * w) if forehead[0] <= 1 else int(forehead[0])
        fh_y = int(forehead[1] * h) if forehead[1] <= 1 else int(forehead[1])

        # Crop a small forehead patch
        patch_size = max(20, int(ipd * w * 0.3)) if ipd <= 1 else max(20, int(ipd * 0.3))
        y1 = max(0, fh_y - patch_size)
        y2 = min(h, fh_y + patch_size // 2)
        x1 = max(0, fh_x - patch_size // 2)
        x2 = min(w, fh_x + patch_size // 2)

        if y2 > y1 and x2 > x1:
            forehead_patch = gray[y1:y2, x1:x2]
            # Laplacian variance — higher = more texture/wrinkles
            texture_score = cv2.Laplacian(forehead_patch, cv2.CV_64F).var()
        else:
            texture_score = 50.0

        # 3. Combine into age estimate (simplified linear model)
        # These weights are approximations — a real system would use a trained model
        base_age = 25.0

        # Proportion adjustments (faces get longer relative to width with age)
        if ratio_ipd_height < 0.38:
            base_age += 10
        elif ratio_ipd_height > 0.44:
            base_age -= 5

        # Texture adjustment (more texture = older)
        if texture_score > 200:
            base_age += 15
        elif texture_score > 100:
            base_age += 8
        elif texture_score > 50:
            base_age += 3
        elif texture_score < 20:
            base_age -= 5

        # Mouth-to-IPD ratio (lips thin with age)
        if ratio_mouth_ipd < 0.55:
            base_age += 5

        estimated_age = max(18, min(70, int(base_age)))

        # Confidence based on face detection quality
        confidence = 0.6 if texture_score > 10 else 0.3

        return estimated_age, confidence

    except Exception as e:
        logger.error(f"Age estimation error: {e}")
        return 30, 0.2


# ─── Main Analysis Function ─────────────────────────────────

async def analyze_face(
    frame_base64: str,
    session_id: str,
    declared_age: Optional[int] = None
) -> FaceAnalysisResult:
    """
    Analyze a video frame for face detection, age estimation, and liveness.
    
    Args:
        frame_base64: Base64-encoded JPEG/PNG frame from the video call
        session_id: Current session ID for tracking
        declared_age: Age declared by customer (for mismatch detection)
    
    Returns:
        FaceAnalysisResult with all findings
    """
    _init_mediapipe()

    try:
        # Decode base64 frame
        img_bytes = base64.b64decode(frame_base64)
        img_array = np.frombuffer(img_bytes, dtype=np.uint8)
        frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

        if frame is None:
            return FaceAnalysisResult(face_detected=False)

        # Convert to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Run face mesh
        if _face_mesh is None:
            return FaceAnalysisResult(face_detected=False)

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        results = _face_mesh.detect(mp_image)
        if not results.face_landmarks:
            return FaceAnalysisResult(face_detected=False)
        face_landmarks = results.face_landmarks[0]
        landmarks = np.array(
            [(lm.x, lm.y, lm.z) for lm in face_landmarks]
)

        # Update face tracker
        tracker = get_tracker(session_id)
        tracker.update(landmarks)

        # Age estimation
        estimated_age, age_confidence = estimate_age_from_landmarks(landmarks, frame)

        # Liveness score
        liveness = tracker.get_liveness_score()

        # Face consistency check
        face_consistent = tracker.is_same_person()

        # Age mismatch check (if customer declared their age)
        age_mismatch = False
        if declared_age is not None:
            age_diff = abs(estimated_age - declared_age)
            age_mismatch = age_diff > 10   # Flag if >10 year difference

        result = FaceAnalysisResult(
            face_detected=True,
            estimated_age=estimated_age,
            age_confidence=age_confidence,
            liveness_score=liveness,
            face_match_consistent=face_consistent,
            age_mismatch_flag=age_mismatch
        )

        logger.info(
            f"Face analysis: age={estimated_age}, liveness={liveness:.2f}, "
            f"consistent={face_consistent}, age_mismatch={age_mismatch}"
        )

        return result

    except Exception as e:
        logger.error(f"Face analysis error: {e}")
        return FaceAnalysisResult(face_detected=False)


async def analyze_frame_quick(frame_base64: str) -> dict:
    """
    Quick frame analysis — just face detection + basic metrics.
    Used for real-time feedback during the call (not full analysis).
    """
    _init_mediapipe()

    try:
        img_bytes = base64.b64decode(frame_base64)
        img_array = np.frombuffer(img_bytes, dtype=np.uint8)
        frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

        if frame is None:
            return {"face_detected": False}

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        if _face_detection is None:
            return {"face_detected": False}

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        results = _face_detection.detect(mp_image)
        if results.detections:
            detection = results.detections[0]
            bbox = detection.bounding_box
            h, w = frame.shape[:2]
            return {
                "face_detected": True,
                "confidence": detection.categories[0].score,
                "bbox": {
                    "x": bbox.origin_x / w,
                    "y": bbox.origin_y / h,
                    "w": bbox.width / w,
                    "h": bbox.height / h,
                }
            }
        return {"face_detected": False}

    except Exception as e:
        logger.error(f"Quick analysis error: {e}")
        return {"face_detected": False}
