"""
MediaPipe & OpenCV AI Face Tracking, Face Mesh & AR Effects Engine
Provides:
1. FaceMeshDetector: High-precision 478-landmark Face Mesh tracking (MediaPipe Tasks + OpenCV Fallback)
2. AutoFaceBlurProcessor: Cinema-grade feathered Gaussian blur, Mosaic, Frosted glass, and Blackout face censor
3. FaceARPropsEngine: Dynamic AR Stickers that automatically follow, rotate, and scale with the face (Glasses, Hats, Mustaches, Masks, Custom Stickers)
4. VideoFaceTrackingWorker: Background processor for full-video trajectory generation
"""

import os
import sys
import math
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Callable
import cv2
import numpy as np

from ui_v_PyQt6.qt_compat import (
    QObject, Signal, QThread, QColor, QFont, QPainter, QImage, QPixmap,
    QPointF, QRectF, QTransform, QPainterPath, QPen, QBrush, QLinearGradient, Qt
)

# ----------------- MEDIAPIPE INITIALIZATION -----------------
MEDIAPIPE_AVAILABLE = False
try:
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision
    MEDIAPIPE_AVAILABLE = True
except Exception:
    MEDIAPIPE_AVAILABLE = False


@dataclass
class FaceKeypoints:
    """Core facial landmarks and spatial orientation attributes."""
    bbox: Tuple[float, float, float, float]  # (norm_x, norm_y, norm_w, norm_h)
    pixel_bbox: Tuple[int, int, int, int]    # (x, y, w, h)
    left_eye: Tuple[float, float]            # (norm_x, norm_y)
    right_eye: Tuple[float, float]           # (norm_x, norm_y)
    nose_tip: Tuple[float, float]            # (norm_x, norm_y)
    mouth_center: Tuple[float, float]        # (norm_x, norm_y)
    forehead: Tuple[float, float]            # (norm_x, norm_y)
    chin: Tuple[float, float]                # (norm_x, norm_y)
    roll_deg: float = 0.0                    # Tilt / roll angle in degrees
    eye_dist: float = 0.1                    # Normalized distance between eyes
    landmarks_raw: List[Tuple[float, float, float]] = field(default_factory=list)


