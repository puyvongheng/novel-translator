"""
Auto Face Tracking & Intelligent Video Reframe Engine (16:9 to 9:16 TikTok / Shorts)
5-Stage Architecture:
  1. Detect Face / Person (MediaPipe, OpenCV Haar Cascades & HOG Person Detector)
  2. Track Position (X, Y) with Identity Persistence across frames
  3. Calculate 9:16 Crop Window & Smart Decision Engine (1 Person vs Multi-Person vs Speaker)
  4. Smooth Camera Movement & Anti-Dizziness (Dead-Zone Stabilizer, Max Pan Speed, Scene Cuts, SciPy Steadicam)
  5. Generate Crop Keyframes for Timeline & Direct 9:16 Export
"""

import os
import sys
import math
import subprocess
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple, Callable
import cv2
import numpy as np

# SciPy for cinematic camera smoothing
try:
    from scipy.signal import savgol_filter
    from scipy.ndimage import gaussian_filter1d
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

# MediaPipe optional import
try:
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = hasattr(mp, "solutions") and hasattr(mp.solutions, "face_detection")
except Exception:
    MEDIAPIPE_AVAILABLE = False


@dataclass
class DetectedSubject:
    id: int
    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    center_x: float
    center_y: float
    mar: float = 0.0  # mouth aspect ratio (talking score)
    is_speaking: bool = False
    area: float = 0.0
    confidence: float = 1.0
    source: str = "face"  # "face", "person", or "fused"


class SubjectTracker:
    """
    Maintains persistent tracks for detected persons and faces across frames.
    Calculates spatial continuity, speaker state history, and smooth center predictions.
    """
    def __init__(self, max_missed_frames: int = 6):
        self.max_missed_frames = max_missed_frames
        self.next_id = 1
        self.tracks: Dict[int, Dict[str, Any]] = {}
        self.active_speaker_id: Optional[int] = None
        self.speaker_switch_hold_frames = 0

    def update(self, detections: List[DetectedSubject], frame_idx: int) -> List[DetectedSubject]:
        matched_track_ids = set()
        updated_subjects: List[DetectedSubject] = []

        for det in detections:
            best_id = None
            best_dist = 999999.0

            for tid, tinfo in self.tracks.items():
                if tid in matched_track_ids:
                    continue
                # Euclidean distance between detection center and track last center
                dist = math.hypot(det.center_x - tinfo["last_x"], det.center_y - tinfo["last_y"])
                if dist < best_dist and dist < max(tinfo["w"], 200):
                    best_dist = dist
                    best_id = tid

            if best_id is not None:
                tid = best_id
                tinfo = self.tracks[tid]
                # Update track with exponential moving average for center
                alpha = 0.70
                smooth_x = alpha * det.center_x + (1.0 - alpha) * tinfo["last_x"]
                smooth_y = alpha * det.center_y + (1.0 - alpha) * tinfo["last_y"]
                tinfo["last_x"] = smooth_x
                tinfo["last_y"] = smooth_y
                tinfo["w"] = det.bbox[2]
                tinfo["h"] = det.bbox[3]
                tinfo["last_seen"] = frame_idx
                tinfo["mar_history"].append(det.mar)
                if len(tinfo["mar_history"]) > 8:
                    tinfo["mar_history"].pop(0)

                # Speaking if average MAR > 0.045
                avg_mar = float(np.mean(tinfo["mar_history"]))
                det.is_speaking = avg_mar > 0.045
                det.id = tid
                det.center_x = smooth_x
                det.center_y = smooth_y
                matched_track_ids.add(tid)
            else:
                tid = self.next_id
                self.next_id += 1
                self.tracks[tid] = {
                    "last_x": det.center_x,
                    "last_y": det.center_y,
                    "w": det.bbox[2],
                    "h": det.bbox[3],
                    "last_seen": frame_idx,
                    "mar_history": [det.mar]
                }
                det.id = tid
                matched_track_ids.add(tid)

            updated_subjects.append(det)

        # Remove stale tracks
        stale_ids = [tid for tid, info in self.tracks.items() if (frame_idx - info["last_seen"]) > self.max_missed_frames]
        for tid in stale_ids:
            del self.tracks[tid]

        return updated_subjects


