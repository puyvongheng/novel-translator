"""
Canvas Item Model & Rendering Engine for Canva-Like Interactive Video Preview
Supports Image overlays, Stickers, Typography / Text, and Vector Shapes
with rotation, proportional resizing, normalized coordinates, and real-time Sharpness / Blur effects.
"""

import os
import math
import uuid
import cv2
import numpy as np
from typing import Tuple, Optional, List, Dict, Any
from ui_v_PyQt6.qt_compat import (
    Qt, QColor, QFont, QPen, QBrush, QPointF, QRectF, QTransform,
    QPainter, QImage, QPixmap, QPainterPath, QImageReader, QLinearGradient
)


class CanvasItem:
    """
    Represents an interactive visual object on top of the video canvas.
    Coordinates are normalized (0.0 to 1.0) relative to the master canvas resolution,
    ensuring 100% resolution independence and zero drift when zooming or exporting.
    """
    HANDLE_SIZE = 10
    ROTATE_OFFSET = 32

    def __init__(
        self,
        item_type: str = "image",  # "image", "text", "shape", "sticker"
        x: float = 0.5,           # normalized center X (0.0 - 1.0)
        y: float = 0.5,           # normalized center Y (0.0 - 1.0)
        w: float = 0.25,          # normalized width
        h: float = 0.25,          # normalized height
        rotation: float = 0.0,    # degrees
        opacity: float = 1.0,
        z_index: int = 0,
        name: str = "Object",
        text: str = None,
        image_path: str = None,
        shape_type: str = "rect",
        **kwargs
    ):
        self.id = str(uuid.uuid4())[:8]
        self.item_type = item_type
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.rotation = rotation
        self.opacity = opacity
        self.z_index = z_index
        self.name = name

        self.is_locked = False
        self.is_visible = True

        # Timeline Start & End Timestamps (in seconds)
        # start_time: when object appears; end_time: when object disappears (0.0 = spans entire video)
        self.start_time = float(kwargs.get("start_time", 0.0))
        self.end_time = float(kwargs.get("end_time", 0.0))

        # Dynamic Motion Path & Keyframe Animation Engine
        self.motion_path = kwargs.get("motion_path", None)

        # Real-time Image/Video Processing Effects
        self.sharpness = 0  # 0 to 100
        self.blur = 0       # 0 to 100

        # Video / PiP Overlay Specific
        self.video_path = kwargs.get("video_path", None)

        # Image / Sticker Specific
        self.image_path = image_path
        self._raw_image = None       # QImage
        self._processed_pixmap = None  # QPixmap with sharpness/blur applied
        if image_path:
            self.load_image(image_path)
        elif self.video_path:
            self.load_video(self.video_path)

        # Text Specific
        self.text = text if text is not None else "Double click to edit"
        self.font_family = kwargs.get("font_family", "Kantumruy Pro")
        self.font_size = kwargs.get("font_size", 28)
        self.font_color = kwargs.get("font_color", QColor("#ffffff"))
        self.bg_color = kwargs.get("bg_color", QColor(0, 0, 0, 0))
        self.is_bold = kwargs.get("is_bold", True)
        self.is_italic = kwargs.get("is_italic", False)
        self.animation = kwargs.get("animation", "karaoke" if item_type == "subtitle" else "none")

        # Vector Shape Specific (Photoshop-grade Shape Layer)
        self.shape_type = kwargs.get("shape_type", shape_type or "rect")
        self.fill_color = kwargs.get("fill_color", QColor("#000000"))
        self.border_color = kwargs.get("border_color", QColor("#e11d48"))
        self.border_width = int(kwargs.get("border_width", 0))
        self.stroke_style = kwargs.get("stroke_style", "none" if self.border_width == 0 else "solid")
        self.corner_radius = float(kwargs.get("corner_radius", 0.0))
        self.radius_tl = float(kwargs.get("radius_tl", self.corner_radius))
        self.radius_tr = float(kwargs.get("radius_tr", self.corner_radius))
        self.radius_bl = float(kwargs.get("radius_bl", self.corner_radius))
        self.radius_br = float(kwargs.get("radius_br", self.corner_radius))

    def is_active_at(self, t: float, total_duration: float = 0.0) -> bool:
        """Checks if this overlay object is active at given timeline playback time (t)."""
        st = float(self.start_time)
        et = float(self.end_time)
        if st == 0.0 and et == 0.0:
            return True  # Spans entire video
        if et <= st:
            et = st + 5.0
        return st <= t <= et

    def get_animated_state(self, current_time: float) -> Tuple[float, float, float, float, float, float]:
        """
        Returns (x, y, w, h, rotation, opacity) at given timestamp.
        Dynamically applies MotionPathAnimation if present.
        """
        if getattr(self, "motion_path", None) and current_time is not None:
            elapsed = max(0.0, current_time - float(self.start_time))
            anim_x, anim_y, sc, rot, op = self.motion_path.evaluate(elapsed)
            w = self.w * sc
            h = self.h * sc
            rotation = self.rotation + rot
            opacity = max(0.0, min(1.0, self.opacity * op))
            return (anim_x, anim_y, w, h, rotation, opacity)
        return (self.x, self.y, self.w, self.h, self.rotation, self.opacity)

    # ------------------ IMAGE & VIDEO EFFECT PROCESSING ------------------
    def load_video(self, file_path: str):
        """Loads a video overlay clip from disk and pre-caches frames for zero-lag 60fps playback (like GIF)."""
        self.video_path = file_path
        self.image_path = file_path
        self.item_type = "video"
        self._video_frames = []
        self._video_total_duration_ms = 0
        try:
            cap = cv2.VideoCapture(file_path)
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 1)
                self.video_fps = fps
                self.video_duration = frame_count / max(1.0, fps)
                self._video_total_duration_ms = max(50, int(self.video_duration * 1000))

                # Pre-decode up to 240 frames (~10s at 24fps) into memory for instant zero-lag lookup
                step = 1 if frame_count <= 240 else max(1, frame_count // 240)
                frame_idx = 0
                first_frame = True
                while cap.isOpened() and len(self._video_frames) < 240:
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        break
                    if frame_idx % step == 0:
                        h, w = frame.shape[:2]
                        if first_frame:
                            aspect = w / max(1, h)
                            self.h = self.w / aspect if aspect > 0 else self.w
                            first_frame = False

                        # Scale down overlay frame if oversized to optimize RAM
                        if w > 854:
                            sc = 854.0 / w
                            frame = cv2.resize(frame, (int(w * sc), int(h * sc)), interpolation=cv2.INTER_AREA)
                            h, w = frame.shape[:2]

                        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        qimg = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888)
                        pix = QPixmap.fromImage(qimg.copy())
                        frame_time_ms = int((frame_idx / max(1.0, fps)) * 1000)
                        self._video_frames.append((pix, frame_time_ms))
                    frame_idx += 1
                cap.release()

                if self._video_frames:
                    self._processed_pixmap = self._video_frames[0][0]
                    self._raw_image = self._video_frames[0][0].toImage()
        except Exception as e:
            print(f"Error loading video overlay: {e}")

    def load_image(self, file_path: str):
        """Loads an image, sticker, or animated GIF from disk."""
        self.image_path = file_path
        self._gif_frames = []
        self._gif_total_duration_ms = 0

        # 1. Animated GIF Ingestion (reads all animation frames for zero-lag 60fps playback)
        if file_path.lower().endswith(".gif"):
            try:
                reader = QImageReader(file_path)
                if reader.supportsAnimation():
                    total_ms = 0
                    while True:
                        qimg = reader.read()
                        if qimg.isNull():
                            break
                        delay = max(20, reader.nextImageDelay())
                        pix = QPixmap.fromImage(qimg.copy())
                        self._gif_frames.append((pix, delay, total_ms))
                        total_ms += delay
                    self._gif_total_duration_ms = max(20, total_ms)
                    if self._gif_frames:
                        self._raw_image = QImage(file_path)
                        self._processed_pixmap = self._gif_frames[0][0]
                        aspect = self._gif_frames[0][0].width() / max(1, self._gif_frames[0][0].height())
                        self.h = self.w / aspect if aspect > 0 else self.w
                        return
            except Exception as e:
                print(f"GIF loading error, falling back to static: {e}")

        # 2. Static image fallback (PNG, JPG, WEBP, SVG, BMP)
        qimg = QImage(file_path)
        if not qimg.isNull():
            self._raw_image = qimg
            aspect = qimg.width() / max(1, qimg.height())
            self.h = self.w / aspect if aspect > 0 else self.w
            self.update_effects()

    def get_frame_pixmap(self, current_time: float = None) -> QPixmap:
        """Returns the active pixmap for given timeline timestamp (smooth live GIF and video sync)."""
        if current_time is None:
            return self._processed_pixmap

        # (a) Animated GIF Frame Look-up
        if getattr(self, "_gif_frames", None) and getattr(self, "_gif_total_duration_ms", 0) > 0:
            local_ms = int(max(0.0, current_time - self.start_time) * 1000)
            rel_ms = local_ms % self._gif_total_duration_ms
            for pix, dur, st_ms in self._gif_frames:
                if st_ms <= rel_ms < st_ms + dur:
                    return pix
            return self._gif_frames[-1][0]

        # (b) Synchronized Video Overlay playback (Zero-Lag Frame Cache, exactly like GIF!)
        if self.item_type == "video" and getattr(self, "_video_frames", None):
            v_dur_ms = getattr(self, "_video_total_duration_ms", 0)
            if v_dur_ms <= 0:
                v_dur_ms = max(50, int(getattr(self, "video_duration", 5.0) * 1000))
            local_ms = int(max(0.0, current_time - self.start_time) * 1000)
            rel_ms = local_ms % max(1, v_dur_ms)

            frames = self._video_frames
            n_frames = len(frames)
            if n_frames == 1:
                return frames[0][0]

            idx = int((rel_ms / max(1, v_dur_ms)) * n_frames)
            idx = max(0, min(n_frames - 1, idx))
            return frames[idx][0]

        return self._processed_pixmap

    def update_effects(self):
        """Applies real OpenCV unsharp mask (sharpness) and Gaussian blur filters."""
        if self._raw_image is None or self._raw_image.isNull():
            return

        # Fast path: No effects applied
        if self.sharpness <= 0 and self.blur <= 0:
            self._processed_pixmap = QPixmap.fromImage(self._raw_image)
            return

        try:
            # Convert QImage to OpenCV BGRA numpy array
            qimg = self._raw_image.convertToFormat(QImage.Format.Format_RGBA8888)
            ptr = qimg.bits()
            ptr.setsize(qimg.sizeInBytes())
            arr = np.frombuffer(ptr, np.uint8).reshape((qimg.height(), qimg.width(), 4))
            bgr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
            alpha = arr[:, :, 3]

            # 1. Apply Gaussian Blur if requested (0 to 100)
            if self.blur > 0:
                k = int((self.blur / 100.0) * 25) * 2 + 1  # 1 to 51 odd kernel
                bgr = cv2.GaussianBlur(bgr, (k, k), 0)
                alpha = cv2.GaussianBlur(alpha, (k, k), 0)

            # 2. Apply Real Sharpness via Unsharp Masking if requested (0 to 100)
            if self.sharpness > 0:
                alpha_factor = (self.sharpness / 100.0) * 1.5
                blurred_base = cv2.GaussianBlur(bgr, (0, 0), 3)
                bgr = cv2.addWeighted(bgr, 1.0 + alpha_factor, blurred_base, -alpha_factor, 0)

            # Recombine with alpha channel
            rgba = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA)
            rgba[:, :, 3] = alpha

            # Convert back to QPixmap
            res_img = QImage(rgba.data, rgba.shape[1], rgba.shape[0], rgba.strides[0], QImage.Format.Format_RGBA8888)
            self._processed_pixmap = QPixmap.fromImage(res_img.copy())
        except Exception as e:
            print(f"Effect processing error on item {self.name}: {e}")
            self._processed_pixmap = QPixmap.fromImage(self._raw_image)

    # ------------------ GEOMETRY & TRANSFORMS ------------------
    def get_pixel_rect(self, canvas_w: int, canvas_h: int, current_time: float = None) -> QRectF:
        """Returns the unrotated bounding rectangle in canvas pixel space."""
        if getattr(self, "motion_path", None) and current_time is not None:
            cx_n, cy_n, w_n, h_n, _, _ = self.get_animated_state(current_time)
            pw = max(16.0, w_n * canvas_w)
            ph = max(16.0, h_n * canvas_h)
            cx = cx_n * canvas_w
            cy = cy_n * canvas_h
            return QRectF(cx - pw / 2.0, cy - ph / 2.0, pw, ph)

        pw = max(16.0, self.w * canvas_w)
        ph = max(16.0, self.h * canvas_h)
        cx = self.x * canvas_w
        cy = self.y * canvas_h
        return QRectF(cx - pw / 2.0, cy - ph / 2.0, pw, ph)

    def get_transform(self, canvas_w: int, canvas_h: int, current_time: float = None) -> QTransform:
        """Returns the complete QTransform (translation to center + rotation)."""
        if getattr(self, "motion_path", None) and current_time is not None:
            cx_n, cy_n, _, _, rot_val, _ = self.get_animated_state(current_time)
            cx = cx_n * canvas_w
            cy = cy_n * canvas_h
        else:
            cx = self.x * canvas_w
            cy = self.y * canvas_h
            rot_val = self.rotation

        t = QTransform()
        t.translate(cx, cy)
        t.rotate(rot_val)
        t.translate(-cx, -cy)
        return t

    def get_inverse_transform(self, canvas_w: int, canvas_h: int, current_time: float = None) -> QTransform:
        """Returns the inverse transform for accurate mouse hit testing."""
        t = self.get_transform(canvas_w, canvas_h, current_time)
        inv, _ = t.inverted()
        return inv

    def contains_point(self, pt: QPointF, canvas_w: int, canvas_h: int, current_time: float = None) -> bool:
        """Hit test checking if cursor point is inside this rotated item."""
        if not self.is_visible:
            return False
        inv = self.get_inverse_transform(canvas_w, canvas_h, current_time)
        local_pt = inv.map(pt)
        rect = self.get_pixel_rect(canvas_w, canvas_h, current_time)
        # Expand hit area slightly by 6px for easy selection
        return rect.adjusted(-6, -6, 6, 6).contains(local_pt)

    def get_handles(self, canvas_w: int, canvas_h: int, current_time: float = None) -> dict:
        """
        Calculates handle positions in canvas pixel space:
        4 Corners, 4 Sides, and 1 Top Rotation Handle.
        """
        rect = self.get_pixel_rect(canvas_w, canvas_h, current_time)
        t = self.get_transform(canvas_w, canvas_h, current_time)

        # Unrotated handle center coordinates
        unrotated = {
            "top_left": rect.topLeft(),
            "top_right": rect.topRight(),
            "bottom_left": rect.bottomLeft(),
            "bottom_right": rect.bottomRight(),
            "top_mid": QPointF(rect.center().x(), rect.top()),
            "bottom_mid": QPointF(rect.center().x(), rect.bottom()),
            "left_mid": QPointF(rect.left(), rect.center().y()),
            "right_mid": QPointF(rect.right(), rect.center().y()),
            "rotate": QPointF(rect.center().x(), rect.top() - self.ROTATE_OFFSET)
        }

        # Apply transformation to get canvas positions
        handles = {}
        for k, p in unrotated.items():
            handles[k] = t.map(p)
        return handles

    def get_handle_at(self, pt: QPointF, canvas_w: int, canvas_h: int, current_time: float = None) -> str:
        """Determines which resize/rotate handle the cursor is hovering over."""
        if self.is_locked or not self.is_visible:
            return None
        handles = self.get_handles(canvas_w, canvas_h, current_time)
        radius_sq = (self.HANDLE_SIZE + 4) ** 2

        for h_name, h_pt in handles.items():
            dx = pt.x() - h_pt.x()
            dy = pt.y() - h_pt.y()
            if (dx * dx + dy * dy) <= radius_sq:
                return h_name
        return None

    # ------------------ RENDERING ------------------
    def render(self, painter: QPainter, canvas_w: int, canvas_h: int, is_selected: bool = False, bg_pixmap: QPixmap = None, current_time: float = None):
        """Renders the canvas object, its contents, and Canva-like selection controls."""
        if not self.is_visible:
            return

        # If current_time is provided and item is not active at this time, don't render (unless selected)
        if current_time is not None and not self.is_active_at(current_time):
            if not is_selected:
                return

        painter.save()
        rect = self.get_pixel_rect(canvas_w, canvas_h, current_time)
        transform = self.get_transform(canvas_w, canvas_h, current_time)
        painter.setTransform(transform, True)
        
        # If animated, apply dynamic animated opacity
        if getattr(self, "motion_path", None) and current_time is not None:
            _, _, _, _, _, anim_op = self.get_animated_state(current_time)
            eff_opacity = anim_op if (self.is_active_at(current_time)) else (anim_op * 0.4)
        else:
            eff_opacity = self.opacity if (current_time is None or self.is_active_at(current_time)) else (self.opacity * 0.4)
        painter.setOpacity(eff_opacity)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # --- 1. Render Specific Item Content ---
        if self.item_type in ("image", "sticker", "video"):
            pix = self.get_frame_pixmap(current_time)
            if pix and not pix.isNull():
                painter.drawPixmap(rect.toRect(), pix)
                if self.item_type == "video":
                    # Video Indicator Tag
                    painter.fillRect(int(rect.left() + 4), int(rect.top() + 4), 60, 18, QColor(15, 23, 42, 210))
                    painter.setPen(QPen(QColor("#f43f5e"), 1))
                    painter.drawRect(int(rect.left() + 4), int(rect.top() + 4), 60, 18)
                    painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                    painter.setPen(QColor("#fda4af"))
                    painter.drawText(int(rect.left() + 7), int(rect.top() + 16), "🎬 VIDEO")
                elif getattr(self, "_gif_frames", None):
                    # Animated GIF Indicator Tag
                    painter.fillRect(int(rect.left() + 4), int(rect.top() + 4), 46, 18, QColor(15, 23, 42, 210))
                    painter.setPen(QPen(QColor("#a855f7"), 1))
                    painter.drawRect(int(rect.left() + 4), int(rect.top() + 4), 46, 18)
                    painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                    painter.setPen(QColor("#d8b4fe"))
                    painter.drawText(int(rect.left() + 7), int(rect.top() + 16), "✨ GIF")
            else:
                # Placeholder frame
                painter.setPen(QPen(QColor("#64748b"), 1, Qt.PenStyle.DashLine))
                painter.setBrush(QBrush(QColor(15, 23, 42, 140)))
                painter.drawRoundedRect(rect, 6, 6)
                painter.setPen(QColor("#94a3b8"))
                label = "🎬 Video Overlay" if self.item_type == "video" else "🖼️ Image Placeholder"
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

        elif self.item_type in ("subtitle", "text"):
            self._render_text_content(painter, rect, canvas_h, current_time)

        elif self.item_type == "shape":
            stype = getattr(self, "shape_type", "rect")
            b_width = getattr(self, "border_width", 0)
            s_style = getattr(self, "stroke_style", "solid")

            # 1. Prepare Brush (Fill)
            if getattr(self, "fill_color", None) and self.fill_color.alpha() > 0 and stype not in ("line", "arrow", "double_arrow"):
                painter.setBrush(QBrush(self.fill_color))
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)

            # 2. Prepare Pen (Stroke)
            b_color = getattr(self, "border_color", QColor("#38bdf8"))
            if b_width > 0 and s_style != "none" and b_color:
                pen = QPen(b_color, b_width)
                if s_style == "dashed":
                    pen.setStyle(Qt.PenStyle.DashLine)
                elif s_style == "dotted":
                    pen.setStyle(Qt.PenStyle.DotLine)
                else:
                    pen.setStyle(Qt.PenStyle.SolidLine)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
            elif stype in ("line", "arrow", "double_arrow"):
                # Lines always have a visible stroke
                eff_w = max(2, b_width if b_width > 0 else 4)
                eff_col = b_color if (b_color and b_color.alpha() > 0) else getattr(self, "fill_color", QColor("#38bdf8"))
                pen = QPen(eff_col, eff_w)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
            else:
                pen = QPen(Qt.PenStyle.NoPen)
                painter.setPen(pen)

            # Optional Neon Glow / Outer Shadow Layer
            if getattr(self, "glow_enabled", False):
                glow_col = getattr(self, "glow_color", QColor("#38bdf8"))
                painter.save()
                for gw, g_alpha in [(12, 35), (8, 60), (4, 100)]:
                    g_pen = QPen(QColor(glow_col.red(), glow_col.green(), glow_col.blue(), g_alpha), pen.width() + gw)
                    g_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    g_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    painter.setPen(g_pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    if stype in ("line", "arrow", "double_arrow"):
                        y_m = rect.center().y()
                        painter.drawLine(QPointF(rect.left(), y_m), QPointF(rect.right(), y_m))
                    elif stype in ("rect", "rounded_rect"):
                        rad = getattr(self, "corner_radius", 0.0)
                        if rad > 0:
                            painter.drawRoundedRect(rect, rad, rad)
                        else:
                            painter.drawRect(rect)
                    elif stype == "circle":
                        painter.drawEllipse(rect)
                painter.restore()

            # 3. Draw Shape Geometry
            r_tl = getattr(self, "radius_tl", getattr(self, "corner_radius", 0.0))
            r_tr = getattr(self, "radius_tr", getattr(self, "corner_radius", 0.0))
            r_bl = getattr(self, "radius_bl", getattr(self, "corner_radius", 0.0))
            r_br = getattr(self, "radius_br", getattr(self, "corner_radius", 0.0))

            if stype in ("rect", "rounded_rect"):
                if max(r_tl, r_tr, r_bl, r_br) > 0.5:
                    self._draw_rounded_rect_complex(painter, rect, r_tl, r_tr, r_bl, r_br)
                else:
                    painter.drawRect(rect)
            elif stype == "circle":
                painter.drawEllipse(rect)
            elif stype in ("line", "arrow", "double_arrow"):
                self._draw_line_or_arrow(painter, rect, stype, pen)
            elif stype == "triangle":
                self._draw_triangle(painter, rect)
            elif stype == "star":
                self._draw_star(painter, rect)
            elif stype == "heart":
                self._draw_heart(painter, rect)
            elif stype == "badge":
                painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
            else:
                painter.drawRect(rect)

        elif self.item_type in ("blur_box", "blur", "mosaic", "glass", "blackout"):
            pixel_rect = rect.toRect()
            has_bg = False
            b_mode = getattr(self, "blur_mode", "blur")
            radius = getattr(self, "corner_radius", 0)

            # Optional rounded corner clipping
            if radius > 0:
                clip_path = QPainterPath()
                clip_path.addRoundedRect(rect, radius, radius)
                painter.save()
                painter.setClipPath(clip_path)

            if bg_pixmap and not bg_pixmap.isNull():
                pw, ph = bg_pixmap.width(), bg_pixmap.height()
                src_x = int((self.x - self.w / 2.0) * pw)
                src_y = int((self.y - self.h / 2.0) * ph)
                src_w = int(self.w * pw)
                src_h = int(self.h * ph)

                src_x = max(0, min(pw - 1, src_x))
                src_y = max(0, min(ph - 1, src_y))
                src_w = max(4, min(pw - src_x, src_w))
                src_h = max(4, min(ph - src_y, src_h))

                cropped = bg_pixmap.copy(src_x, src_y, src_w, src_h)
                if not cropped.isNull():
                    has_bg = True
                    if b_mode == "mosaic":
                        factor = max(4, int(20 * (self.blur_strength / 25.0)))
                        sw = max(2, cropped.width() // factor)
                        sh = max(2, cropped.height() // factor)
                        small = cropped.scaled(sw, sh, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
                        censored = small.scaled(pixel_rect.width(), pixel_rect.height(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
                    elif b_mode == "blackout":
                        censored = None
                    else:
                        # Smooth Blur or Frosted Glass
                        factor = max(6, int(18 * (self.blur_strength / 25.0)))
                        sw = max(2, cropped.width() // factor)
                        sh = max(2, cropped.height() // factor)
                        small = cropped.scaled(sw, sh, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
                        censored = small.scaled(pixel_rect.width(), pixel_rect.height(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)

                    if censored is not None:
                        painter.drawPixmap(pixel_rect, censored)

            if not has_bg:
                painter.setPen(QPen(QColor("#64748b"), 1, Qt.PenStyle.DashLine))
                painter.setBrush(QBrush(QColor(15, 23, 42, 180)))
                if radius > 0:
                    painter.drawRoundedRect(rect, radius, radius)
                else:
                    painter.drawRect(rect)
                painter.setPen(QColor("#38bdf8"))
                painter.setFont(QFont("Kantumruy Pro", 10, QFont.Weight.Bold))
                mode_txt = "✨ Frosted Glass" if b_mode == "glass" else ("⬛ Blackout Bar" if b_mode == "blackout" else ("🔲 Mosaic Box" if b_mode == "mosaic" else "🌫️ Blur Box"))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{mode_txt}\n(បិទបាំងវីដេអូ)")
            else:
                # Custom Styling based on Mode
                if b_mode == "glass":
                    # Modern Frosted Glassmorphism: diagonal specular sheen & white glow
                    glass_grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
                    glass_grad.setColorAt(0.0, QColor(255, 255, 255, int(90 * self.opacity)))
                    glass_grad.setColorAt(0.4, QColor(255, 255, 255, int(30 * self.opacity)))
                    glass_grad.setColorAt(1.0, QColor(186, 230, 253, int(60 * self.opacity)))
                    painter.setBrush(QBrush(glass_grad))
                    painter.setPen(Qt.PenStyle.NoPen)
                    if radius > 0:
                        painter.drawRoundedRect(rect, radius, radius)
                    else:
                        painter.drawRect(rect)

                    # Frosted specular border
                    border_pen = QPen(QColor(255, 255, 255, int(180 * self.opacity)), 1.5)
                    painter.setPen(border_pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    if radius > 0:
                        painter.drawRoundedRect(rect, radius, radius)
                    else:
                        painter.drawRect(rect)

                elif b_mode == "blackout":
                    # Cinema Blackout Bar
                    tint_alpha = int(255 * self.opacity)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(QColor(0, 0, 0, tint_alpha)))
                    if radius > 0:
                        painter.drawRoundedRect(rect, radius, radius)
                    else:
                        painter.drawRect(rect)

                else:
                    # Smooth Blur or Mosaic tint
                    tint_alpha = int(75 * self.opacity)
                    tint_col = getattr(self, "glass_tint_color", QColor(15, 23, 42))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(QColor(tint_col.red(), tint_col.green(), tint_col.blue(), tint_alpha)))
                    if radius > 0:
                        painter.drawRoundedRect(rect, radius, radius)
                    else:
                        painter.drawRect(rect)

                    # Subtle boundary outline for manipulation only when selected
                    if is_selected:
                        painter.setPen(QPen(QColor(56, 189, 248, 140), 1, Qt.PenStyle.DotLine))
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        if radius > 0:
                            painter.drawRoundedRect(rect, radius, radius)
                        else:
                            painter.drawRect(rect)

            if radius > 0:
                painter.restore()

        painter.restore()

        # --- 2. Render Canva-Style Transformation Bounding Box ---
        if is_selected:
            self._render_canva_bounding_box(painter, canvas_w, canvas_h)

    def _render_canva_bounding_box(self, painter: QPainter, canvas_w: int, canvas_h: int):
        """Draws Canva's signature bounding box, corner dots, pill side handles, and rotation anchor."""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.get_pixel_rect(canvas_w, canvas_h)
        t = self.get_transform(canvas_w, canvas_h)
        painter.setTransform(t, True)

        # Canva signature purple-blue bounding line (#8b5cf6 / #0ea5e9)
        box_color = QColor("#0ea5e9") if not self.is_locked else QColor("#ef4444")
        pen = QPen(box_color, 2, Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)

        if not self.is_locked:
            # Vertical stem to rotation handle
            stem_pen = QPen(QColor("#0ea5e9"), 1.5, Qt.PenStyle.DashLine)
            painter.setPen(stem_pen)
            top_center = QPointF(rect.center().x(), rect.top())
            rot_center = QPointF(rect.center().x(), rect.top() - self.ROTATE_OFFSET)
            painter.drawLine(top_center, rot_center)

            # Circular Rotation Handle
            painter.setPen(QPen(QColor("#0ea5e9"), 2))
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.drawEllipse(rot_center, 9, 9)

            # Tiny rotation icon inside circular handle
            painter.setPen(QPen(QColor("#0ea5e9"), 1.5))
            painter.drawArc(QRectF(rot_center.x() - 5, rot_center.y() - 5, 10, 10), 45 * 16, 270 * 16)

            # 4 White Circular Corner Handles
            painter.setPen(QPen(QColor("#0ea5e9"), 2))
            painter.setBrush(QBrush(QColor("#ffffff")))
            hs = self.HANDLE_SIZE / 2.0
            for pt in [rect.topLeft(), rect.topRight(), rect.bottomLeft(), rect.bottomRight()]:
                painter.drawEllipse(pt, hs, hs)

            # 4 Pill-shaped Side Handles
            painter.setBrush(QBrush(QColor("#ffffff")))
            # Top & Bottom mid handles (horizontal pills)
            for pt in [QPointF(rect.center().x(), rect.top()), QPointF(rect.center().x(), rect.bottom())]:
                painter.drawRoundedRect(QRectF(pt.x() - 8, pt.y() - 3, 16, 6), 3, 3)
            # Left & Right mid handles (vertical pills)
            for pt in [QPointF(rect.left(), rect.center().y()), QPointF(rect.right(), rect.center().y())]:
                painter.drawRoundedRect(QRectF(pt.x() - 3, pt.y() - 8, 6, 16), 3, 3)

        else:
            # Locked badge icon at top right
            painter.setBrush(QBrush(QColor("#ef4444")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(rect.right() - 20, rect.top() - 24, 20, 20), 4, 4)
            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.drawText(QRectF(rect.right() - 20, rect.top() - 24, 20, 20), Qt.AlignmentFlag.AlignCenter, "🔒")

        painter.restore()

    def _draw_star(self, painter: QPainter, rect: QRectF, points: int = 5):
        """Draws a vector 5-pointed star inside the bounding rectangle."""
        path = QPainterPath()
        cx = rect.center().x()
        cy = rect.center().y()
        r_outer = min(rect.width(), rect.height()) / 2.0
        r_inner = r_outer * 0.42

        angle = -math.pi / 2.0
        step = math.pi / points

        for i in range(points * 2):
            r = r_outer if i % 2 == 0 else r_inner
            px = cx + r * math.cos(angle)
            py = cy + r * math.sin(angle)
            if i == 0:
                path.moveTo(px, py)
            else:
                path.lineTo(px, py)
            angle += step

        path.closeSubpath()
        painter.drawPath(path)

    def _draw_rounded_rect_complex(self, painter: QPainter, rect: QRectF, r_tl: float, r_tr: float, r_bl: float, r_br: float):
        """Draws rounded rectangle with distinct Top-Left, Top-Right, Bottom-Left, Bottom-Right corner radii (Photoshop-standard)."""
        path = QPainterPath()
        x = rect.x()
        y = rect.y()
        w = rect.width()
        h = rect.height()
        max_r = min(w / 2.0, h / 2.0)
        r_tl = min(max_r, max(0.0, float(r_tl)))
        r_tr = min(max_r, max(0.0, float(r_tr)))
        r_br = min(max_r, max(0.0, float(r_br)))
        r_bl = min(max_r, max(0.0, float(r_bl)))

        path.moveTo(x + r_tl, y)
        path.lineTo(x + w - r_tr, y)
        if r_tr > 0:
            path.arcTo(x + w - 2 * r_tr, y, 2 * r_tr, 2 * r_tr, 90, -90)
        path.lineTo(x + w, y + h - r_br)
        if r_br > 0:
            path.arcTo(x + w - 2 * r_br, y + h - 2 * r_br, 2 * r_br, 2 * r_br, 0, -90)
        path.lineTo(x + r_bl, y + h)
        if r_bl > 0:
            path.arcTo(x, y + h - 2 * r_bl, 2 * r_bl, 2 * r_bl, 270, -90)
        path.lineTo(x, y + r_tl)
        if r_tl > 0:
            path.arcTo(x, y, 2 * r_tl, 2 * r_tl, 180, -90)
        path.closeSubpath()
        painter.drawPath(path)

    def _draw_line_or_arrow(self, painter: QPainter, rect: QRectF, stype: str, pen: QPen):
        """Renders crisp vector straight line or arrow with styled heads."""
        y_mid = rect.center().y()
        p1 = QPointF(rect.left(), y_mid)
        p2 = QPointF(rect.right(), y_mid)

        b_width = max(1, pen.width())
        arrow_size = float(getattr(self, "arrowhead_size", max(10.0, b_width * 2.8)))
        arrow_color = pen.color() if pen.style() != Qt.PenStyle.NoPen else getattr(self, "border_color", QColor("#38bdf8"))

        line_p1 = QPointF(p1)
        line_p2 = QPointF(p2)
        if stype in ("arrow", "double_arrow"):
            line_p2 = QPointF(max(p1.x(), p2.x() - arrow_size * 0.7), y_mid)
        if stype == "double_arrow":
            line_p1 = QPointF(min(p2.x(), p1.x() + arrow_size * 0.7), y_mid)

        # Draw main stem line
        painter.setPen(pen)
        painter.drawLine(line_p1, line_p2)

        # Draw arrowheads
        head_brush = QBrush(arrow_color)
        head_pen = QPen(arrow_color, 1)

        if stype in ("arrow", "double_arrow"):
            # Right Arrowhead
            a_path = QPainterPath()
            a_path.moveTo(p2.x(), y_mid)
            a_path.lineTo(p2.x() - arrow_size, y_mid - arrow_size * 0.55)
            a_path.lineTo(p2.x() - arrow_size * 0.7, y_mid)
            a_path.lineTo(p2.x() - arrow_size, y_mid + arrow_size * 0.55)
            a_path.closeSubpath()
            painter.setPen(head_pen)
            painter.setBrush(head_brush)
            painter.drawPath(a_path)

        if stype == "double_arrow":
            # Left Arrowhead
            l_path = QPainterPath()
            l_path.moveTo(p1.x(), y_mid)
            l_path.lineTo(p1.x() + arrow_size, y_mid - arrow_size * 0.55)
            l_path.lineTo(p1.x() + arrow_size * 0.7, y_mid)
            l_path.lineTo(p1.x() + arrow_size, y_mid + arrow_size * 0.55)
            l_path.closeSubpath()
            painter.setPen(head_pen)
            painter.setBrush(head_brush)
            painter.drawPath(l_path)

    def _draw_triangle(self, painter: QPainter, rect: QRectF):
        """Draws an equilateral or isosceles triangle."""
        path = QPainterPath()
        path.moveTo(rect.center().x(), rect.top())
        path.lineTo(rect.right(), rect.bottom())
        path.lineTo(rect.left(), rect.bottom())
        path.closeSubpath()
        painter.drawPath(path)

    def _draw_heart(self, painter: QPainter, rect: QRectF):
        """Draws a smooth vector heart shape."""
        path = QPainterPath()
        cx = rect.center().x()
        top = rect.top()
        bot = rect.bottom()
        w = rect.width()
        h = rect.height()
        path.moveTo(cx, top + h * 0.28)
        path.cubicTo(cx, top, rect.left(), top, rect.left(), top + h * 0.35)
        path.cubicTo(rect.left(), top + h * 0.65, cx, top + h * 0.85, cx, bot)
        path.cubicTo(cx, top + h * 0.85, rect.right(), top + h * 0.65, rect.right(), top + h * 0.35)
        path.cubicTo(rect.right(), top, cx, top, cx, top + h * 0.28)
        path.closeSubpath()
        painter.drawPath(path)

    def _render_text_content(self, painter: QPainter, rect: QRectF, canvas_h: int, current_time: float = None):
        """Renders typography text or CC subtitles with live 60fps animations (Karaoke, Pop, Fade, Slide, Bounce, Typewriter)."""
        is_sub = (self.item_type == "subtitle")
        anim = (getattr(self, "animation", "none") or "none").lower()
        txt = str(self.text or "")
        if not txt.strip():
            return

        # Calculate animation timeline parameters
        st = float(getattr(self, "start_time", 0.0))
        et = float(getattr(self, "end_time", 0.0))
        dur = max(0.2, (et - st) if et > st else 3.5)
        elapsed = 0.5
        if current_time is not None and st > 0:
            elapsed = max(0.0, current_time - st)
        elif current_time is not None and current_time > 0:
            elapsed = max(0.0, current_time % dur)
        progress = min(1.0, max(0.0, elapsed / dur))

        draw_rect = QRectF(rect)
        orig_opacity = painter.opacity()

        # Apply Entry / Exit Visual Animations
        if anim == "fade":
            fade_in = min(1.0, elapsed / 0.25)
            fade_out = min(1.0, max(0.0, (dur - elapsed) / 0.25))
            painter.setOpacity(orig_opacity * min(fade_in, fade_out))

        elif anim == "popup":
            if elapsed < 0.14:
                sc = 0.70 + 0.45 * (elapsed / 0.14)
            elif elapsed < 0.26:
                sc = 1.15 - 0.15 * ((elapsed - 0.14) / 0.12)
            else:
                sc = 1.0
            cx, cy = draw_rect.center().x(), draw_rect.center().y()
            nw, nh = draw_rect.width() * sc, draw_rect.height() * sc
            draw_rect = QRectF(cx - nw / 2.0, cy - nh / 2.0, nw, nh)

        elif anim == "slide":
            if elapsed < 0.22:
                dy = 24.0 * (1.0 - (elapsed / 0.22))
                draw_rect.translate(0, dy)

        elif anim == "bounce":
            if elapsed < 0.35:
                decay = 1.0 - (elapsed / 0.35)
                dy = -math.sin((elapsed / 0.35) * math.pi * 3) * 12.0 * decay
                draw_rect.translate(0, dy)

        display_text = txt
        if anim == "typewriter":
            chars = max(1, min(len(txt), int((progress / 0.75) * len(txt))))
            display_text = txt[:chars]

        # 1. Render Background Box / Pill
        if is_sub:
            painter.setPen(Qt.PenStyle.NoPen)
            bg_col = getattr(self, "bg_color", None)
            if bg_col and bg_col.alpha() > 0:
                painter.setBrush(QBrush(bg_col))
            else:
                painter.setBrush(QBrush(QColor(0, 0, 0, 195)))
            painter.drawRoundedRect(draw_rect, 6, 6)
        elif getattr(self, "bg_color", None) and self.bg_color.alpha() > 0:
            painter.setBrush(QBrush(self.bg_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(draw_rect, 4, 4)

        # 2. Font configuration
        scale_ratio = canvas_h / 720.0
        base_fs = max(8, int(getattr(self, "font_size", 28) or 28))
        font_size = max(10 if is_sub else 8, int(base_fs * max(0.25, scale_ratio)))
        font = QFont(self.font_family, max(8, font_size))
        font.setBold(self.is_bold if not is_sub else True)
        font.setItalic(self.is_italic)
        painter.setFont(font)

        # 3. Text Rendering (Base Layer)
        text_color = QColor(self.font_color) if self.font_color else (QColor("#facc15") if is_sub else QColor("#ffffff"))
        painter.setPen(text_color)

        if anim in ("marquee", "news_ticker", "ticker"):
            # News Ticker Marquee ("រត់ដូចព័ត៌មាន")
            painter.save()
            painter.setClipRect(draw_rect)
            fm = painter.fontMetrics()
            tw = max(10, fm.horizontalAdvance(display_text))
            th = max(10, fm.height())
            dir_mode = getattr(self, "marquee_direction", "right_to_left") or "right_to_left"
            is_loop = getattr(self, "marquee_loop", True)
            spd = max(0.1, float(getattr(self, "marquee_speed", 1.0) or 1.0))
            gap = 60.0

            if dir_mode in ("right_to_left", "left_to_right"):
                travel = draw_rect.width() + tw + gap
                px_per_sec = 110.0 * spd
                cycle = max(0.8, travel / px_per_sec)
                p = (elapsed % cycle) / cycle if is_loop else min(1.0, elapsed / cycle)
                base_y = draw_rect.center().y() + th * 0.35

                if dir_mode == "right_to_left":
                    x1 = draw_rect.right() - p * travel
                    painter.drawText(QPointF(x1, base_y), display_text)
                    if is_loop and (x1 + tw + gap < draw_rect.right() + tw + gap):
                        painter.drawText(QPointF(x1 + tw + gap, base_y), display_text)
                else:  # left_to_right
                    x1 = draw_rect.left() - tw + p * travel
                    painter.drawText(QPointF(x1, base_y), display_text)
                    if is_loop and (x1 - (tw + gap) > draw_rect.left() - tw - gap):
                        painter.drawText(QPointF(x1 - (tw + gap), base_y), display_text)

            else:  # bottom_to_top or top_to_bottom
                travel = draw_rect.height() + th + gap
                px_per_sec = 60.0 * spd
                cycle = max(0.8, travel / px_per_sec)
                p = (elapsed % cycle) / cycle if is_loop else min(1.0, elapsed / cycle)
                base_x = draw_rect.center().x() - tw / 2.0

                if dir_mode == "bottom_to_top":
                    y1 = draw_rect.bottom() + th - p * travel
                    painter.drawText(QPointF(base_x, y1), display_text)
                    if is_loop and (y1 + th + gap < draw_rect.bottom() + th + gap):
                        painter.drawText(QPointF(base_x, y1 + th + gap), display_text)
                else:  # top_to_bottom
                    y1 = draw_rect.top() - th + p * travel
                    painter.drawText(QPointF(base_x, y1), display_text)
                    if is_loop and (y1 - (th + gap) > draw_rect.top() - th - gap):
                        painter.drawText(QPointF(base_x, y1 - (th + gap)), display_text)

            painter.restore()
        else:
            painter.drawText(draw_rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, display_text)

        # 4. Karaoke Highlight Wiping Overlay (Progressive Color Fill)
        if anim == "karaoke" and progress > 0.0:
            painter.save()
            kw = draw_rect.width() * min(1.0, progress * 1.08)
            clip_k = QRectF(draw_rect.x(), draw_rect.y(), kw, draw_rect.height())
            painter.setClipRect(clip_k)
            hi_col = getattr(self, "highlight_color", None) or QColor("#00E5FF")
            painter.setPen(QColor(hi_col))
            painter.drawText(draw_rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, display_text)
            painter.restore()

        # Restore opacity if changed by fade
        if anim == "fade":
            painter.setOpacity(orig_opacity)

    def clone(self) -> "CanvasItem":
        """Creates a duplicate of this item offset slightly for Canva-style copy-paste."""
        c = CanvasItem(
            item_type=self.item_type,
            x=min(0.9, self.x + 0.04),
            y=min(0.9, self.y + 0.04),
            w=self.w,
            h=self.h,
            rotation=self.rotation,
            opacity=self.opacity,
            z_index=self.z_index + 1,
            name=f"{self.name} Copy"
        )
        c.sharpness = self.sharpness
        c.blur = self.blur
        c.image_path = self.image_path
        c._raw_image = self._raw_image
        c._processed_pixmap = self._processed_pixmap
        c.text = self.text
        c.font_family = self.font_family
        c.font_size = self.font_size
        c.font_color = QColor(self.font_color)
        c.bg_color = QColor(self.bg_color)
        c.is_bold = self.is_bold
        c.is_italic = self.is_italic
        c.animation = getattr(self, "animation", "none")
        c.highlight_color = QColor(getattr(self, "highlight_color", QColor("#00E5FF")))
        c.marquee_direction = getattr(self, "marquee_direction", "right_to_left")
        c.marquee_loop = getattr(self, "marquee_loop", True)
        c.marquee_speed = getattr(self, "marquee_speed", 1.0)
        c.shape_type = self.shape_type
        c.fill_color = QColor(self.fill_color)
        c.border_color = QColor(self.border_color)
        c.border_width = self.border_width
        return c