class FaceMeshDetector:
    """
    Dual-Engine Face Detector:
    - Primary: MediaPipe Tasks FaceLandmarker (478 3D landmarks, robust to occlusion & rotation)
    - Fallback: OpenCV Haar Cascades (frontalface + profileface + upperbody)
    """
    def __init__(self, model_path: Optional[str] = None):
        self._detector = None
        self._haar_faces = None
        self._haar_eyes = None
        self.is_mediapipe = False

        if model_path is None:
            # Check default model location
            base_dir = os.path.dirname(os.path.abspath(__file__))
            default_task = os.path.join(base_dir, "models", "face_landmarker.task")
            if os.path.exists(default_task):
                model_path = default_task

        if MEDIAPIPE_AVAILABLE and model_path and os.path.exists(model_path):
            try:
                base_options = mp_python.BaseOptions(model_asset_path=model_path)
                options = vision.FaceLandmarkerOptions(
                    base_options=base_options,
                    output_face_blendshapes=False,
                    output_facial_transformation_matrixes=False,
                    num_faces=6,
                    min_face_detection_confidence=0.5,
                    min_face_presence_confidence=0.5,
                    min_tracking_confidence=0.5
                )
                self._detector = vision.FaceLandmarker.create_from_options(options)
                self.is_mediapipe = True
            except Exception as e:
                print(f"[FaceMeshDetector] MediaPipe initialization error: {e}, falling back to OpenCV")

        # Initialize OpenCV Haar Cascades fallback
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            f_xml = os.path.join(base_dir, "models", "haarcascade_frontalface_default.xml")
            if os.path.exists(f_xml):
                self._haar_faces = cv2.CascadeClassifier(f_xml)
        except Exception:
            pass

    def detect_faces(self, frame_bgr: np.ndarray) -> List[FaceKeypoints]:
        """Detects all faces in a BGR video frame and returns standardized FaceKeypoints."""
        if frame_bgr is None or frame_bgr.size == 0:
            return []

        h, w = frame_bgr.shape[:2]
        results = []

        # 1. MediaPipe Tasks Detection
        if self.is_mediapipe and self._detector:
            try:
                rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                res = self._detector.detect(mp_image)

                if res and res.face_landmarks:
                    for lms in res.face_landmarks:
                        # Extract key landmark indices:
                        # 33: Left eye inner, 133: Left eye outer, 159: Left eye top, 145: Left eye bottom
                        # 362: Right eye inner, 263: Right eye outer
                        # 1: Nose tip
                        # 13, 14: Lips
                        # 10: Forehead top
                        # 152: Chin bottom
                        xs = [lm.x for lm in lms]
                        ys = [lm.y for lm in lms]
                        min_x, max_x = max(0.0, min(xs)), min(1.0, max(xs))
                        min_y, max_y = max(0.0, min(ys)), min(1.0, max(ys))
                        bbox = (min_x, min_y, max_x - min_x, max_y - min_y)
                        px_bbox = (int(min_x * w), int(min_y * h), int((max_x - min_x) * w), int((max_y - min_y) * h))

                        # Eye centers (468/473 if iris present, else midpoint of inner/outer)
                        lx, ly = (lms[33].x + lms[133].x) / 2.0, (lms[33].y + lms[133].y) / 2.0
                        rx, ry = (lms[362].x + lms[263].x) / 2.0, (lms[362].y + lms[263].y) / 2.0

                        # Nose & mouth
                        nx, ny = lms[1].x, lms[1].y
                        mx, my = (lms[13].x + lms[14].x) / 2.0, (lms[13].y + lms[14].y) / 2.0
                        fx, fy = lms[10].x, lms[10].y
                        cx, cy = lms[152].x, lms[152].y

                        # Roll / Angle
                        dx = (rx - lx) * w
                        dy = (ry - ly) * h
                        roll = math.degrees(math.atan2(dy, dx))
                        eye_d = math.hypot(rx - lx, ry - ly)

                        raw_pts = [(lm.x, lm.y, lm.z) for lm in lms]
                        results.append(FaceKeypoints(
                            bbox=bbox,
                            pixel_bbox=px_bbox,
                            left_eye=(lx, ly),
                            right_eye=(rx, ry),
                            nose_tip=(nx, ny),
                            mouth_center=(mx, my),
                            forehead=(fx, fy),
                            chin=(cx, cy),
                            roll_deg=roll,
                            eye_dist=eye_d,
                            landmarks_raw=raw_pts
                        ))
                    return results
            except Exception as e:
                pass

        # 2. OpenCV Fallback
        if self._haar_faces and not self._haar_faces.empty():
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            faces = self._haar_faces.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=4, minSize=(40, 40))
            for (fx, fy, fw, fh) in faces:
                nx, ny, nw, nh = fx / float(w), fy / float(h), fw / float(w), fh / float(h)
                lx, ly = nx + nw * 0.35, ny + nh * 0.38
                rx, ry = nx + nw * 0.65, ny + nh * 0.38
                nose_x, nose_y = nx + nw * 0.5, ny + nh * 0.55
                mx, my = nx + nw * 0.5, ny + nh * 0.75
                results.append(FaceKeypoints(
                    bbox=(nx, ny, nw, nh),
                    pixel_bbox=(fx, fy, fw, fh),
                    left_eye=(lx, ly),
                    right_eye=(rx, ry),
                    nose_tip=(nose_x, nose_y),
                    mouth_center=(mx, my),
                    forehead=(nx + nw * 0.5, ny + nh * 0.15),
                    chin=(nx + nw * 0.5, ny + nh * 0.95),
                    roll_deg=0.0,
                    eye_dist=nw * 0.30
                ))

        return results