class AutoReframeEngine:
    """
    Professional 5-Stage Smart Auto Reframe Engine (16:9 Landscape -> 9:16 Vertical for TikTok / Shorts)
    Features:
    - Smart Decision Engine: Decides whether to frame 1 person or multiple people (group framing)
    - Anti-Dizziness Camera Stabilizer (Dead-Zone Pan Dead-Band) to prevent viewer fatigue
    - Velocity Limiter (Cinematic Pan Speed Clamp)
    - Scene Cut Jump-Cut Detection (No ugly slow glides across camera cuts)
    - MediaPipe FaceMesh + Local Haar Cascades + OpenCV HOG Person Detector
    """

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        self.log_callback = log_callback or (lambda msg: None)
        self._stop_requested = False
        self._models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
        self._init_detectors()

    def log(self, msg: str):
        if self.log_callback:
            self.log_callback(msg)

    def request_stop(self):
        self._stop_requested = True

    # -------------------------------------------------------------
    # 1. CORE DETECTION: FACES & PERSONS
    # -------------------------------------------------------------
    def _init_detectors(self):
        """Initializes Face and Person Detectors (MediaPipe + Local Haar Cascades + HOG)"""
        self.mp_detector = None
        self.mp_mesh = None
        self.face_cascade = None
        self.profile_cascade = None
        self.upperbody_cascade = None
        self.hog_person = None

        # 1. MediaPipe if available
        if MEDIAPIPE_AVAILABLE:
            try:
                mp_face_detection = mp.solutions.face_detection
                self.mp_detector = mp_face_detection.FaceDetection(
                    model_selection=1,
                    min_detection_confidence=0.5
                )
                mp_mesh_module = mp.solutions.face_mesh
                self.mp_mesh = mp_mesh_module.FaceMesh(
                    static_image_mode=False,
                    max_num_faces=4,
                    refine_landmarks=True,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5
                )
            except Exception as e:
                self.mp_detector = None
                self.mp_mesh = None

        # 2. Local Haar Cascades (Frontal Face, Profile Face, Upper Body)
        try:
            f_face = os.path.join(self._models_dir, "haarcascade_frontalface_default.xml")
            f_prof = os.path.join(self._models_dir, "haarcascade_profileface.xml")
            f_up = os.path.join(self._models_dir, "haarcascade_upperbody.xml")

            if os.path.exists(f_face):
                self.face_cascade = cv2.CascadeClassifier(f_face)
            if os.path.exists(f_prof):
                self.profile_cascade = cv2.CascadeClassifier(f_prof)
            if os.path.exists(f_up):
                self.upperbody_cascade = cv2.CascadeClassifier(f_up)
        except Exception as e:
            self.log(f"⚠️ [Reframe] Cascade init note: {e}")

        # 3. OpenCV HOG Person Detector (Full/Upper Body)
        try:
            hog = cv2.HOGDescriptor()
            hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            self.hog_person = hog
        except Exception:
            self.hog_person = None

    def _calc_mouth_aspect_ratio(self, landmarks, w: int, h: int) -> float:
        """Calculates Mouth Aspect Ratio (MAR) for active talking detection."""
        try:
            p13 = np.array([landmarks[13].x * w, landmarks[13].y * h])
            p14 = np.array([landmarks[14].x * w, landmarks[14].y * h])
            p61 = np.array([landmarks[61].x * w, landmarks[61].y * h])
            p291 = np.array([landmarks[291].x * w, landmarks[291].y * h])

            vertical = np.linalg.norm(p13 - p14)
            horizontal = np.linalg.norm(p61 - p291)
            if horizontal > 1.0:
                return float(vertical / horizontal)
        except Exception:
            pass
        return 0.0

    def _detect_faces_and_persons(self, frame_bgr: np.ndarray, frame_rgb: np.ndarray) -> List[DetectedSubject]:
        """
        Multi-modal detector that detects both faces and persons.
        Returns a list of DetectedSubject with coordinates, size, and speech activity.
        """
        h, w = frame_bgr.shape[:2]
        subjects: List[DetectedSubject] = []

        # 1. Try MediaPipe FaceMesh / Detection
        if self.mp_mesh:
            try:
                results = self.mp_mesh.process(frame_rgb)
                if results and results.multi_face_landmarks:
                    for idx, lms in enumerate(results.multi_face_landmarks):
                        xs = [lm.x * w for lm in lms.landmark]
                        ys = [lm.y * h for lm in lms.landmark]
                        fx = max(0, min(xs))
                        fy = max(0, min(ys))
                        fw = min(w - fx, max(xs) - fx)
                        fh = min(h - fy, max(ys) - fy)
                        mar = self._calc_mouth_aspect_ratio(lms.landmark, w, h)

                        # Estimate upper torso around the face
                        cx = fx + fw / 2.0
                        cy = fy + fh / 2.0
                        subjects.append(DetectedSubject(
                            id=idx,
                            bbox=(int(fx), int(fy), int(fw), int(fh)),
                            center_x=cx,
                            center_y=cy,
                            mar=mar,
                            is_speaking=mar > 0.05,
                            area=fw * fh,
                            confidence=0.95,
                            source="mediapipe_mesh"
                        ))
                    return subjects
            except Exception:
                pass

        # 2. Local Haar Cascades for Faces (Frontal + Profile)
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        face_boxes = []

        if self.face_cascade:
            faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=4, minSize=(40, 40))
            if len(faces) > 0:
                face_boxes.extend(faces)

        if len(face_boxes) == 0 and self.profile_cascade:
            profiles = self.profile_cascade.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=4, minSize=(40, 40))
            if len(profiles) > 0:
                face_boxes.extend(profiles)

        # 3. If no faces found, check HOG Person / Upper Body Detector
        person_boxes = []
        if len(face_boxes) == 0 and self.hog_person:
            try:
                small = cv2.resize(frame_bgr, (640, int(640 * h / w)))
                scale_w = w / 640.0
                scale_h = h / (640 * h / w)
                rects, weights = self.hog_person.detectMultiScale(small, winStride=(8, 8), padding=(8, 8), scale=1.05)
                for (rx, ry, rw, rh), wt in zip(rects, weights):
                    if wt > 0.3:
                        person_boxes.append((int(rx * scale_w), int(ry * scale_h), int(rw * scale_w), int(rh * scale_h)))
            except Exception:
                pass

        if len(face_boxes) == 0 and len(person_boxes) == 0 and self.upperbody_cascade:
            try:
                ups = self.upperbody_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=3, minSize=(60, 60))
                if len(ups) > 0:
                    person_boxes.extend(ups)
            except Exception:
                pass

        # Convert face boxes to DetectedSubjects
        for idx, (fx, fy, fw, fh) in enumerate(face_boxes):
            cx = fx + fw / 2.0
            cy = fy + fh / 2.0
            subjects.append(DetectedSubject(
                id=idx,
                bbox=(int(fx), int(fy), int(fw), int(fh)),
                center_x=cx,
                center_y=cy,
                mar=0.0,
                is_speaking=False,
                area=float(fw * fh),
                confidence=0.85,
                source="haar_face"
            ))

        # Add person boxes if no face was already inside them
        for idx, (px, py, pw, ph) in enumerate(person_boxes):
            # Check if any face already covers this
            pcx = px + pw / 2.0
            pcy = py + ph / 2.0
            already_covered = any(abs(s.center_x - pcx) < pw * 0.4 for s in subjects)
            if not already_covered:
                subjects.append(DetectedSubject(
                    id=100 + idx,
                    bbox=(int(px), int(py), int(pw), int(ph)),
                    center_x=pcx,
                    center_y=pcy,
                    mar=0.0,
                    is_speaking=False,
                    area=float(pw * ph),
                    confidence=0.70,
                    source="hog_person"
                ))

        return subjects

    # -------------------------------------------------------------
    # 2. VIDEO TRACKING, DECISION ENGINE & DEAD-ZONE STABILIZER
    # -------------------------------------------------------------
    def analyze_video(
        self,
        video_path: str,
        target_aspect_w: int = 9,
        target_aspect_h: int = 16,
        mode: str = "smart",  # "smart", "speaker", "multi", "face"
        smoothness: float = 0.85,  # 0.2 to 1.0
        dead_zone_ratio: float = 0.15,  # 15% dead band to prevent dizziness
        max_pan_speed_px_per_sec: float = 380.0,  # speed clamp
        sample_interval: int = 2,  # sample every N frames
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Scans video and computes 9:16 vertical crop coordinates using the 5-stage pipeline:
        1. Detect Face & Person
        2. Track Position (X, Y)
        3. Smart Decision: 1 Person vs Multi-Person vs Speaker Focus
        4. Anti-Dizziness Stabilization (Dead-Zone Filter + Max Pan Speed Clamp)
        5. Generate Keyframes & Trajectory
        """
        self._stop_requested = False
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video with OpenCV: {video_path}")

        vw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1920)
        vh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1080)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 1)
        dur = total_frames / max(1.0, fps)

        # 9:16 Crop Window Dimensions
        crop_h = vh
        crop_w = int(vh * (target_aspect_w / target_aspect_h))
        if crop_w > vw:
            crop_w = vw
            crop_h = int(vw * (target_aspect_h / target_aspect_w))

        max_crop_x = max(0, vw - crop_w)
        default_crop_x = max_crop_x // 2
        dead_zone_px = int(crop_w * max(0.05, min(0.35, dead_zone_ratio)))

        self.log(
            f"🎬 [Smart Reframe] {vw}x{vh} @ {fps:.1f}fps | TikTok Crop: {crop_w}x{crop_h} | "
            f"Mode: {mode.upper()} | Dead-Zone: {dead_zone_px}px ({int(dead_zone_ratio*100)}%)"
        )

        tracker = SubjectTracker(max_missed_frames=int(fps * 0.8))

        # Tracking state
        raw_target_x = []
        stabilized_x = []
        frame_indices = []
        timestamps = []
        decisions = []
        scene_cut_indices = set()

        last_known_target_x = default_crop_x
        curr_stabilized_x = default_crop_x
        prev_sample_frame_gray = None

        decision_counts = {"single": 0, "group": 0, "speaker": 0, "steady_locked": 0}

        frame_idx = 0
        while cap.isOpened() and not self._stop_requested:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % sample_interval == 0:
                t = frame_idx / fps
                h, w = frame.shape[:2]
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                # --- A. SCENE CUT DETECTION ---
                is_scene_cut = False
                if prev_sample_frame_gray is not None:
                    # Compare histogram difference
                    hist1 = cv2.calcHist([prev_sample_frame_gray], [0], None, [32], [0, 256])
                    hist2 = cv2.calcHist([gray_frame], [0], None, [32], [0, 256])
                    cv2.normalize(hist1, hist1)
                    cv2.normalize(hist2, hist2)
                    comp = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
                    if comp < 0.35:  # Significant scene change
                        is_scene_cut = True
                prev_sample_frame_gray = gray_frame

                # --- B. DETECT FACE & PERSON ---
                detected = self._detect_faces_and_persons(frame, rgb_frame)

                # --- C. TRACK POSITION ACROSS FRAMES ---
                active_subjects = tracker.update(detected, frame_idx)

                # --- D. SMART 9:16 CROP DECISION ENGINE ---
                # Decide whether to frame 1 person or multiple people (group framing)
                target_focus_x = last_known_target_x + (crop_w / 2.0)
                frame_decision = "steady"

                if not active_subjects:
                    # 0 subjects detected: hold last known position
                    target_focus_x = last_known_target_x + (crop_w / 2.0)
                    frame_decision = "none"
                elif len(active_subjects) == 1 or mode == "face":
                    # Single person detected
                    target_focus_x = active_subjects[0].center_x
                    frame_decision = "single"
                    decision_counts["single"] += 1
                else:
                    # Multiple people detected (2 or more)
                    min_x = min(s.bbox[0] for s in active_subjects)
                    max_x = max(s.bbox[0] + s.bbox[2] for s in active_subjects)
                    group_span = max_x - min_x

                    # Check if all people fit inside the 9:16 crop window with comfortable margin
                    can_fit_group = (group_span <= crop_w * 0.88)

                    if mode == "multi" or (mode == "smart" and can_fit_group):
                        # DECISION: MULTI-PERSON GROUP FRAMING
                        # Center the 9:16 window on the entire group!
                        target_focus_x = (min_x + max_x) / 2.0
                        frame_decision = "group"
                        decision_counts["group"] += 1
                    else:
                        # People are too far apart to fit together in 9:16 crop!
                        # Check if someone is actively speaking
                        speakers = [s for s in active_subjects if s.is_speaking or s.mar > 0.045]
                        if speakers or mode == "speaker":
                            best_speaker = max(active_subjects, key=lambda s: s.mar)
                            target_focus_x = best_speaker.center_x
                            frame_decision = "speaker"
                            decision_counts["speaker"] += 1
                        else:
                            # Frame dominant/primary subject (largest bounding box)
                            primary = max(active_subjects, key=lambda s: s.area)
                            target_focus_x = primary.center_x
                            frame_decision = "primary"
                            decision_counts["single"] += 1

                # Convert focus center to crop left X clamped
                ideal_crop_left = int(target_focus_x - (crop_w / 2.0))
                ideal_crop_left = max(0, min(max_crop_x, ideal_crop_left))
                last_known_target_x = ideal_crop_left

                # --- E. ANTI-DIZZINESS STABILIZER (DEAD-ZONE PAN DEAD-BAND) ---
                # If subject displacement is within the dead-zone threshold,
                # THE CAMERA REMAINS ABSOLUTELY LOCKED AND STATIC.
                # This prevents all micro-jitter, breathing, and viewer nausea!
                diff_x = ideal_crop_left - curr_stabilized_x

                if is_scene_cut:
                    # Jump cut: snap immediately to new scene framing
                    curr_stabilized_x = ideal_crop_left
                    scene_cut_indices.add(len(stabilized_x))
                elif abs(diff_x) <= dead_zone_px:
                    # Within dead zone: CAMERA DOES NOT MOVE!
                    decision_counts["steady_locked"] += 1
                    # Keep curr_stabilized_x unchanged
                else:
                    # Subject stepped outside dead zone: smoothly pan camera
                    # Shift camera just enough to keep subject in comfortable window
                    if diff_x > 0:
                        desired_x = ideal_crop_left - dead_zone_px
                    else:
                        desired_x = ideal_crop_left + dead_zone_px

                    # Clamp pan speed so camera pan is cinematic and never whips violently
                    dt = sample_interval / fps
                    max_delta_px = max_pan_speed_px_per_sec * dt
                    step = desired_x - curr_stabilized_x
                    if abs(step) > max_delta_px:
                        step = math.copysign(max_delta_px, step)
                    curr_stabilized_x = int(curr_stabilized_x + step)

                curr_stabilized_x = max(0, min(max_crop_x, curr_stabilized_x))

                raw_target_x.append(ideal_crop_left)
                stabilized_x.append(curr_stabilized_x)
                frame_indices.append(frame_idx)
                timestamps.append(t)
                decisions.append(frame_decision)

                if progress_callback and total_frames > 0 and (frame_idx % (sample_interval * 15) == 0):
                    pct = min(0.70, (frame_idx / total_frames) * 0.70)
                    progress_callback(pct, f"AI Tracking & Smart Framing ({int(pct*100)}%)...")

            frame_idx += 1

        cap.release()

        if self._stop_requested:
            self.log("🛑 [Smart Reframe] Analysis cancelled by user.")
            return {}

        if not stabilized_x:
            stabilized_x = [default_crop_x]
            raw_target_x = [default_crop_x]
            frame_indices = [0]
            timestamps = [0.0]
            decisions = ["none"]

        # --- F. CINEMATIC SCIPY STEADICAM SMOOTHING ---
        self.log("🌊 [Smart Reframe] Applying SciPy Steadicam motion smoothing...")
        if progress_callback:
            progress_callback(0.75, "Applying Steadicam camera smoothing...")

        smoothed_x = self._smooth_trajectory_segments(
            stabilized_x,
            cut_indices=scene_cut_indices,
            smoothness=smoothness,
            max_bound=max_crop_x
        )

        # --- G. GENERATE TIMELINE KEYFRAMES & FULL TRAJECTORY ---
        full_trajectory = []
        keyframes = []
        last_kf_x = -9999
        last_kf_time = -99.0

        for i, (f_idx, t, cx, dec) in enumerate(zip(frame_indices, timestamps, smoothed_x, decisions)):
            full_trajectory.append({
                "frame": f_idx,
                "time": round(t, 3),
                "crop_x": int(cx),
                "decision": dec
            })

            # Keyframe emitted when camera pans > 15px, at scene cuts, or every 2.5 seconds
            time_gap = t - last_kf_time
            is_cut = (i in scene_cut_indices)
            if abs(cx - last_kf_x) >= 15 or is_cut or time_gap >= 2.5 or i == 0 or i == len(smoothed_x) - 1:
                keyframes.append({
                    "time": round(t, 3),
                    "crop_x": int(cx),
                    "crop_w": crop_w,
                    "crop_h": crop_h,
                    "decision": dec
                })
                last_kf_x = cx
                last_kf_time = t

        if progress_callback:
            progress_callback(1.0, "Smart Auto Reframe Complete!")

        total_analyzed = max(1, len(stabilized_x))
        self.log(
            f"✅ [Smart Reframe] Complete: {len(keyframes)} Keyframes generated | "
            f"Group Frames: {decision_counts['group']} | Single: {decision_counts['single']} | "
            f"Camera Locked Steady: {decision_counts['steady_locked']} ({int(decision_counts['steady_locked']/total_analyzed*100)}%)"
        )

        return {
            "video_w": vw,
            "video_h": vh,
            "crop_w": crop_w,
            "crop_h": crop_h,
            "fps": fps,
            "duration": dur,
            "keyframes": keyframes,
            "trajectory": full_trajectory,
            "stats": {
                "decision_counts": decision_counts,
                "scene_cuts": len(scene_cut_indices),
                "locked_steady_pct": round(decision_counts["steady_locked"] / total_analyzed * 100, 1)
            }
        }

    # -------------------------------------------------------------
    # 3. SCIPY CINEMATIC MOTION SMOOTHING (PER-SEGMENT ACROSS CUTS)
    # -------------------------------------------------------------
    def _smooth_trajectory_segments(
        self,
        raw_x: List[int],
        cut_indices: set,
        smoothness: float = 0.85,
        max_bound: int = 1920
    ) -> List[int]:
        """
        Smooths trajectory per continuous shot segment so that smoothing does NOT
        blur or smear across scene cuts. Uses Savitzky-Golay + Gaussian ease-in/out.
        """
        arr = np.array(raw_x, dtype=np.float64)
        n = len(arr)
        if n < 3:
            return [int(np.clip(x, 0, max_bound)) for x in arr]

        # Break into continuous segments between cuts
        segments = []
        start_idx = 0
        for i in range(1, n):
            if i in cut_indices:
                segments.append((start_idx, i))
                start_idx = i
        segments.append((start_idx, n))

        result = arr.copy()

        for seg_start, seg_end in segments:
            seg_len = seg_end - seg_start
            if seg_len < 3:
                continue

            sub_arr = arr[seg_start:seg_end].copy()

            # Window length proportional to smoothness
            window_size = int(max(5, min(seg_len - 1, 15 + int(smoothness * 35))))
            if window_size % 2 == 0:
                window_size += 1
            if window_size >= seg_len:
                window_size = seg_len if seg_len % 2 != 0 else seg_len - 1
                if window_size < 3:
                    window_size = 3

            if SCIPY_AVAILABLE and seg_len >= 5:
                try:
                    poly_order = 2 if window_size > 2 else 1
                    smoothed = savgol_filter(sub_arr, window_length=window_size, polyorder=poly_order)
                    sigma = max(0.8, smoothness * 5.0)
                    smoothed = gaussian_filter1d(smoothed, sigma=sigma)
                except Exception:
                    smoothed = self._moving_average(sub_arr, window_size)
            else:
                smoothed = self._moving_average(sub_arr, window_size)

            result[seg_start:seg_end] = smoothed

        clamped = [int(np.clip(round(x), 0, max_bound)) for x in result]
        return clamped

    def _moving_average(self, arr: np.ndarray, window: int) -> np.ndarray:
        """Lightweight moving average fallback"""
        res = np.copy(arr)
        half = window // 2
        for i in range(len(arr)):
            lo = max(0, i - half)
            hi = min(len(arr), i + half + 1)
            res[i] = np.mean(arr[lo:hi])
        return res

    # -------------------------------------------------------------
    # 4. HIGH-PERFORMANCE 9:16 TIKTOK EXPORT RENDERER
    # -------------------------------------------------------------
    def render_reframe_video(
        self,
        video_path: str,
        trajectory: List[Dict[str, Any]],
        output_path: str,
        target_w: int = 1080,
        target_h: int = 1920,
        use_gpu: bool = True,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> bool:
        """
        Renders the vertical 9:16 re-framed video with moving camera crop directly into output_path.
        Uses hardware-accelerated FFmpeg pipe with OpenCV reading for ultra-fast rendering.
        """
        self._stop_requested = False
        if not os.path.exists(video_path):
            return False

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return False

        vw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1920)
        vh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1080)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 1)

        crop_h = vh
        crop_w = int(vh * (9.0 / 16.0))
        max_crop_x = max(0, vw - crop_w)

        # Map trajectory by frame
        traj_map = {item["frame"]: item["crop_x"] for item in trajectory}

        # Build FFmpeg pipe command
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        encoder = "h264_nvenc" if use_gpu else "libx264"
        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{target_w}x{target_h}",
            "-pix_fmt", "bgr24",
            "-r", str(fps),
            "-i", "-",  # Video input from pipe
            "-i", video_path,  # Audio source from original video
            "-map", "0:v:0",
            "-map", "1:a:0?",
            "-c:v", encoder,
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            output_path
        ]

        # Test if GPU encoder is supported, fallback to libx264 if not
        try:
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        except Exception:
            cmd[cmd.index(encoder)] = "libx264"
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        curr_crop_x = max_crop_x // 2
        f_idx = 0

        self.log(f"🚀 [Smart Reframe] Rendering 9:16 TikTok Vertical Video ({target_w}x{target_h})...")

        try:
            while cap.isOpened() and not self._stop_requested:
                ret, frame = cap.read()
                if not ret:
                    break

                if f_idx in traj_map:
                    curr_crop_x = traj_map[f_idx]

                cx = max(0, min(max_crop_x, curr_crop_x))
                cropped = frame[0:crop_h, cx:cx + crop_w]

                # Resize cropped slice to target 1080x1920
                resized = cv2.resize(cropped, (target_w, target_h), interpolation=cv2.INTER_LINEAR)

                try:
                    p.stdin.write(resized.tobytes())
                except (IOError, BrokenPipeError):
                    break

                if progress_callback and total_frames > 0 and (f_idx % 30 == 0):
                    pct = min(1.0, f_idx / total_frames)
                    progress_callback(pct, f"Exporting 9:16 Video: {int(pct*100)}%")

                f_idx += 1

            p.stdin.close()
            p.wait()
            cap.release()

            if self._stop_requested:
                if os.path.exists(output_path):
                    os.remove(output_path)
                return False

            self.log(f"🎉 [Smart Reframe] TikTok 9:16 Vertical Video successfully created: {output_path}")
            return os.path.exists(output_path) and os.path.getsize(output_path) > 1000

        except Exception as e:
            self.log(f"❌ [Smart Reframe] Render error: {e}")
            try:
                p.kill()
            except Exception:
                pass
            cap.release()
            return False