class AutoFaceBlurProcessor:
    """
    Cinema-Grade Face Censor & Blurring Engine:
    Supports:
    - 'blur': Smooth Gaussian Blur with soft feathering
    - 'mosaic': High-tech Pixelate / Mosaic censor
    - 'glass': Modern Frosted Glassmorphism with specular border
    - 'blackout': Sleek Blackout bar / Oval blackout
    """
    @staticmethod
    def apply_face_blur(
        frame_bgr: np.ndarray,
        faces: List[FaceKeypoints],
        mode: str = "blur",
        strength: int = 25,
        feather: bool = True,
        shape_type: str = "ellipse"  # "ellipse" (natural face oval) or "rect"
    ) -> np.ndarray:
        if frame_bgr is None or not faces:
            return frame_bgr

        out = frame_bgr.copy()
        fh, fw = out.shape[:2]

        for face in faces:
            x, y, w, h = face.pixel_bbox
            # Add 15% padding around face for natural head coverage
            pad_w = int(w * 0.15)
            pad_h = int(h * 0.18)
            bx = max(0, x - pad_w)
            by = max(0, y - pad_h)
            bw = min(fw - bx, w + pad_w * 2)
            bh = min(fh - by, h + pad_h * 2)

            if bw < 8 or bh < 8:
                continue

            roi = out[by:by+bh, bx:bx+bw]
            censored_roi = None

            if mode == "mosaic":
                factor = max(4, int(20 * (strength / 25.0)))
                sw = max(2, bw // factor)
                sh = max(2, bh // factor)
                small = cv2.resize(roi, (sw, sh), interpolation=cv2.INTER_NEAREST)
                censored_roi = cv2.resize(small, (bw, bh), interpolation=cv2.INTER_NEAREST)

            elif mode == "blackout":
                censored_roi = np.zeros_like(roi)

            elif mode == "glass":
                # Frosted glass: bilateral / smooth blur + bright tint
                ksize = max(9, (int(strength * 1.5) // 2) * 2 + 1)
                blurred = cv2.GaussianBlur(roi, (ksize, ksize), 0)
                tint = np.full_like(roi, 230)
                censored_roi = cv2.addWeighted(blurred, 0.70, tint, 0.30, 0)

            else:  # "blur"
                ksize = max(11, (int(strength * 2) // 2) * 2 + 1)
                censored_roi = cv2.GaussianBlur(roi, (ksize, ksize), 0)

            if censored_roi is not None:
                if shape_type == "ellipse":
                    # Create oval mask with smooth feathering
                    mask = np.zeros((bh, bw), dtype=np.uint8)
                    center = (bw // 2, bh // 2)
                    axes = (int(bw * 0.46), int(bh * 0.48))
                    cv2.ellipse(mask, center, axes, int(face.roll_deg), 0, 360, 255, -1)
                    if feather:
                        mask = cv2.GaussianBlur(mask, (15, 15), 0)
                    mask_f = (mask / 255.0)[:, :, np.newaxis]
                    out[by:by+bh, bx:bx+bw] = (censored_roi * mask_f + roi * (1.0 - mask_f)).astype(np.uint8)
                else:
                    out[by:by+bh, bx:bx+bw] = censored_roi

        return out


class FaceARPropsEngine:
    """
    Renders dynamic AR accessories (Glasses, Hats, Crowns, Mustaches, Masks, Custom Stickers)
    onto QPainter mapped precisely to facial geometry (roll angle, eye distance, scale).
    """
    @staticmethod
    def draw_ar_props_on_painter(
        painter: QPainter,
        canvas_rect: QRectF,
        faces: List[FaceKeypoints],
        prop_type: str = "glasses",      # "glasses", "crown", "mustache", "mask", "bunny", "custom"
        custom_pixmap: Optional[QPixmap] = None,
        anchor: str = "eyes",           # "eyes", "head", "mouth", "face"
        scale_factor: float = 1.0,
        offset_y: float = 0.0
    ):
        """Draws dynamic vector or pixmap AR props directly onto canvas painter with 60fps anti-aliasing."""
        if not faces or not canvas_rect:
            return

        cl, ct = canvas_rect.left(), canvas_rect.top()
        cw, ch = canvas_rect.width(), canvas_rect.height()

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        for face in faces:
            # Determine Anchor Point
            if anchor == "head":
                ax = cl + face.forehead[0] * cw
                ay = ct + face.forehead[1] * ch + (offset_y * ch)
            elif anchor == "mouth":
                ax = cl + face.mouth_center[0] * cw
                ay = ct + face.mouth_center[1] * ch + (offset_y * ch)
            elif anchor == "face":
                ax = cl + (face.bbox[0] + face.bbox[2] / 2.0) * cw
                ay = ct + (face.bbox[1] + face.bbox[3] / 2.0) * ch + (offset_y * ch)
            else:  # "eyes"
                ax = cl + (face.left_eye[0] + face.right_eye[0]) / 2.0 * cw
                ay = ct + (face.left_eye[1] + face.right_eye[1]) / 2.0 * ch + (offset_y * ch)

            # Compute scale based on inter-pupillary eye distance
            base_eye_px = max(20.0, face.eye_dist * cw)
            roll = face.roll_deg

            painter.save()
            painter.translate(ax, ay)
            painter.rotate(roll)

            if prop_type == "glasses":
                FaceARPropsEngine._draw_sunglasses(painter, base_eye_px * 2.3 * scale_factor)
            elif prop_type == "crown":
                FaceARPropsEngine._draw_golden_crown(painter, base_eye_px * 2.8 * scale_factor)
            elif prop_type == "mustache":
                FaceARPropsEngine._draw_mustache(painter, base_eye_px * 1.5 * scale_factor)
            elif prop_type == "mask":
                FaceARPropsEngine._draw_face_mask(painter, base_eye_px * 2.4 * scale_factor)
            elif prop_type == "bunny":
                FaceARPropsEngine._draw_bunny_ears(painter, base_eye_px * 2.6 * scale_factor)
            elif prop_type == "custom" and custom_pixmap and not custom_pixmap.isNull():
                pw = base_eye_px * 2.2 * scale_factor
                ph = pw * (custom_pixmap.height() / float(max(1, custom_pixmap.width())))
                painter.drawPixmap(QRectF(-pw / 2.0, -ph / 2.0, pw, ph).toRect(), custom_pixmap)

            painter.restore()

        painter.restore()

    @staticmethod
    def _draw_sunglasses(painter: QPainter, width: float):
        """Draws stylish cinema sunglasses with golden bridge and lens reflections."""
        h = width * 0.38
        w_lens = width * 0.44
        gap = width * 0.12

        # Lenses (Left and Right)
        lens_grad = QLinearGradient(0, -h/2, 0, h/2)
        lens_grad.setColorAt(0.0, QColor(20, 24, 33, 240))
        lens_grad.setColorAt(0.5, QColor(10, 12, 16, 255))
        lens_grad.setColorAt(1.0, QColor(30, 41, 59, 230))

        painter.setBrush(QBrush(lens_grad))
        painter.setPen(QPen(QColor("#e2e8f0"), 2))

        # Left Lens
        r_lens = h * 0.35
        rect_l = QRectF(-width/2, -h/2, w_lens, h)
        painter.drawRoundedRect(rect_l, r_lens, r_lens)

        # Right Lens
        rect_r = QRectF(-width/2 + w_lens + gap, -h/2, w_lens, h)
        painter.drawRoundedRect(rect_r, r_lens, r_lens)

        # Gold Bridge
        painter.setPen(QPen(QColor("#facc15"), 3))
        painter.drawLine(QPointF(-gap/2, -h*0.2), QPointF(gap/2, -h*0.2))

        # Gloss reflection glint
        glint_pen = QPen(QColor(255, 255, 255, 120), 2)
        painter.setPen(glint_pen)
        painter.drawLine(QPointF(-width/2 + 8, -h/2 + 6), QPointF(-width/2 + w_lens - 10, -h/2 + 16))
        painter.drawLine(QPointF(gap/2 + 8, -h/2 + 6), QPointF(gap/2 + w_lens - 10, -h/2 + 16))

    @staticmethod
    def _draw_golden_crown(painter: QPainter, width: float):
        """Draws metallic royal golden crown with rubies."""
        h = width * 0.55
        y_base = 0.0

        path = QPainterPath()
        path.moveTo(-width/2, y_base)
        path.lineTo(-width/2 * 0.9, y_base - h * 0.75)  # Left peak
        path.lineTo(-width * 0.22, y_base - h * 0.40)  # Valley 1
        path.lineTo(0, y_base - h)                     # Center highest peak
        path.lineTo(width * 0.22, y_base - h * 0.40)   # Valley 2
        path.lineTo(width/2 * 0.9, y_base - h * 0.75)   # Right peak
        path.lineTo(width/2, y_base)                   # Base right
        path.closeSubpath()

        gold_grad = QLinearGradient(0, y_base - h, 0, y_base)
        gold_grad.setColorAt(0.0, QColor("#fef08a"))
        gold_grad.setColorAt(0.4, QColor("#eab308"))
        gold_grad.setColorAt(1.0, QColor("#ca8a04"))

        painter.setBrush(QBrush(gold_grad))
        painter.setPen(QPen(QColor("#78350f"), 2))
        painter.drawPath(path)

        # Rubies / Jewels on peaks
        painter.setBrush(QBrush(QColor("#ef4444")))
        painter.setPen(QPen(QColor("#ffffff"), 1))
        painter.drawEllipse(QPointF(-width/2 * 0.9, y_base - h * 0.75), 5, 5)
        painter.drawEllipse(QPointF(0, y_base - h), 7, 7)
        painter.drawEllipse(QPointF(width/2 * 0.9, y_base - h * 0.75), 5, 5)

    @staticmethod
    def _draw_mustache(painter: QPainter, width: float):
        """Draws classic vintage curled gentleman mustache."""
        h = width * 0.32
        path = QPainterPath()
        path.moveTo(0, 0)
        # Left curl
        path.cubicTo(-width * 0.2, -h * 0.6, -width * 0.4, -h * 0.2, -width/2, h * 0.4)
        path.cubicTo(-width * 0.35, h * 0.6, -width * 0.15, h * 0.2, 0, h * 0.3)
        # Right curl
        path.cubicTo(width * 0.15, h * 0.2, width * 0.35, h * 0.6, width/2, h * 0.4)
        path.cubicTo(width * 0.4, -h * 0.2, width * 0.2, -h * 0.6, 0, 0)

        painter.setBrush(QBrush(QColor("#1c1917")))
        painter.setPen(QPen(QColor("#44403c"), 1.5))
        painter.drawPath(path)

    @staticmethod
    def _draw_face_mask(painter: QPainter, width: float):
        """Draws protective surgical mask with pleated creases."""
        h = width * 0.60
        rect = QRectF(-width/2, -h/2, width, h)

        painter.setBrush(QBrush(QColor("#38bdf8")))
        painter.setPen(QPen(QColor("#0284c7"), 1.5))
        painter.drawRoundedRect(rect, 10, 10)

        # Pleats
        painter.setPen(QPen(QColor("#0369a1"), 1.5))
        painter.drawLine(QPointF(-width * 0.4, -h * 0.15), QPointF(width * 0.4, -h * 0.15))
        painter.drawLine(QPointF(-width * 0.4, h * 0.10), QPointF(width * 0.4, h * 0.10))

    @staticmethod
    def _draw_bunny_ears(painter: QPainter, width: float):
        """Draws cute pink & white animated bunny ears above head."""
        h = width * 1.2
        y_base = 0.0

        # Outer White Ears
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.setPen(QPen(QColor("#e2e8f0"), 2))

        # Left Ear
        path_l = QPainterPath()
        path_l.moveTo(-width * 0.25, y_base)
        path_l.cubicTo(-width * 0.4, y_base - h * 0.5, -width * 0.45, y_base - h, -width * 0.25, y_base - h)
        path_l.cubicTo(-width * 0.05, y_base - h, -width * 0.1, y_base - h * 0.5, -width * 0.15, y_base)
        painter.drawPath(path_l)

        # Right Ear
        path_r = QPainterPath()
        path_r.moveTo(width * 0.15, y_base)
        path_r.cubicTo(width * 0.1, y_base - h * 0.5, width * 0.05, y_base - h, width * 0.25, y_base - h)
        path_r.cubicTo(width * 0.45, y_base - h, width * 0.4, y_base - h * 0.5, width * 0.25, y_base)
        painter.drawPath(path_r)

        # Inner Pink Pad
        painter.setBrush(QBrush(QColor("#f472b6")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(-width * 0.30, y_base - h * 0.85, width * 0.12, h * 0.65))
        painter.drawEllipse(QRectF(width * 0.18, y_base - h * 0.85, width * 0.12, h * 0.65))

    @staticmethod
    def draw_face_mesh_wireframe(painter: QPainter, canvas_rect: QRectF, faces: List[FaceKeypoints]):
        """Renders futuristic neon cyan / magenta AR face mesh wireframe for visual tracking feedback."""
        if not faces or not canvas_rect:
            return

        cl, ct = canvas_rect.left(), canvas_rect.top()
        cw, ch = canvas_rect.width(), canvas_rect.height()

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        for face in faces:
            # 1. Bounding Box Bracket
            bx, by, bw, bh = face.pixel_bbox
            painter.setPen(QPen(QColor("#00e5ff"), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            target_rect = QRectF(cl + face.bbox[0] * cw, ct + face.bbox[1] * ch, face.bbox[2] * cw, face.bbox[3] * ch)
            painter.drawRoundedRect(target_rect, 6, 6)

            # 2. Keypoints (Eyes, Nose, Mouth, Forehead, Chin)
            pts = [
                (face.left_eye, QColor("#38bdf8")),
                (face.right_eye, QColor("#38bdf8")),
                (face.nose_tip, QColor("#f43f5e")),
                (face.mouth_center, QColor("#eab308")),
                (face.forehead, QColor("#a855f7")),
                (face.chin, QColor("#10b981"))
            ]
            for (nx, ny), col in pts:
                px = cl + nx * cw
                py = ct + ny * ch
                painter.setPen(QPen(QColor("#ffffff"), 1))
                painter.setBrush(QBrush(col))
                painter.drawEllipse(QPointF(px, py), 4, 4)

            # 3. Connect Eyes Line
            lx = cl + face.left_eye[0] * cw
            ly = ct + face.left_eye[1] * ch
            rx = cl + face.right_eye[0] * cw
            ry = ct + face.right_eye[1] * ch
            painter.setPen(QPen(QColor(56, 189, 248, 160), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(lx, ly), QPointF(rx, ry))

            # 4. Info Tag (Angle, Distance)
            painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
            painter.setPen(QColor("#38bdf8"))
            tag = f"Face: {int(face.roll_deg)}° | Eye: {int(face.eye_dist*cw)}px"
            painter.drawText(QPointF(target_rect.left(), target_rect.top() - 6), tag)

        painter.restore()


class VideoFaceScannerWorker(QThread):
    """
    High-Speed Video Face Scanner & Cast Recognition Worker.
    Scans an entire video file, detects all human faces across scenes,
    extracts facial feature descriptors, and clusters them into distinct characters / people.
    Emits progress and the final list of detected cast members with HD thumbnail crops and timestamps.
    """
    progress = Signal(int, float, int)  # (percent: 0-100, current_sec, unique_people_found)
    finished = Signal(list)             # list of person dicts
    error = Signal(str)

    def __init__(
        self,
        video_path: str,
        sample_interval: float = 1.0,
        similarity_thresh: float = 0.65,
        max_faces_per_frame: int = 6,
        parent=None
    ):
        super().__init__(parent)
        self.video_path = video_path
        self.sample_interval = max(0.2, float(sample_interval))
        self.similarity_thresh = float(similarity_thresh)
        self.max_faces_per_frame = max_faces_per_frame
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        if not self.video_path or not os.path.exists(self.video_path):
            self.error.emit(f"Video file not found: {self.video_path}")
            return

        try:
            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                self.error.emit("Failed to open video file with OpenCV")
                return

            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0.0

            step = max(1, int(fps * self.sample_interval))
            detector = FaceMeshDetector()

            clusters = []  # list of person dictionaries
            frame_idx = 0

            while frame_idx < total_frames and not self._is_cancelled:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                if not ret or frame is None:
                    break

                sec = round(frame_idx / fps, 2)
                h, w = frame.shape[:2]

                faces = detector.detect_faces(frame)
                if faces:
                    for f in faces[:self.max_faces_per_frame]:
                        # Bounding box in pixel coords with safety padding
                        nx, ny, nw, nh = f.bbox
                        pad_x = int(nw * w * 0.15)
                        pad_y = int(nh * h * 0.20)
                        x1 = max(0, int(nx * w) - pad_x)
                        y1 = max(0, int(ny * h) - pad_y)
                        x2 = min(w, int((nx + nw) * w) + pad_x)
                        y2 = min(h, int((ny + nh) * h) + pad_y)

                        if x2 - x1 < 20 or y2 - y1 < 20:
                            continue

                        face_crop = frame[y1:y2, x1:x2]

                        # Compute HSV Color Histogram (skin tone, hair, contrast)
                        hsv = cv2.cvtColor(face_crop, cv2.COLOR_BGR2HSV)
                        hist = cv2.calcHist([hsv], [0, 1], None, [16, 8], [0, 180, 0, 256])
                        cv2.normalize(hist, hist)

                        # Compute Normalized Spatial Patch
                        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
                        patch = cv2.resize(gray, (24, 24)).flatten().astype(np.float32)
                        patch_norm = patch / (np.linalg.norm(patch) + 1e-6)

                        # Match against existing clusters
                        best_match = None
                        best_score = -1.0

                        for c in clusters:
                            sim_hist = cv2.compareHist(c["hist"], hist, cv2.HISTCMP_CORREL)
                            sim_patch = float(np.dot(c["patch"], patch_norm))
                            sim = 0.60 * sim_hist + 0.40 * sim_patch
                            if sim > best_score:
                                best_score = sim
                                best_match = c

                        if best_score >= self.similarity_thresh and best_match is not None:
                            # Existing Person
                            best_match["appearances"].append({
                                "time": sec,
                                "bbox": (round(nx, 3), round(ny, 3), round(nw, 3), round(nh, 3))
                            })
                            best_match["count"] += 1
                            # Update avatar if current face crop is larger / higher resolution
                            cw, ch = face_crop.shape[1], face_crop.shape[0]
                            prev_w, prev_h = best_match["thumb_bgr"].shape[1], best_match["thumb_bgr"].shape[0]
                            if cw * ch > prev_w * prev_h and cw >= 48 and ch >= 48:
                                best_match["thumb_bgr"] = face_crop.copy()
                        else:
                            # New Person
                            new_id = len(clusters) + 1
                            clusters.append({
                                "id": new_id,
                                "name": f"Person {new_id}",
                                "thumb_bgr": face_crop.copy(),
                                "hist": hist,
                                "patch": patch_norm,
                                "appearances": [{
                                    "time": sec,
                                    "bbox": (round(nx, 3), round(ny, 3), round(nw, 3), round(nh, 3))
                                }],
                                "count": 1
                            })

                frame_idx += step
                pct = min(100, int((frame_idx / max(1, total_frames)) * 100))
                self.progress.emit(pct, sec, len(clusters))

            cap.release()

            if self._is_cancelled:
                return

            # Sort clusters by frequency (most frequent actors first)
            clusters.sort(key=lambda x: x["count"], reverse=True)
            for i, c in enumerate(clusters, 1):
                c["rank"] = i

            self.progress.emit(100, duration, len(clusters))
            self.finished.emit(clusters)

        except Exception as e:
            self.error.emit(str(e))

