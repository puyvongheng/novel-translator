"""
Canva-Like Interactive Video Preview Canvas Component for PyQt6 / PySide6
Features:
- Drag & Drop media (images, stickers, shapes, text) at exact cursor coordinates
- Canva-style Transformation Bounding Box (8 resize handles, rotation anchor with degree display)
- Aspect ratios (16:9, 9:16, 1:1, 4:5, Custom/Fit)
- Normalized coordinate system ensuring zero drift on zoom, resize, or export
- Smart magnetic snapping guides (center lines, edges, safe margins)
- Multi-selection (marquee drag & Shift-click)
- Undo/Redo history stack, Copy, Paste, Duplicate, Delete, Lock, Hide, Layer ordering
- Real-time OpenCV Sharpness (unsharp mask) and Gaussian Blur processing
"""

import os
import math
import cv2
import numpy as np
from ui_v_PyQt6.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider,
    QComboBox, QFrame, QGroupBox, QMenu, QFileDialog, QInputDialog,
    Qt, QColor, QFont, QPen, QBrush, QPointF, QRectF, QTransform,
    QPainter, QImage, QPixmap, QPainterPath, QCursor, QToolTip,
    Signal, QKeySequence, QShortcut
)
from ui_v_PyQt6.components.player.canvas_item import CanvasItem
from ui_v_PyQt6.components.player.guide_dialogs import NewGuideDialog, NewGuideLayoutDialog


class CanvaPreviewCanvas(QWidget):
    """
    State-of-the-art Canva-like interactive video preview monitor:
    - Direct manipulation on canvas (Drag, Move, Resize, Rotate, Snap, Duplicate, Delete)
    - Aspect ratio masking & canvas zooming
    - Drag-and-drop ingestion from Media Library / OS
    - Real-time video frame background with live OpenCV Sharpness & Blur
    """
    item_selected = Signal(object)
    item_added = Signal(object)
    item_deleted = Signal(object)
    canvas_modified = Signal()
    video_dropped = Signal(str)
    subtitle_dropped = Signal(str)
    lut_dropped = Signal(str)
    resolution_changed = Signal(int, int, str)
    crop_offset_changed = Signal(float, float)   # (ox, oy)
    video_scale_changed = Signal(float)          # zoom scale factor (1.0x to 5.0x)
    video_transform_changed = Signal(dict)       # {scale, pos_x, pos_y, flip_h, flip_v, rotation}
    keyframe_added = Signal(dict)                # keyframe data
    keyframe_removed = Signal(float)             # timestamp
    keyframes_modified = Signal(list)            # all keyframes
    transform_mode_changed = Signal(bool)        # transform tool active / inactive
    subtitle_visibility_changed = Signal(bool)   # CC layer toggled on / off

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.is_subtitle_layer_visible = True

        # Video Frame Background
        self._current_frame_bgr = None
        self._processed_frame_pixmap = None
        self._blurred_frame_pixmap = None
        self.video_native_w = 1920
        self.video_native_h = 1080

        # Video Framing, Zoom, Pan, Flip & Keyframes System
        self.aspect_ratio_mode = "fit"  # "fit", "16:9", "9:16", "1:1", "4:5", "21:9", "custom"
        self.custom_w = 1080
        self.custom_h = 1920
        self.video_fit_mode = "fill"    # "fill" (Crop to Fill), "fit" (Fit + Blur Backdrop), "black" (Letterbox)
        self.video_scale = 1.0          # 1.0 (100%) to 5.0 (500% zoom)
        self.crop_offset_x = 0.0        # -2.0 (Left) to +2.0 (Right) for crop framing
        self.crop_offset_y = 0.0        # -2.0 (Top) to +2.0 (Bottom) for crop framing
        self.video_flip_h = False       # True = Flip Horizontal (ឆ្លុះឆ្វេង-ស្តាំ)
        self.video_flip_v = False       # True = Flip Vertical (ឆ្លុះលើ-ក្រោម)
        self.video_rotation_angle = 0.0 # 0, 90, 180, 270 degrees
        self.video_keyframes = []       # List of animation keyframe dicts
        self.is_transform_mode = False  # Video framing can ONLY be dragged when Transform tool is active!
        self.zoom_level = 1.0  # 1.0 = Fit to preview container
        self.show_grid = False
        self.show_rulers = True
        self.enable_snapping = True

        # Photoshop CC Guides & Rulers System
        self.guides_h = []           # List of float (normalized 0.0 to 1.0 relative to canvas height)
        self.guides_v = []           # List of float (normalized 0.0 to 1.0 relative to canvas width)
        self.show_guides = True      # Toggle guide lines visibility
        self.guides_locked = False   # Lock guides from accidental moving
        self._active_guide = None    # ("h", index) or ("v", index) currently dragged
        self._hover_guide = None     # ("h", index) or ("v", index) currently hovered
        self._drag_guide_current_pos = None  # QPointF position during drag

        # MediaPipe & OpenCV AI Face Tracking, AR & Auto Blur Engine
        self.face_mesh_detector = None
        self._detected_faces = []
        self.auto_face_blur_enabled = False
        self.auto_face_blur_mode = "blur"
        self.auto_face_blur_strength = 25
        self.auto_face_blur_shape = "ellipse"
        self.auto_face_blur_feather = True
        self.face_ar_enabled = False
        self.face_ar_prop = "glasses"
        self.face_ar_anchor = "eyes"
        self.face_ar_scale = 1.0
        self.face_ar_offset_y = 0.0
        self.face_ar_custom_pixmap = None
        self.face_mesh_overlay_enabled = False

        # Timeline Playhead Synchronization
        self.current_time = 0.0
        self.duration = 0.0

        # Global Canvas / Video Effects
        self.canvas_sharpness = 0  # 0 to 100
        self.canvas_blur = 0       # 0 to 100
        self.color_preset = "none" # "none", "cine_teal_orange", "film_kodak", etc.
        self.color_preset_intensity = 0.80 # 0.0 to 1.0
        self.active_subtitle_text = ""  # Live Subtitle Overlay

        # Interactive CC Subtitle CanvasItem (drag, resize, rotate on monitor)
        self._subtitle_item = None

        # Items & Selection
        self.items = []            # list of CanvasItem
        self.selected_items = []   # list of currently selected CanvasItem
        self.clipboard_item = None

        # Interactive Transform State
        self._interaction_mode = None  # None, "move", "resize", "rotate", "marquee"
        self._active_handle = None     # handle name string
        self._drag_start_pos = None    # QPointF
        self._item_initial_states = {} # item_id -> dict of x, y, w, h, rotation
        self._marquee_rect = None      # QRectF for rubber-band selection

        # Snapping Guide Lines
        self._snap_lines_h = []
        self._snap_lines_v = []

        # Undo / Redo History Stack (up to 40 states)
        self._undo_stack = []
        self._redo_stack = []

        # AI Auto Face Tracking & Dynamic Reframe State
        self.is_reframe_active = False
        self.reframe_trajectory = []
        self.reframe_keyframes = []
        self.reframe_crop_w = 607
        self.reframe_crop_h = 1080

        self._setup_shortcuts()

    # ------------------ ASPECT RATIO, SIZING & GEOMETRY ------------------
    def set_aspect_ratio(self, mode: str):
        """Sets canvas aspect ratio: '16:9', '9:16', '1:1', '4:5', '21:9', 'custom', 'fit'"""
        self.aspect_ratio_mode = mode
        w, h = self.get_current_canvas_resolution()
        lbl = self.get_aspect_ratio_label()
        self.resolution_changed.emit(w, h, lbl)
        self.update()

    def set_custom_resolution(self, w: int, h: int, fit_mode: str = None):
        """Sets user-defined custom width and height in pixels."""
        self.custom_w = max(100, int(w))
        self.custom_h = max(100, int(h))
        self.aspect_ratio_mode = "custom"
        if fit_mode:
            self.video_fit_mode = fit_mode
        w_cur, h_cur = self.get_current_canvas_resolution()
        lbl = f"Custom ({self.custom_w}x{self.custom_h})"
        self.resolution_changed.emit(w_cur, h_cur, lbl)
        self.update()

    def set_video_fit_mode(self, mode: str):
        """Sets framing mode: 'fill' (Crop to Fill), 'fit' (Fit + Blur Backdrop), 'black' (Letterbox)"""
        if mode in ("fill", "fit", "black"):
            self.video_fit_mode = mode
            self.update()

    def set_crop_offset(self, ox: float = 0.0, oy: float = 0.0):
        """Shifts video framing horizontally (-2.0 to 2.0) and vertically (-2.0 to 2.0) when cropping/zooming."""
        self.crop_offset_x = max(-2.0, min(2.0, float(ox)))
        self.crop_offset_y = max(-2.0, min(2.0, float(oy)))
        self.crop_offset_changed.emit(self.crop_offset_x, self.crop_offset_y)
        self.video_transform_changed.emit(self.get_current_video_transform())
        self.update()

    def set_video_scale(self, scale: float):
        """Sets zoom factor for the video frame (0.5x to 5.0x)."""
        self.video_scale = max(0.5, min(5.0, float(scale)))
        self.video_scale_changed.emit(self.video_scale)
        self.video_transform_changed.emit(self.get_current_video_transform())
        self.update()

    def toggle_flip_horizontal(self) -> bool:
        """Toggles horizontal mirror flip (ឆ្លុះឆ្វេង-ស្តាំ)."""
        self.video_flip_h = not getattr(self, "video_flip_h", False)
        self.video_transform_changed.emit(self.get_current_video_transform())
        self.update()
        return self.video_flip_h

    def toggle_flip_vertical(self) -> bool:
        """Toggles vertical flip (ឆ្លុះលើ-ក្រោម)."""
        self.video_flip_v = not getattr(self, "video_flip_v", False)
        self.video_transform_changed.emit(self.get_current_video_transform())
        self.update()
        return self.video_flip_v

    def rotate_video_90(self):
        """Rotates video frame 90 degrees clockwise."""
        self.video_rotation_angle = (getattr(self, "video_rotation_angle", 0.0) + 90.0) % 360.0
        self.video_transform_changed.emit(self.get_current_video_transform())
        self.update()

    def reset_video_transform(self):
        """Resets zoom, pan, flip, and rotation back to default 100% normal view."""
        self.video_scale = 1.0
        self.crop_offset_x = 0.0
        self.crop_offset_y = 0.0
        self.video_flip_h = False
        self.video_flip_v = False
        self.video_rotation_angle = 0.0
        self.video_scale_changed.emit(1.0)
        self.crop_offset_changed.emit(0.0, 0.0)
        self.video_transform_changed.emit(self.get_current_video_transform())
        self.update()

    def set_transform_mode(self, enabled: bool):
        """Enables or disables Transform & Pan mode (Only allows video dragging when active)."""
        self.is_transform_mode = bool(enabled)
        self.transform_mode_changed.emit(self.is_transform_mode)
        if not self.is_transform_mode and self._interaction_mode == "pan_video":
            self._interaction_mode = None
        self.setCursor(Qt.CursorShape.OpenHandCursor if self.is_transform_mode else Qt.CursorShape.ArrowCursor)
        self.update()

    def toggle_transform_mode(self) -> bool:
        """Toggles Transform & Pan mode."""
        self.set_transform_mode(not getattr(self, "is_transform_mode", False))
        return self.is_transform_mode

    def nudge_video_pan(self, dx: float, dy: float):
        """Nudges video framing offset by delta x and delta y."""
        new_ox = max(-2.0, min(2.0, round(getattr(self, "crop_offset_x", 0.0) + dx, 3)))
        new_oy = max(-2.0, min(2.0, round(getattr(self, "crop_offset_y", 0.0) + dy, 3)))
        self.set_crop_offset(new_ox, new_oy)

    def get_current_video_transform(self) -> dict:
        return {
            "scale": getattr(self, "video_scale", 1.0),
            "pos_x": getattr(self, "crop_offset_x", 0.0),
            "pos_y": getattr(self, "crop_offset_y", 0.0),
            "flip_h": getattr(self, "video_flip_h", False),
            "flip_v": getattr(self, "video_flip_v", False),
            "rotation": getattr(self, "video_rotation_angle", 0.0)
        }

    # ------------------ VIDEO KEYFRAMES ANIMATION SYSTEM ------------------
    def add_keyframe_at_current_time(self) -> dict:
        """Saves current zoom, pan, flip, and rotation as a keyframe at the playhead time."""
        t = round(float(getattr(self, "current_time", 0.0)), 3)
        curr = self.get_current_video_transform()
        existing = None
        for kf in self.video_keyframes:
            if abs(float(kf.get("time", 0.0)) - t) <= 0.05:
                existing = kf
                break

        if existing:
            existing.update(curr)
            kf_obj = existing
        else:
            kf_obj = {"time": t, **curr}
            self.video_keyframes.append(kf_obj)

        self.video_keyframes.sort(key=lambda x: float(x.get("time", 0.0)))
        self.keyframe_added.emit(kf_obj)
        self.keyframes_modified.emit(self.video_keyframes)
        self.update()
        return kf_obj

    def remove_keyframe_at_time(self, t: float, tol: float = 0.08) -> bool:
        """Removes a keyframe at or near the given timestamp."""
        orig_len = len(self.video_keyframes)
        self.video_keyframes = [k for k in self.video_keyframes if abs(float(k.get("time", 0.0)) - t) > tol]
        if len(self.video_keyframes) < orig_len:
            self.keyframe_removed.emit(t)
            self.keyframes_modified.emit(self.video_keyframes)
            self.update()
            return True
        return False

    def toggle_keyframe_at_current_time(self):
        """Toggles a keyframe at the current playhead time."""
        t = round(float(getattr(self, "current_time", 0.0)), 3)
        if self.has_keyframe_at_time(t):
            self.remove_keyframe_at_time(t)
        else:
            self.add_keyframe_at_current_time()

    def has_keyframe_at_time(self, t: float, tol: float = 0.08) -> bool:
        return any(abs(float(k.get("time", 0.0)) - t) <= tol for k in getattr(self, "video_keyframes", []))

    def get_keyframe_state_at(self, t: float) -> dict:
        """Smoothly interpolates zoom, pan, flip, and rotation between keyframes at given time."""
        kfs = getattr(self, "video_keyframes", None)
        if not kfs:
            return None
        if len(kfs) == 1:
            return kfs[0]
        if t <= float(kfs[0]["time"]):
            return kfs[0]
        if t >= float(kfs[-1]["time"]):
            return kfs[-1]

        for i in range(len(kfs) - 1):
            k1 = kfs[i]
            k2 = kfs[i + 1]
            t1 = float(k1["time"])
            t2 = float(k2["time"])
            if t1 <= t <= t2:
                dur = max(0.001, t2 - t1)
                alpha = (t - t1) / dur
                scale = float(k1.get("scale", 1.0)) + alpha * (float(k2.get("scale", 1.0)) - float(k1.get("scale", 1.0)))
                pos_x = float(k1.get("pos_x", 0.0)) + alpha * (float(k2.get("pos_x", 0.0)) - float(k1.get("pos_x", 0.0)))
                pos_y = float(k1.get("pos_y", 0.0)) + alpha * (float(k2.get("pos_y", 0.0)) - float(k1.get("pos_y", 0.0)))
                rot = float(k1.get("rotation", 0.0)) + alpha * (float(k2.get("rotation", 0.0)) - float(k1.get("rotation", 0.0)))
                return {
                    "scale": scale,
                    "pos_x": pos_x,
                    "pos_y": pos_y,
                    "flip_h": k1.get("flip_h", False) if alpha < 0.5 else k2.get("flip_h", False),
                    "flip_v": k1.get("flip_v", False) if alpha < 0.5 else k2.get("flip_v", False),
                    "rotation": rot
                }
        return kfs[-1]

    def jump_to_prev_keyframe(self) -> float:
        """Jumps playhead to previous video keyframe."""
        cur_t = float(getattr(self, "current_time", 0.0)) - 0.05
        prev_t = None
        for kf in reversed(getattr(self, "video_keyframes", [])):
            kt = float(kf.get("time", 0.0))
            if kt < cur_t:
                prev_t = kt
                break
        if prev_t is not None:
            parent_p = getattr(self, "player", None) or self.parent()
            if parent_p and hasattr(parent_p, "seek"):
                parent_p.seek(prev_t)
            return prev_t
        return None

    def jump_to_next_keyframe(self) -> float:
        """Jumps playhead to next video keyframe."""
        cur_t = float(getattr(self, "current_time", 0.0)) + 0.05
        next_t = None
        for kf in getattr(self, "video_keyframes", []):
            kt = float(kf.get("time", 0.0))
            if kt > cur_t:
                next_t = kt
                break
        if next_t is not None:
            parent_p = getattr(self, "player", None) or self.parent()
            if parent_p and hasattr(parent_p, "seek"):
                parent_p.seek(next_t)
            return next_t
        return None

    def clear_all_keyframes(self):
        """Clears all video editing keyframes."""
        self.video_keyframes.clear()
        self.keyframes_modified.emit([])
        self.update()

    def open_custom_size_dialog(self):
        """Opens dialog to configure custom width, height, and crop framing mode."""
        from ui_v_PyQt6.components.player.custom_size_dialog import CustomResolutionDialog
        cur_w, cur_h = self.get_current_canvas_resolution()
        dlg = CustomResolutionDialog(
            current_w=cur_w,
            current_h=cur_h,
            current_mode=self.video_fit_mode,
            parent=self
        )
        if dlg.exec():
            w, h, mode = dlg.get_result()
            self.set_custom_resolution(w, h, fit_mode=mode)

    def set_reframe_data(self, data: dict):
        """Sets AI facial motion trajectory and keyframes for dynamic 9:16 re-framing."""
        if not data:
            self.is_reframe_active = False
            self.reframe_trajectory = []
            self.reframe_keyframes = []
            self.update()
            return
        self.is_reframe_active = True
        self.reframe_trajectory = data.get("trajectory", [])
        self.reframe_keyframes = data.get("keyframes", [])
        self.reframe_crop_w = data.get("crop_w", 607)
        self.reframe_crop_h = data.get("crop_h", 1080)
        self.update()

    def get_reframe_crop_x_at(self, t: float):
        """Finds closest smoothed camera crop X coordinate at given timestamp."""
        if not self.reframe_trajectory:
            return None
        left = 0
        right = len(self.reframe_trajectory) - 1
        best = self.reframe_trajectory[0]
        min_diff = abs(best.get("time", 0.0) - t)
        while left <= right:
            mid = (left + right) // 2
            item = self.reframe_trajectory[mid]
            diff = abs(item.get("time", 0.0) - t)
            if diff < min_diff:
                min_diff = diff
                best = item
            if item.get("time", 0.0) < t:
                left = mid + 1
            else:
                right = mid - 1
        return best.get("crop_x", 0)

    def get_aspect_ratio_label(self) -> str:
        if self.aspect_ratio_mode == "16:9":
            return "16:9 Long Video (YouTube / Cinema)"
        elif self.aspect_ratio_mode == "9:16":
            return "9:16 Short Video (TikTok / Reels)"
        elif self.aspect_ratio_mode == "1:1":
            return "1:1 Square (Instagram / Post)"
        elif self.aspect_ratio_mode == "4:5":
            return "4:5 Portrait (Instagram Feed)"
        elif self.aspect_ratio_mode == "21:9":
            return "21:9 Cinema Scope (Ultrawide)"
        elif self.aspect_ratio_mode == "custom":
            return f"Custom ({self.custom_w}x{self.custom_h})"
        else:
            return f"Fit Video ({self.video_native_w}x{self.video_native_h})"

    def get_current_canvas_resolution(self) -> tuple:
        """Returns standard pixel dimensions (width, height) for current aspect ratio mode."""
        if self.aspect_ratio_mode == "16:9":
            return (1920, 1080) if self.video_native_w >= 1400 else (1280, 720)
        elif self.aspect_ratio_mode == "9:16":
            return (1080, 1920) if self.video_native_h >= 1400 else (720, 1280)
        elif self.aspect_ratio_mode == "1:1":
            return (1080, 1080)
        elif self.aspect_ratio_mode == "4:5":
            return (1080, 1350)
        elif self.aspect_ratio_mode == "21:9":
            return (2560, 1080)
        elif self.aspect_ratio_mode == "custom":
            return (self.custom_w, self.custom_h)
        else:
            return (self.video_native_w, self.video_native_h)

    def get_aspect_ratio_dims(self) -> tuple:
        """Returns (width, height) ratio based on current mode."""
        if self.aspect_ratio_mode == "16:9":
            return (16, 9)
        elif self.aspect_ratio_mode == "9:16":
            return (9, 16)
        elif self.aspect_ratio_mode == "1:1":
            return (1, 1)
        elif self.aspect_ratio_mode == "4:5":
            return (4, 5)
        elif self.aspect_ratio_mode == "21:9":
            return (21, 9)
        elif self.aspect_ratio_mode == "custom":
            return (max(10, self.custom_w), max(10, self.custom_h))
        else:
            return (self.video_native_w, self.video_native_h)

    def get_canvas_rect(self) -> QRectF:
        """
        Calculates the destination canvas rectangle centered inside the widget,
        accounting for chosen aspect ratio, zoom level, and symmetrical 4-corner borders.
        """
        margin = 18 if self.show_rulers else 0
        w_avail = max(10, self.width() - (margin * 2))
        h_avail = max(10, self.height() - (margin * 2))

        ar_w, ar_h = self.get_aspect_ratio_dims()
        target_ar = ar_w / max(1, ar_h)
        container_ar = w_avail / max(1, h_avail)

        if container_ar > target_ar:
            # Container is wider: height constrained
            h = h_avail * 0.95 * self.zoom_level
            w = h * target_ar
        else:
            # Container is taller: width constrained
            w = w_avail * 0.95 * self.zoom_level
            h = w / target_ar

        # Perfectly centered on all 4 sides
        cx = margin + (w_avail - w) / 2.0
        cy = margin + (h_avail - h) / 2.0
        return QRectF(cx, cy, w, h)

    def widget_to_normalized(self, pt: QPointF) -> QPointF:
        """Converts mouse coordinate in widget space to normalized (0.0 to 1.0) canvas space."""
        rect = self.get_canvas_rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return QPointF(0.5, 0.5)
        nx = (pt.x() - rect.left()) / rect.width()
        ny = (pt.y() - rect.top()) / rect.height()
        return QPointF(max(0.0, min(1.0, nx)), max(0.0, min(1.0, ny)))

    # ------------------ VIDEO FRAME INGESTION & REAL-TIME EFFECTS ------------------
    def set_frame(self, frame_bgr):
        """Sets the active video frame from OpenCV player and applies real-time effects."""
        self._current_frame_bgr = frame_bgr
        if frame_bgr is not None:
            self.video_native_h, self.video_native_w = frame_bgr.shape[:2]
        self._update_processed_frame()
        self.update()

    def set_current_time(self, t: float):
        """Updates timeline playback position (seconds) to synchronize overlays."""
        self.current_time = max(0.0, float(t))
        self.update()

    def set_duration(self, dur: float):
        """Updates total video duration."""
        self.duration = max(0.0, float(dur))

    def set_subtitle_visibility(self, visible: bool):
        """Toggles visibility of the CC subtitle layer on the video monitor."""
        self.is_subtitle_layer_visible = bool(visible)
        if self._subtitle_item is not None:
            self._subtitle_item.is_visible = bool(visible) and bool(self.active_subtitle_text)
        self.subtitle_visibility_changed.emit(self.is_subtitle_layer_visible)
        self.update()

    def set_active_subtitle(self, text: str, start_time: float = None, end_time: float = None):
        """Sets active subtitle as an interactive CanvasItem (drag, resize, rotate, and animations on monitor)."""
        self.active_subtitle_text = text or ""

        if text and getattr(self, "is_subtitle_layer_visible", True):
            if self._subtitle_item is None:
                # Create interactive CC subtitle item at bottom center (cinema convention)
                self._subtitle_item = CanvasItem(
                    item_type="subtitle",
                    x=0.5,
                    y=0.88,
                    w=0.65,
                    h=0.08,
                    z_index=9999,  # Always on top
                    name="CC Subtitle",
                    animation="karaoke"
                )
                self._subtitle_item.font_family = "Kantumruy Pro"
                self._subtitle_item.font_size = 22
                self._subtitle_item.font_color = QColor("#facc15")
                self._subtitle_item.highlight_color = QColor("#00E5FF")
                self._subtitle_item.is_bold = True
                self.items.append(self._subtitle_item)

            # Update text content and timing (position/size/rotation preserved from user drag)
            self._subtitle_item.text = text
            if start_time is not None:
                self._subtitle_item.start_time = float(start_time)
            if end_time is not None and float(end_time) > float(start_time or 0):
                self._subtitle_item.end_time = float(end_time)
            self._subtitle_item.is_visible = True
        else:
            # Hide subtitle item when no active CC text or layer hidden
            if self._subtitle_item is not None:
                self._subtitle_item.is_visible = False

        self.update()

    def set_canvas_sharpness(self, val: int):
        """Applies real unsharp masking filter to video background (0 to 100)."""
        self.canvas_sharpness = max(0, min(100, val))
        self._update_processed_frame()
        self.update()

    def set_canvas_blur(self, val: int):
        """Applies real Gaussian blur filter to video background (0 to 100)."""
        self.canvas_blur = max(0, min(100, val))
        self._update_processed_frame()
        self.update()

    def reset_effects(self):
        """Resets both canvas and selected object sharpness and blur to 0."""
        self.canvas_sharpness = 0
        self.canvas_blur = 0
        for item in self.selected_items:
            item.sharpness = 0
            item.blur = 0
            item.update_effects()
        self._update_processed_frame()
        self.update()

    def _get_face_detector(self):
        if self.face_mesh_detector is None:
            from services.video.face_tracking_service import FaceMeshDetector
            self.face_mesh_detector = FaceMeshDetector()
        return self.face_mesh_detector

    def _update_processed_frame(self):
        """Processes OpenCV frame with real sharpness, blur, and AI Auto Face Blur."""
        if self._current_frame_bgr is None:
            self._processed_frame_pixmap = None
            return

        frame = self._current_frame_bgr.copy()

        # Real-time Color Preset Filter (None, Mono, Cinematic, Bright, Film, Night Scene, Past)
        if getattr(self, "color_preset", "none") != "none":
            from ui_v_PyQt6.components.player.color_presets import apply_color_preset
            frame = apply_color_preset(frame, self.color_preset, getattr(self, "color_preset_intensity", 0.80))

        # Real-time Advanced HSL & Tone Grading
        if getattr(self, "color_hsl_settings", None):
            from ui_v_PyQt6.components.player.color_presets import apply_advanced_hsl
            frame = apply_advanced_hsl(frame, self.color_hsl_settings)

        # AI Face Mesh, Face Tracking & Auto Face Blur Engine
        needs_faces = (
            getattr(self, "auto_face_blur_enabled", False) or
            getattr(self, "face_ar_enabled", False) or
            getattr(self, "face_mesh_overlay_enabled", False)
        )
        if needs_faces:
            try:
                detector = self._get_face_detector()
                self._detected_faces = detector.detect_faces(frame)
                if getattr(self, "auto_face_blur_enabled", False) and self._detected_faces:
                    from services.video.face_tracking_service import AutoFaceBlurProcessor
                    frame = AutoFaceBlurProcessor.apply_face_blur(
                        frame,
                        self._detected_faces,
                        mode=getattr(self, "auto_face_blur_mode", "blur"),
                        strength=getattr(self, "auto_face_blur_strength", 25),
                        feather=getattr(self, "auto_face_blur_feather", True),
                        shape_type=getattr(self, "auto_face_blur_shape", "ellipse")
                    )
            except Exception as e:
                pass
        else:
            self._detected_faces = []

        # Real OpenCV Gaussian Blur (0 to 100)
        if self.canvas_blur > 0:
            k = int((self.canvas_blur / 100.0) * 20) * 2 + 1
            frame = cv2.GaussianBlur(frame, (k, k), 0)

        # Real OpenCV Unsharp Masking Sharpness (0 to 100)
        if self.canvas_sharpness > 0:
            alpha = (self.canvas_sharpness / 100.0) * 1.5
            blurred = cv2.GaussianBlur(frame, (0, 0), 3)
            frame = cv2.addWeighted(frame, 1.0 + alpha, blurred, -alpha, 0)

        # Convert to QPixmap
        h, w, ch = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self._processed_frame_pixmap = QPixmap.fromImage(qimg)

        # Ultra-fast blurred background for Fit/Blur mode
        try:
            small_w = max(16, w // 16)
            small_h = max(16, h // 16)
            small = cv2.resize(frame, (small_w, small_h), interpolation=cv2.INTER_LINEAR)
            small_blur = cv2.GaussianBlur(small, (15, 15), 0)
            small_rgb = cv2.cvtColor(small_blur, cv2.COLOR_BGR2RGB)
            qimg_blur = QImage(small_rgb.data, small_w, small_h, ch * small_w, QImage.Format.Format_RGB888)
            self._blurred_frame_pixmap = QPixmap.fromImage(qimg_blur)
        except Exception:
            self._blurred_frame_pixmap = None

    def set_color_preset(self, preset_id: str, intensity: float = 0.80):
        """Sets active color grading preset and intensity (0.0 to 1.0)."""
        self.color_preset = preset_id or "none"
        self.color_preset_intensity = float(intensity)
        self._update_processed_frame()
        self.update()

    def set_color_hsl(self, hsl_settings: dict):
        """Sets active advanced HSL color grading settings."""
        self.color_hsl_settings = hsl_settings or {}
        self._update_processed_frame()
        self.update()

    def open_color_presets_dialog(self):
        """Opens the full Color Presets & Advanced HSL suite dialog."""
        from ui_v_PyQt6.components.player.color_presets import ColorPresetsDialog
        dlg = ColorPresetsDialog(
            parent=self,
            current_preset=getattr(self, "color_preset", "none"),
            current_intensity=getattr(self, "color_preset_intensity", 0.80),
            preview_frame_bgr=self._current_frame_bgr,
            current_hsl=getattr(self, "color_hsl_settings", None)
        )
        dlg.preset_selected.connect(self.set_color_preset)
        dlg.hsl_modified.connect(self.set_color_hsl)
        if dlg.exec():
            self.set_color_preset(dlg.active_preset_id, dlg.active_intensity)
            self.set_color_hsl(dlg.hsl_settings)
        else:
            self._update_processed_frame()
            self.update()

    # ------------------ DRAG AND DROP (CANVA STYLE) ------------------
    def dragEnterEvent(self, event):
        """Accepts Video, Subtitle (CC), LUT, Sticker, Image files, and text dropped onto the monitor."""
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        """Drops Video, Sticker, LUT, Image, Subtitle (CC), or Text directly onto the canvas."""
        norm_pos = self.widget_to_normalized(event.position())
        added_any = False

        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                fpath = url.toLocalFile()
                if not fpath:
                    continue
                fpath_lower = fpath.lower()

                # 1. Video Drop (loads video in player and timeline, OR adds as Picture-in-Picture Video Overlay)
                if fpath_lower.endswith((".mp4", ".mkv", ".avi", ".mov", ".flv", ".webm", ".ts", ".wmv", ".m4v")):
                    if self._current_frame_bgr is None and getattr(self, "duration", 0.0) <= 0:
                        self.video_dropped.emit(fpath)
                    else:
                        self.add_video_item(fpath, norm_pos=norm_pos)
                    added_any = True

                # 2. Subtitle (CC) Drop (loads SRT/VTT/ASS in studio)
                elif fpath_lower.endswith((".srt", ".vtt", ".ass", ".ssa", ".sub")):
                    self.subtitle_dropped.emit(fpath)
                    added_any = True

                # 3. LUT Color Grading Drop (.cube, .3dl)
                elif fpath_lower.endswith((".cube", ".3dl")):
                    self.lut_dropped.emit(fpath)
                    added_any = True

                # 4. Image / Sticker Drop (.png, .jpg, .webp, .svg, etc.)
                elif fpath_lower.endswith((".png", ".jpg", ".jpeg", ".webp", ".svg", ".bmp", ".gif")):
                    self.save_undo_state()
                    # Classify as sticker if transparent or webp/sticker name
                    is_sticker = (
                        fpath_lower.endswith((".webp", ".png", ".svg")) and 
                        any(k in fpath_lower for k in ("sticker", "badge", "icon", "emoji", "watermark", "overlay"))
                    )
                    item_type = "sticker" if is_sticker else "image"
                    item = CanvasItem(
                        item_type=item_type,
                        x=norm_pos.x(),
                        y=norm_pos.y(),
                        w=0.25,
                        h=0.25,
                        z_index=len(self.items) + 1,
                        name=os.path.basename(fpath)
                    )
                    item.load_image(fpath)
                    self.items.append(item)
                    self.selected_items = [item]
                    self.item_added.emit(item)
                    self.item_selected.emit(item)
                    added_any = True

        elif event.mimeData().hasText():
            txt = event.mimeData().text().strip()
            if txt:
                self.save_undo_state()
                # Check if it's subtitle format with timestamps or plain text
                if "-->" in txt:
                    lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
                    dialogue_lines = [ln for ln in lines if not ln.isdigit() and "-->" not in ln]
                    cc_dialogue = " ".join(dialogue_lines) if dialogue_lines else txt
                    self.set_active_subtitle(cc_dialogue)
                    added_any = True
                else:
                    item = CanvasItem(
                        item_type="text",
                        x=norm_pos.x(),
                        y=norm_pos.y(),
                        w=0.40,
                        h=0.12,
                        z_index=len(self.items) + 1,
                        name="Text Overlay"
                    )
                    item.text = txt
                    self.items.append(item)
                    self.selected_items = [item]
                    self.item_added.emit(item)
                    self.item_selected.emit(item)
                    added_any = True

        if added_any:
            self.canvas_modified.emit()
            self.update()
            event.acceptProposedAction()

    # ------------------ ITEM MANAGEMENT & QUICK ADD ------------------
    def add_item(self, item: CanvasItem):
        """Adds a preconfigured CanvasItem to the canvas."""
        self.save_undo_state()
        if not item.z_index:
            item.z_index = len(self.items) + 1
        self.items.append(item)
        self.selected_items = [item]
        self.item_added.emit(item)
        self.item_selected.emit(item)
        self.canvas_modified.emit()
        self.update()

    def add_text_item(self, text: str = "Add Heading", norm_pos: QPointF = None):
        """Adds a Canva-style typography heading text overlay."""
        self.save_undo_state()
        pos = norm_pos if norm_pos else QPointF(0.5, 0.5)
        cur_t = getattr(self, "current_time", 0.0)
        dur = getattr(self, "duration", 0.0)
        end_t = min(dur, cur_t + 5.0) if dur > cur_t + 1.0 else cur_t + 5.0
        item = CanvasItem(
            item_type="text",
            x=pos.x(),
            y=pos.y(),
            w=0.45,
            h=0.12,
            z_index=len(self.items) + 1,
            name="Heading Text",
            start_time=cur_t,
            end_time=end_t
        )
        item.text = text
        item.font_size = 32
        self.items.append(item)
        self.selected_items = [item]
        self.item_added.emit(item)
        self.item_selected.emit(item)
        self.canvas_modified.emit()
        self.update()
        return item

    def add_shape_item(self, shape_type: str = "rect", fill_color: str = "#0ea5e9", norm_pos: QPointF = None):
        """Adds a Canva vector shape (rectangle, rounded rectangle, circle, star, badge)."""
        self.save_undo_state()
        pos = norm_pos if norm_pos else QPointF(0.5, 0.5)
        cur_t = getattr(self, "current_time", 0.0)
        dur = getattr(self, "duration", 0.0)
        end_t = min(dur, cur_t + 5.0) if dur > cur_t + 1.0 else cur_t + 5.0
        is_line = shape_type in ("line", "arrow", "double_arrow")
        shape_count = sum(1 for it in self.items if getattr(it, "item_type", "") == "shape") + 1
        if is_line:
            label_map = {"line": "Straight Line", "arrow": "Arrow", "double_arrow": "Double Arrow"}
            default_name = f"{label_map.get(shape_type, 'Line')} {shape_count}"
            item_w = 0.35
            item_h = 0.04
        else:
            default_name = f"Rectangle {shape_count}" if shape_type in ("rect", "rounded_rect") else f"{shape_type.title()} {shape_count}"
            item_w = 0.30
            item_h = 0.20 if shape_type != "badge" else 0.12

        item = CanvasItem(
            item_type="shape",
            x=pos.x(),
            y=pos.y(),
            w=item_w,
            h=item_h,
            z_index=len(self.items) + 1,
            name=default_name,
            start_time=cur_t,
            end_time=end_t
        )
        item.shape_type = shape_type
        if is_line:
            item.fill_color = QColor(0, 0, 0, 0)
            item.border_color = QColor(fill_color if fill_color else "#38bdf8")
            item.border_width = 4
            item.stroke_style = "solid"
            item.arrowhead_size = 16.0
        else:
            item.fill_color = QColor(fill_color)
            item.border_color = QColor("#ffffff")
            item.border_width = 0
            item.stroke_style = "none"
        item.corner_radius = 0.0
        item.radius_tl = 0.0
        item.radius_tr = 0.0
        item.radius_bl = 0.0
        item.radius_br = 0.0
        self.items.append(item)
        self.selected_items = [item]
        self.item_added.emit(item)
        self.item_selected.emit(item)
        self.canvas_modified.emit()
        self.update()
        return item

    def add_image_item(self, file_path: str, norm_pos: QPointF = None):
        """Adds an image or sticker overlay."""
        self.save_undo_state()
        pos = norm_pos if norm_pos else QPointF(0.5, 0.5)
        cur_t = getattr(self, "current_time", 0.0)
        dur = getattr(self, "duration", 0.0)
        end_t = min(dur, cur_t + 5.0) if dur > cur_t + 1.0 else cur_t + 5.0
        item = CanvasItem(
            item_type="image",
            x=pos.x(),
            y=pos.y(),
            w=0.28,
            h=0.28,
            z_index=len(self.items) + 1,
            name=os.path.basename(file_path),
            start_time=cur_t,
            end_time=end_t
        )
        item.load_image(file_path)
        self.items.append(item)
        self.selected_items = [item]
        self.item_added.emit(item)
        self.item_selected.emit(item)
        self.canvas_modified.emit()
        self.update()
        return item

    def add_video_item(self, file_path: str, norm_pos: QPointF = None):
        """Adds a Picture-in-Picture (PiP) video overlay clip."""
        self.save_undo_state()
        pos = norm_pos if norm_pos else QPointF(0.5, 0.5)
        cur_t = getattr(self, "current_time", 0.0)
        dur = getattr(self, "duration", 0.0)
        end_t = min(dur, cur_t + 5.0) if dur > cur_t + 1.0 else cur_t + 5.0
        item = CanvasItem(
            item_type="video",
            x=pos.x(),
            y=pos.y(),
            w=0.32,
            h=0.20,
            z_index=len(self.items) + 1,
            name=f"Video ({os.path.basename(file_path)})",
            video_path=file_path,
            start_time=cur_t,
            end_time=end_t
        )
        self.items.append(item)
        self.selected_items = [item]
        self.item_added.emit(item)
        self.item_selected.emit(item)
        self.canvas_modified.emit()
        self.update()
        return item

    def _prompt_add_image(self, norm_pos: QPointF = None):
        """Opens file dialog to choose and insert image/logo overlay."""
        f, _ = QFileDialog.getOpenFileName(
            self, "Select Overlay Image / Logo / Watermark", "",
            "Images (*.png *.jpg *.jpeg *.webp *.svg *.bmp *.gif)"
        )
        if f:
            self.add_image_item(f, norm_pos=norm_pos)

    def _prompt_add_video(self, norm_pos: QPointF = None):
        """Opens file dialog to choose and insert video overlay clip."""
        f, _ = QFileDialog.getOpenFileName(
            self, "Select Video Overlay Clip (PiP)", "",
            "Videos (*.mp4 *.mkv *.avi *.mov *.flv *.wmv *.webm *.ts)"
        )
        if f:
            self.add_video_item(f, norm_pos=norm_pos)

    def add_blur_box_item(self, norm_pos: QPointF = None, blur_mode: str = "blur"):
        """Adds an interactive blur / censor box that blurs video underneath it."""
        self.save_undo_state()
        pos = norm_pos if norm_pos else QPointF(0.5, 0.5)
        cur_t = getattr(self, "current_time", 0.0)
        dur = getattr(self, "duration", 0.0)
        end_t = min(dur, cur_t + 5.0) if dur > cur_t + 1.0 else cur_t + 5.0
        item = CanvasItem(
            item_type="blur_box",
            x=pos.x(),
            y=pos.y(),
            w=0.25,
            h=0.15,
            z_index=len(self.items) + 1,
            name="Frosted Glass Box" if blur_mode == "glass" else ("Blackout Bar" if blur_mode == "blackout" else ("Mosaic Censor Box" if blur_mode == "mosaic" else "Blur Censor Box")),
            blur_mode=blur_mode,
            blur_strength=30,
            corner_radius=12 if blur_mode == "glass" else 0,
            start_time=cur_t,
            end_time=end_t
        )
        self.items.append(item)
        self.selected_items = [item]
        self.item_added.emit(item)
        self.item_selected.emit(item)
        self.canvas_modified.emit()
        self.update()
        return item

    def add_glass_box_item(self, norm_pos: QPointF = None):
        """Adds a Canva-style frosted glassmorphism box overlay."""
        return self.add_blur_box_item(norm_pos=norm_pos, blur_mode="glass")

    def open_blur_style_dialog(self, item: CanvasItem = None):
        """Opens live Frosted Glass, Blur, Opacity, and Corner Radius customizer dialog."""
        target = item
        if not target and self.selected_items:
            target = self.selected_items[0]
        if not target:
            return
        from ui_v_PyQt6.components.player.blur_style_dialog import BlurBoxStyleDialog
        dlg = BlurBoxStyleDialog(target, self, self)
        dlg.exec()

    def _set_blur_preset(self, item: CanvasItem, mode: str):
        self.save_undo_state()
        item.blur_mode = mode
        if mode == "glass":
            item.name = "Frosted Glass Box"
            if getattr(item, "corner_radius", 0) == 0:
                item.corner_radius = 12
        elif mode == "mosaic":
            item.name = "Mosaic Censor Box"
        elif mode == "blackout":
            item.name = "Blackout Bar"
        else:
            item.name = "Blur Censor Box"
        self.canvas_modified.emit()
        self.update()

    def _set_item_opacity(self, item: CanvasItem, percent: int):
        self.save_undo_state()
        item.opacity = round(percent / 100.0, 2)
        self.canvas_modified.emit()
        self.update()

    def _toggle_blur_mode(self, item: CanvasItem):
        self.save_undo_state()
        item.blur_mode = "mosaic" if item.blur_mode == "blur" else "blur"
        item.name = "Mosaic Censor Box" if item.blur_mode == "mosaic" else "Blur Censor Box"
        self.canvas_modified.emit()
        self.update()

    def _adjust_blur_strength(self, item: CanvasItem, delta: int):
        self.save_undo_state()
        item.blur_strength = max(5, min(100, item.blur_strength + delta))
        self.canvas_modified.emit()
        self.update()

    def get_subtitles_list(self) -> list:
        """Retrieves active subtitles list from player/timeline context."""
        if hasattr(self, "subtitles") and isinstance(self.subtitles, list) and self.subtitles:
            return self.subtitles
        p = self.parent()
        if p:
            te = getattr(p, "timeline_editor", None)
            if te and hasattr(te, "canvas") and getattr(te.canvas, "subtitles", None):
                return te.canvas.subtitles
            # Walk up parent hierarchy
            curr = p
            while curr:
                if hasattr(curr, "subtitles") and isinstance(curr.subtitles, list):
                    return curr.subtitles
                curr = curr.parent()
        return []

    def snap_selected_to_subtitle(self, sub: dict = None):
        """Snaps selected overlay item(s) to match active or specified subtitle line timing."""
        if not self.selected_items:
            return
        subs = self.get_subtitles_list()
        cur_t = getattr(self, "current_time", 0.0)
        target_sub = sub
        if not target_sub and subs:
            for s in subs:
                if float(s.get("start", 0.0)) <= cur_t <= float(s.get("end", 0.0)):
                    target_sub = s
                    break
            if not target_sub:
                target_sub = min(subs, key=lambda s: abs(float(s.get("start", 0.0)) - cur_t))

        if target_sub:
            self.save_undo_state()
            st = float(target_sub.get("start", 0.0))
            et = float(target_sub.get("end", 0.0))
            for it in self.selected_items:
                it.start_time = round(st, 3)
                it.end_time = round(et, 3)
            self.canvas_modified.emit()
            self.update()

    def snap_selected_to_all_subtitles(self):
        """Stretches selected overlay to span the entire movie subtitles range (first to last line)."""
        subs = self.get_subtitles_list()
        if not subs or not self.selected_items:
            return
        self.save_undo_state()
        st = float(subs[0].get("start", 0.0))
        et = float(subs[-1].get("end", 0.0))
        for it in self.selected_items:
            it.start_time = round(st, 3)
            it.end_time = round(et, 3)
        self.canvas_modified.emit()
        self.update()

    def replicate_selected_for_all_subtitles(self):
        """
        Creates synchronized duplicate blur/censor boxes for EVERY subtitle line in the movie.
        Perfect for censoring hardcoded foreign dialogue (Chinese/English) throughout the entire movie!
        """
        subs = self.get_subtitles_list()
        if not subs or not self.selected_items:
            return
        template_item = self.selected_items[0]
        self.save_undo_state()
        created_items = []
        for idx, s in enumerate(subs):
            st = float(s.get("start", 0.0))
            et = float(s.get("end", 0.0))
            new_it = CanvasItem(
                item_type=template_item.item_type,
                x=template_item.x,
                y=template_item.y,
                w=template_item.w,
                h=template_item.h,
                rotation=template_item.rotation,
                opacity=template_item.opacity,
                z_index=len(self.items) + len(created_items) + 1,
                name=f"{template_item.name} #{idx+1}",
                blur_mode=getattr(template_item, "blur_mode", "blur"),
                blur_strength=getattr(template_item, "blur_strength", 25),
                corner_radius=getattr(template_item, "corner_radius", 0),
                start_time=round(st, 3),
                end_time=round(et, 3)
            )
            if hasattr(template_item, "glass_tint_color"):
                new_it.glass_tint_color = template_item.glass_tint_color
            if hasattr(template_item, "image_path") and template_item.image_path:
                new_it.image_path = template_item.image_path
                new_it._raw_image = template_item._raw_image
                new_it._processed_pixmap = template_item._processed_pixmap
            created_items.append(new_it)

        if template_item in self.items:
            self.items.remove(template_item)
        self.items.extend(created_items)
        self.selected_items = created_items[:1]
        self.canvas_modified.emit()
        self.update()

    def delete_selected(self):
        """Deletes all currently selected items."""
        if not self.selected_items:
            return
        self.save_undo_state()
        for it in self.selected_items:
            if not it.is_locked:
                if it in self.items:
                    self.items.remove(it)
                self.item_deleted.emit(it)
        self.selected_items = []
        self.item_selected.emit(None)
        self.canvas_modified.emit()
        self.update()

    def duplicate_selected(self):
        """Duplicates selected items with Canva-style slight offset."""
        if not self.selected_items:
            return
        self.save_undo_state()
        new_selection = []
        for it in self.selected_items:
            cloned = it.clone()
            self.items.append(cloned)
            self.item_added.emit(cloned)
            new_selection.append(cloned)
        self.selected_items = new_selection
        self.item_selected.emit(new_selection[0] if new_selection else None)
        self.canvas_modified.emit()
        self.update()

    def toggle_lock_selected(self):
        for it in self.selected_items:
            it.is_locked = not it.is_locked
        self.canvas_modified.emit()
        self.update()

    def bring_forward(self):
        if not self.selected_items:
            return
        self.save_undo_state()
        for it in self.selected_items:
            idx = self.items.index(it)
            if idx < len(self.items) - 1:
                self.items[idx], self.items[idx + 1] = self.items[idx + 1], self.items[idx]
        self.canvas_modified.emit()
        self.update()

    def send_backward(self):
        if not self.selected_items:
            return
        self.save_undo_state()
        for it in self.selected_items:
            idx = self.items.index(it)
            if idx > 0:
                self.items[idx], self.items[idx - 1] = self.items[idx - 1], self.items[idx]
        self.canvas_modified.emit()
        self.update()

    def bring_to_front(self):
        if not self.selected_items:
            return
        self.save_undo_state()
        for it in self.selected_items:
            self.items.remove(it)
            self.items.append(it)
        self.canvas_modified.emit()
        self.update()

    def send_to_back(self):
        if not self.selected_items:
            return
        self.save_undo_state()
        for it in reversed(self.selected_items):
            self.items.remove(it)
            self.items.insert(0, it)
        self.canvas_modified.emit()
        self.update()

    # ------------------ UNDO / REDO HISTORY STACK ------------------
    def save_undo_state(self):
        """Snapshots all item properties for instant Ctrl+Z undo."""
        snapshot = []
        for it in self.items:
            snapshot.append({
                "item_type": it.item_type,
                "x": it.x, "y": it.y, "w": it.w, "h": it.h,
                "rotation": it.rotation, "opacity": it.opacity,
                "is_locked": it.is_locked, "name": it.name,
                "sharpness": it.sharpness, "blur": it.blur,
                "image_path": it.image_path, "text": it.text,
                "font_family": it.font_family, "font_size": it.font_size,
                "font_color": it.font_color.name(),
                "shape_type": it.shape_type,
                "fill_color": it.fill_color.name(),
                "border_color": it.border_color.name(),
                "border_width": it.border_width
            })
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > 40:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def undo(self):
        if not self._undo_stack:
            return
        # Save current to redo
        self._redo_stack.append(self._capture_current_snapshot())
        snapshot = self._undo_stack.pop()
        self._restore_from_snapshot(snapshot)

    def redo(self):
        if not self._redo_stack:
            return
        self._undo_stack.append(self._capture_current_snapshot())
        snapshot = self._redo_stack.pop()
        self._restore_from_snapshot(snapshot)

    def _capture_current_snapshot(self):
        return [
            {
                "item_type": it.item_type, "x": it.x, "y": it.y, "w": it.w, "h": it.h,
                "rotation": it.rotation, "opacity": it.opacity, "is_locked": it.is_locked,
                "name": it.name, "sharpness": it.sharpness, "blur": it.blur,
                "image_path": it.image_path, "text": it.text, "font_family": it.font_family,
                "font_size": it.font_size, "font_color": it.font_color.name(),
                "shape_type": it.shape_type, "fill_color": it.fill_color.name(),
                "border_color": it.border_color.name(), "border_width": it.border_width
            }
            for it in self.items
        ]

    def _restore_from_snapshot(self, snapshot):
        self.items = []
        for d in snapshot:
            it = CanvasItem(item_type=d["item_type"], x=d["x"], y=d["y"], w=d["w"], h=d["h"], rotation=d["rotation"], opacity=d["opacity"], name=d["name"])
            it.is_locked = d["is_locked"]
            it.sharpness = d["sharpness"]
            it.blur = d["blur"]
            if d.get("image_path") and os.path.exists(d["image_path"]):
                it.load_image(d["image_path"])
            it.text = d.get("text", "")
            it.font_family = d.get("font_family", "Kantumruy Pro")
            it.font_size = d.get("font_size", 28)
            it.font_color = QColor(d.get("font_color", "#ffffff"))
            it.shape_type = d.get("shape_type", "rect")
            it.fill_color = QColor(d.get("fill_color", "#0ea5e9"))
            it.border_color = QColor(d.get("border_color", "#38bdf8"))
            it.border_width = d.get("border_width", 3)
            it.update_effects()
            self.items.append(it)
        self.selected_items = []
        self.canvas_modified.emit()
        self.update()

    # ------------------ SHORTCUTS ------------------
    def _setup_shortcuts(self):
        QShortcut(QKeySequence.StandardKey.Delete, self).activated.connect(self.delete_selected)
        QShortcut(QKeySequence(Qt.Key.Key_Backspace), self).activated.connect(self.delete_selected)
        QShortcut(QKeySequence.StandardKey.Undo, self).activated.connect(self.undo)
        QShortcut(QKeySequence.StandardKey.Redo, self).activated.connect(self.redo)
        QShortcut(QKeySequence.StandardKey.Copy, self).activated.connect(self._copy_selected)
        QShortcut(QKeySequence.StandardKey.Paste, self).activated.connect(self._paste_selected)
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(self.duplicate_selected)
        QShortcut(QKeySequence("Ctrl+;"), self).activated.connect(self.toggle_guides)
        # Arrow keys nudging (scoped to WidgetShortcut so it never blocks video seeking shortcuts)
        sc_l = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        sc_l.setContext(Qt.ShortcutContext.WidgetShortcut)
        sc_l.activated.connect(lambda: self._nudge(-0.003, 0))

        sc_r = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        sc_r.setContext(Qt.ShortcutContext.WidgetShortcut)
        sc_r.activated.connect(lambda: self._nudge(0.003, 0))

        sc_u = QShortcut(QKeySequence(Qt.Key.Key_Up), self)
        sc_u.setContext(Qt.ShortcutContext.WidgetShortcut)
        sc_u.activated.connect(lambda: self._nudge(0, -0.003))

        sc_d = QShortcut(QKeySequence(Qt.Key.Key_Down), self)
        sc_d.setContext(Qt.ShortcutContext.WidgetShortcut)
        sc_d.activated.connect(lambda: self._nudge(0, 0.003))

    def _nudge(self, dx: float, dy: float):
        if not self.selected_items:
            # If no canvas item is selected, forward Arrow Left / Arrow Right to video player seeking!
            parent_p = getattr(self, "player", None) or self.parent()
            if parent_p and hasattr(parent_p, "_seek_relative"):
                delta = 2.0 if dx > 0 else (-2.0 if dx < 0 else 0.0)
                if delta != 0.0:
                    parent_p._seek_relative(delta)
            return
        self.save_undo_state()
        for it in self.selected_items:
            if not it.is_locked:
                it.x = max(0.02, min(0.98, it.x + dx))
                it.y = max(0.02, min(0.98, it.y + dy))
        self.canvas_modified.emit()
        self.update()

    def _copy_selected(self):
        if self.selected_items:
            self.clipboard_item = self.selected_items[0].clone()

    def _paste_selected(self):
        if self.clipboard_item:
            self.save_undo_state()
            p = self.clipboard_item.clone()
            self.items.append(p)
            self.selected_items = [p]
            self.item_added.emit(p)
            self.item_selected.emit(p)
            self.canvas_modified.emit()
            self.update()

    # ------------------ MOUSE INTERACTION & HIT TESTING ------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pt = event.position()
            rect = self.get_canvas_rect()
            w, h = rect.width(), rect.height()
            r_sz = 18 if self.show_rulers else 0

            # 0A. Check if clicking on Rulers to drag a NEW Guide (Photoshop Rulers Drag)
            if self.show_rulers and not self.guides_locked:
                if pt.y() <= r_sz or pt.y() >= self.height() - r_sz:
                    self._interaction_mode = "drag_new_guide_h"
                    self._drag_guide_current_pos = pt
                    self.setCursor(Qt.CursorShape.SplitVCursor)
                    self.update()
                    return
                elif pt.x() <= r_sz or pt.x() >= self.width() - r_sz:
                    self._interaction_mode = "drag_new_guide_v"
                    self._drag_guide_current_pos = pt
                    self.setCursor(Qt.CursorShape.SplitHCursor)
                    self.update()
                    return

            # 0B. Check if clicking on an EXISTING Guide Line to move or remove
            hit_guide = self._find_guide_at(pt)
            if hit_guide:
                self.save_undo_state()
                self._interaction_mode = "drag_existing_guide"
                self._active_guide = hit_guide
                self._drag_guide_current_pos = pt
                self.setCursor(Qt.CursorShape.SplitVCursor if hit_guide[0] == "h" else Qt.CursorShape.SplitHCursor)
                self.update()
                return

            # 1. Check if clicking on resize/rotate handle of selected item
            if len(self.selected_items) == 1:
                item = self.selected_items[0]
                h_name = item.get_handle_at(pt - rect.topLeft(), w, h)
                if h_name:
                    self.save_undo_state()
                    self._interaction_mode = "rotate" if h_name == "rotate" else "resize"
                    self._active_handle = h_name
                    self._drag_start_pos = pt
                    self._capture_initial_states()
                    return

            # 2. Check if clicking on an item
            hit_item = None
            cur_t = getattr(self, "current_time", 0.0)
            dur = getattr(self, "duration", 0.0)
            sub_item = getattr(self, "_subtitle_item", None)
            for it in reversed(self.items):
                if it is sub_item or it.is_active_at(cur_t, dur):
                    if it.contains_point(pt - rect.topLeft(), w, h):
                        hit_item = it
                        break

            if hit_item:
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    # Multi-select toggle
                    if hit_item in self.selected_items:
                        self.selected_items.remove(hit_item)
                    else:
                        self.selected_items.append(hit_item)
                else:
                    if hit_item not in self.selected_items:
                        self.selected_items = [hit_item]

                self.save_undo_state()
                self._interaction_mode = "move"
                self._drag_start_pos = pt
                self._capture_initial_states()
                self.item_selected.emit(hit_item)

            else:
                # Clicked video frame background!
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    # Shift-drag = marquee selection
                    self._interaction_mode = "marquee"
                    self._drag_start_pos = pt
                    self._marquee_rect = QRectF(pt, pt)
                elif getattr(self, "is_transform_mode", False):
                    # Direct interactive Pan & Crop video framing ONLY when in Transform tool mode!
                    self.selected_items = []
                    self.item_selected.emit(None)
                    self._interaction_mode = "pan_video"
                    self._drag_start_pos = pt
                    self._initial_crop_ox = getattr(self, "crop_offset_x", 0.0)
                    self._initial_crop_oy = getattr(self, "crop_offset_y", 0.0)
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)
                else:
                    # Normal mode: Deselect all items, do NOT pan or drag video background!
                    self.selected_items = []
                    self.item_selected.emit(None)
                    self._interaction_mode = None
                    self.setCursor(Qt.CursorShape.ArrowCursor)

            self.update()

        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.position())

    def mouseMoveEvent(self, event):
        pt = event.position()
        rect = self.get_canvas_rect()
        w, h = rect.width(), rect.height()

        if self._interaction_mode in ("drag_new_guide_h", "drag_new_guide_v", "drag_existing_guide"):
            self._drag_guide_current_pos = pt
            if self._interaction_mode == "drag_existing_guide" and self._active_guide:
                g_type, g_idx = self._active_guide
                if g_type == "h":
                    norm_y = max(0.0, min(1.0, (pt.y() - rect.top()) / max(1.0, h)))
                    self.guides_h[g_idx] = round(norm_y, 4)
                else:
                    norm_x = max(0.0, min(1.0, (pt.x() - rect.left()) / max(1.0, w)))
                    self.guides_v[g_idx] = round(norm_x, 4)
            self.update()
            return

        if self._interaction_mode == "pan_video":
            # Smooth video pan offset (left/right, up/down)
            dx = pt.x() - self._drag_start_pos.x()
            dy = pt.y() - self._drag_start_pos.y()
            sens_x = max(40.0, w * 0.45)
            sens_y = max(40.0, h * 0.45)
            new_ox = max(-2.0, min(2.0, self._initial_crop_ox + (dx / sens_x)))
            new_oy = max(-2.0, min(2.0, self._initial_crop_oy + (dy / sens_y)))
            self.crop_offset_x = round(new_ox, 3)
            self.crop_offset_y = round(new_oy, 3)
            self.crop_offset_changed.emit(self.crop_offset_x, self.crop_offset_y)
            self.video_transform_changed.emit(self.get_current_video_transform())
            self.update()

        elif self._interaction_mode == "move":
            dx = (pt.x() - self._drag_start_pos.x()) / max(1, w)
            dy = (pt.y() - self._drag_start_pos.y()) / max(1, h)
            self._snap_lines_h.clear()
            self._snap_lines_v.clear()

            for it in self.selected_items:
                if it.is_locked:
                    continue
                init = self._item_initial_states.get(it.id, {})
                new_x = init.get("x", it.x) + dx
                new_y = init.get("y", it.y) + dy

                # Magnetic Snapping Guides
                if self.enable_snapping and len(self.selected_items) == 1:
                    # Snap Center Horizontal (x = 0.5)
                    if abs(new_x - 0.5) < 0.015:
                        new_x = 0.5
                        self._snap_lines_v.append(rect.left() + rect.width() * 0.5)
                    # Snap Center Vertical (y = 0.5)
                    if abs(new_y - 0.5) < 0.015:
                        new_y = 0.5
                        self._snap_lines_h.append(rect.top() + rect.height() * 0.5)
                    # Snap Safe Margins (5%, 95%)
                    if abs(new_x - 0.05) < 0.012:
                        new_x = 0.05
                        self._snap_lines_v.append(rect.left() + rect.width() * 0.05)
                    if abs(new_x - 0.95) < 0.012:
                        new_x = 0.95
                        self._snap_lines_v.append(rect.left() + rect.width() * 0.95)

                    # Snap to Persistent User Guides (self.guides_v & self.guides_h)
                    if self.show_guides:
                        half_w = it.w / 2.0
                        half_h = it.h / 2.0
                        for gv in self.guides_v:
                            if abs(new_x - gv) < 0.012:
                                new_x = gv
                                self._snap_lines_v.append(rect.left() + rect.width() * gv)
                                break
                            elif abs((new_x - half_w) - gv) < 0.012:
                                new_x = gv + half_w
                                self._snap_lines_v.append(rect.left() + rect.width() * gv)
                                break
                            elif abs((new_x + half_w) - gv) < 0.012:
                                new_x = gv - half_w
                                self._snap_lines_v.append(rect.left() + rect.width() * gv)
                                break

                        for gh in self.guides_h:
                            if abs(new_y - gh) < 0.012:
                                new_y = gh
                                self._snap_lines_h.append(rect.top() + rect.height() * gh)
                                break
                            elif abs((new_y - half_h) - gh) < 0.012:
                                new_y = gh + half_h
                                self._snap_lines_h.append(rect.top() + rect.height() * gh)
                                break
                            elif abs((new_y + half_h) - gh) < 0.012:
                                new_y = gh - half_h
                                self._snap_lines_h.append(rect.top() + rect.height() * gh)
                                break

                it.x = max(0.01, min(0.99, new_x))
                it.y = max(0.01, min(0.99, new_y))

            self.update()

        elif self._interaction_mode == "rotate" and len(self.selected_items) == 1:
            item = self.selected_items[0]
            cx = rect.left() + item.x * w
            cy = rect.top() + item.y * h
            angle_rad = math.atan2(pt.y() - cy, pt.x() - cx)
            angle_deg = math.degrees(angle_rad) + 90.0

            # Snap to 0, 45, 90, 180, 270 degrees
            for snap_deg in [0, 45, 90, 135, 180, 225, 270, 315, 360]:
                if abs(angle_deg - snap_deg) < 4.0:
                    angle_deg = snap_deg
                    break

            item.rotation = round(angle_deg % 360.0, 1)
            QToolTip.showText(QCursor.pos(), f"{int(item.rotation)}°")
            self.update()

        elif self._interaction_mode == "resize" and len(self.selected_items) == 1:
            item = self.selected_items[0]
            init = self._item_initial_states.get(item.id, {})
            dx = (pt.x() - self._drag_start_pos.x()) / max(1, w)
            dy = (pt.y() - self._drag_start_pos.y()) / max(1, h)

            # Proportional or directional resizing based on handle
            h_name = self._active_handle
            iw, ih = init["w"], init["h"]
            aspect = iw / max(0.01, ih)

            if "right" in h_name:
                item.w = max(0.04, iw + dx)
            elif "left" in h_name:
                item.w = max(0.04, iw - dx)

            if "bottom" in h_name:
                item.h = max(0.04, ih + dy)
            elif "top" in h_name:
                item.h = max(0.04, ih - dy)

            # Proportional corner scaling
            if h_name in ("top_left", "top_right", "bottom_left", "bottom_right"):
                item.h = item.w / aspect

            self.update()

        elif self._interaction_mode == "marquee":
            self._marquee_rect = QRectF(self._drag_start_pos, pt).normalized()
            # Select all items intersecting marquee box
            self.selected_items = []
            for it in self.items:
                it_rect = it.get_pixel_rect(w, h).translated(rect.topLeft())
                if self._marquee_rect.intersects(it_rect):
                    self.selected_items.append(it)
            self.update()

        else:
            # Hover cursor update
            self._update_hover_cursor(pt)

    def mouseReleaseEvent(self, event):
        if self._interaction_mode in ("drag_new_guide_h", "drag_new_guide_v", "drag_existing_guide"):
            pt = event.position()
            rect = self.get_canvas_rect()
            r_sz = 18 if self.show_rulers else 0
            is_in_ruler = (pt.x() <= r_sz or pt.x() >= self.width() - r_sz or
                           pt.y() <= r_sz or pt.y() >= self.height() - r_sz)

            if self._interaction_mode == "drag_new_guide_h":
                if not is_in_ruler and rect.top() <= pt.y() <= rect.bottom():
                    norm_y = max(0.0, min(1.0, (pt.y() - rect.top()) / max(1.0, rect.height())))
                    self.save_undo_state()
                    self.guides_h.append(round(norm_y, 4))
                    self.guides_h.sort()
            elif self._interaction_mode == "drag_new_guide_v":
                if not is_in_ruler and rect.left() <= pt.x() <= rect.right():
                    norm_x = max(0.0, min(1.0, (pt.x() - rect.left()) / max(1.0, rect.width())))
                    self.save_undo_state()
                    self.guides_v.append(round(norm_x, 4))
                    self.guides_v.sort()
            elif self._interaction_mode == "drag_existing_guide" and self._active_guide:
                g_type, g_idx = self._active_guide
                if is_in_ruler:
                    if g_type == "h" and 0 <= g_idx < len(self.guides_h):
                        self.guides_h.pop(g_idx)
                    elif g_type == "v" and 0 <= g_idx < len(self.guides_v):
                        self.guides_v.pop(g_idx)
                else:
                    if g_type == "h":
                        self.guides_h.sort()
                    else:
                        self.guides_v.sort()

            self._interaction_mode = None
            self._active_guide = None
            self._drag_guide_current_pos = None
            self._update_hover_cursor(event.position())
            self.update()
            return

        if self._interaction_mode in ("move", "resize", "rotate"):
            self.canvas_modified.emit()
        elif self._interaction_mode == "pan_video":
            # If a keyframe exists near current playhead time, auto-sync its position!
            cur_t = round(float(getattr(self, "current_time", 0.0)), 3)
            for kf in getattr(self, "video_keyframes", []):
                if abs(float(kf.get("time", 0.0)) - cur_t) <= 0.08:
                    kf["pos_x"] = self.crop_offset_x
                    kf["pos_y"] = self.crop_offset_y
                    self.keyframes_modified.emit(self.video_keyframes)
                    break

        self._interaction_mode = None
        self._active_handle = None
        self._marquee_rect = None
        self._snap_lines_h.clear()
        self._snap_lines_v.clear()
        self._update_hover_cursor(event.position())
        self.update()

    def wheelEvent(self, event):
        """Scroll wheel zooms video frame scale in/out when in Transform mode or Ctrl is held."""
        if getattr(self, "is_transform_mode", False) or (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            delta = event.angleDelta().y()
            if delta != 0:
                factor = 1.08 if delta > 0 else 0.92
                cur_scale = getattr(self, "video_scale", 1.0)
                new_scale = max(0.5, min(5.0, round(cur_scale * factor, 3)))
                self.set_video_scale(new_scale)
                # If keyframe at playhead, sync scale
                cur_t = round(float(getattr(self, "current_time", 0.0)), 3)
                for kf in getattr(self, "video_keyframes", []):
                    if abs(float(kf.get("time", 0.0)) - cur_t) <= 0.08:
                        kf["scale"] = new_scale
                        self.keyframes_modified.emit(self.video_keyframes)
                        break
                event.accept()
                return
        super().wheelEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Double clicking on text allows inline editing; on blur/glass box opens style customizer."""
        if len(self.selected_items) == 1:
            item = self.selected_items[0]
            if item.item_type == "text":
                new_text, ok = QInputDialog.getText(self, "Edit Text", "Enter typography text:", text=item.text)
                if ok and new_text:
                    self.save_undo_state()
                    item.text = new_text
                    self.canvas_modified.emit()
                    self.update()
            elif item.item_type in ("blur_box", "blur", "mosaic", "glass", "blackout"):
                self.open_blur_style_dialog(item)

    def _capture_initial_states(self):
        self._item_initial_states = {}
        for it in self.selected_items:
            self._item_initial_states[it.id] = {
                "x": it.x, "y": it.y, "w": it.w, "h": it.h, "rotation": it.rotation
            }

    def _update_hover_cursor(self, pt: QPointF):
        rect = self.get_canvas_rect()
        w, h = rect.width(), rect.height()

        # Check if hovering over guide lines
        hit_g = self._find_guide_at(pt)
        if hit_g:
            if self._hover_guide != hit_g:
                self._hover_guide = hit_g
                self.update()
            self.setCursor(Qt.CursorShape.SplitVCursor if hit_g[0] == "h" else Qt.CursorShape.SplitHCursor)
            return
        else:
            if self._hover_guide is not None:
                self._hover_guide = None
                self.update()

        # Check if hovering over ruler area
        r_sz = 18 if self.show_rulers else 0
        if self.show_rulers and not self.guides_locked:
            if (pt.y() <= r_sz or pt.y() >= self.height() - r_sz or
                pt.x() <= r_sz or pt.x() >= self.width() - r_sz):
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                return

        if len(self.selected_items) == 1:
            h_name = self.selected_items[0].get_handle_at(pt - rect.topLeft(), w, h)
            if h_name:
                if h_name == "rotate":
                    self.setCursor(Qt.CursorShape.PointingHandCursor)
                elif h_name in ("top_left", "bottom_right"):
                    self.setCursor(Qt.CursorShape.SizeFDiagCursor)
                elif h_name in ("top_right", "bottom_left"):
                    self.setCursor(Qt.CursorShape.SizeBDiagCursor)
                elif h_name in ("left_mid", "right_mid"):
                    self.setCursor(Qt.CursorShape.SizeHorCursor)
                elif h_name in ("top_mid", "bottom_mid"):
                    self.setCursor(Qt.CursorShape.SizeVerCursor)
                return

        for it in reversed(self.items):
            if it.contains_point(pt - rect.topLeft(), w, h):
                self.setCursor(Qt.CursorShape.SizeAllCursor if not it.is_locked else Qt.CursorShape.ForbiddenCursor)
                return

        # Over canvas monitor empty area:
        if rect.contains(pt):
            if getattr(self, "is_transform_mode", False):
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    # ------------------ CONTEXT MENU & FLOATING CONTROLS ------------------
    def _show_context_menu(self, pos: QPointF):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e2430;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item:selected {
                background-color: #0284c7;
            }
        """)

        norm_pos = self.widget_to_normalized(pos)

        if self.selected_items:
            it = self.selected_items[0]
            act_dup = menu.addAction("📋 Duplicate (Ctrl+D)")
            act_dup.triggered.connect(self.duplicate_selected)

            act_del = menu.addAction("🗑️ Delete (Del)")
            act_del.triggered.connect(self.delete_selected)

            # Special controls if Blur / Mosaic / Glass / Blackout box is selected
            if it.item_type in ("blur_box", "blur", "mosaic", "glass", "blackout"):
                menu.addSeparator()
                act_custom_style = menu.addAction("🎨 Customize Style & Frosted Glass (កែសម្រួល Style & Opacity)...")
                act_custom_style.triggered.connect(lambda: self.open_blur_style_dialog(it))

                m_preset = menu.addMenu("✨ Quick Preset Style")
                m_preset.addAction("✨ Frosted Glass (កញ្ចក់ព្រិល Glassmorphism)").triggered.connect(lambda: self._set_blur_preset(it, "glass"))
                m_preset.addAction("🌫️ Smooth Blur (ព្រិលធម្មតា)").triggered.connect(lambda: self._set_blur_preset(it, "blur"))
                m_preset.addAction("🔲 Mosaic / Pixelate (ក្រឡាការ៉ូ Censor)").triggered.connect(lambda: self._set_blur_preset(it, "mosaic"))
                m_preset.addAction("⬛ Blackout Bar (បន្ទះខ្មៅបិទបាំង)").triggered.connect(lambda: self._set_blur_preset(it, "blackout"))

                m_op = menu.addMenu("💧 Opacity (កម្រិតថ្លា/ស្រអាប់)")
                for op_val in [100, 85, 70, 50, 30]:
                    m_op.addAction(f"{op_val}%").triggered.connect(lambda checked=False, v=op_val: self._set_item_opacity(it, v))

            menu.addSeparator()
            m_srt = menu.addMenu("⏱️ កំណត់ម៉ោងតាម Subtitle / SRT (Sync Time with SRT)")
            m_srt.addAction("🎯 ដាក់ម៉ោងតាម Subtitle បច្ចុប្បន្ន (Snap to Current Subtitle Line)").triggered.connect(lambda: self.snap_selected_to_subtitle())
            m_srt.addAction("🎬 ពង្រីកគ្របដណ្ដប់ Subtitles ទាំងអស់ (Cover Entire Subtitles Range)").triggered.connect(self.snap_selected_to_all_subtitles)
            m_srt.addAction("✨ បង្កើត Blur Box ស្វ័យប្រវត្តិតាមគ្រប់បន្ទាត់ SRT (Replicate for Every Subtitle Line)").triggered.connect(self.replicate_selected_for_all_subtitles)

            menu.addSeparator()
            act_front = menu.addAction("⏫ Bring to Front")
            act_front.triggered.connect(self.bring_to_front)
            act_back = menu.addAction("⏬ Send to Back")
            act_back.triggered.connect(self.send_to_back)

            menu.addSeparator()
            act_lock = menu.addAction("🔓 Unlock" if it.is_locked else "🔒 Lock")
            act_lock.triggered.connect(self.toggle_lock_selected)

            menu.addSeparator()
            m_add = menu.addMenu("➕ Add More Objects")
            m_add.addAction("✨ Frosted Glass Box (ប្រអប់កញ្ចក់ព្រិល)").triggered.connect(lambda: self.add_glass_box_item(norm_pos))
            m_add.addAction("🌫️ Blur Box (ប្រអប់ព្រិលបិទបាំង)").triggered.connect(lambda: self.add_blur_box_item(norm_pos, "blur"))
            m_add.addAction("🔲 Mosaic Box (ប្រអប់ក្រឡាបិទបាំង)").triggered.connect(lambda: self.add_blur_box_item(norm_pos, "mosaic"))
            m_add.addAction("⬛ Blackout Bar (បន្ទះខ្មៅបិទបាំង)").triggered.connect(lambda: self.add_blur_box_item(norm_pos, "blackout"))
            m_add.addAction("🖼️ Add Image / Logo (បញ្ចូលរូបភាព/ឡូហ្គោ)...").triggered.connect(lambda: self._prompt_add_image(norm_pos))
            m_add.addAction("🎬 Add Video Overlay (បញ្ចូលវីដេអូបន្ថែម)...").triggered.connect(lambda: self._prompt_add_video(norm_pos))
            m_add.addAction("📝 Heading Text").triggered.connect(lambda: self.add_text_item("New Heading", norm_pos))
            m_add.addAction("🟦 Rectangle Shape").triggered.connect(lambda: self.add_shape_item("rounded_rect", norm_pos=norm_pos))

        else:
            # Video Frame Controls & Keyframes
            m_video = menu.addMenu("🎬 Video Framing, Crop & Zoom (កែទម្រង់ និងពង្រីក)")
            act_tf = m_video.addAction("✥ Transform Mode (Drag to Pan ↔ ↕)")
            act_tf.setCheckable(True)
            act_tf.setChecked(getattr(self, "is_transform_mode", False))
            act_tf.triggered.connect(self.toggle_transform_mode)
            m_video.addSeparator()
            act_fit = m_video.addAction("📐 Fit Video (Blurred Backdrop)" if getattr(self, "video_fit_mode", "fill") == "fill" else "✂️ Fill Video (Center Crop)")
            act_fit.triggered.connect(lambda: self.set_video_fit_mode("fit" if getattr(self, "video_fit_mode", "fill") == "fill" else "fill"))
            m_video.addAction("↔️ Flip Horizontal (ឆ្លុះឆ្វេង-ស្តាំ)").triggered.connect(self.toggle_flip_horizontal)
            m_video.addAction("↕️ Flip Vertical (ឆ្លុះលើ-ក្រោម)").triggered.connect(self.toggle_flip_vertical)
            m_video.addAction("🔄 Rotate 90° (បង្វិល 90 ដឺក្រេ)").triggered.connect(self.rotate_video_90)
            m_video.addAction("🎯 Reset Video Transform (កំណត់ទំហំដើម 100%)").triggered.connect(self.reset_video_transform)
            m_video.addSeparator()
            m_zoom = m_video.addMenu("🔍 Zoom Level")
            for z_val in [1.0, 1.25, 1.5, 2.0, 3.0]:
                m_zoom.addAction(f"{int(z_val*100)}%").triggered.connect(lambda ch=False, s=z_val: self.set_video_scale(s))

            m_kf = menu.addMenu("◆ Video Keyframes (គន្លឹះចលនា Video)")
            m_kf.addAction("◆+ Add / Update Keyframe at Playhead").triggered.connect(self.add_keyframe_at_current_time)
            m_kf.addAction("◀◆ Jump to Previous Keyframe").triggered.connect(self.jump_to_prev_keyframe)
            m_kf.addAction("◆▶ Jump to Next Keyframe").triggered.connect(self.jump_to_next_keyframe)
            m_kf.addAction("🗑️ Clear All Keyframes").triggered.connect(self.clear_all_keyframes)

            menu.addSeparator()
            act_glass = menu.addAction("✨ Add Frosted Glass Box (ប្រអប់កញ្ចក់ព្រិលទំនើប)")
            act_glass.triggered.connect(lambda: self.add_glass_box_item(norm_pos))

            act_blur = menu.addAction("🌫️ Add Blur Box (ប្រអប់ព្រិលបិទបាំងវីដេអូ)")
            act_blur.triggered.connect(lambda: self.add_blur_box_item(norm_pos, "blur"))

            act_mosaic = menu.addAction("🔲 Add Mosaic Box (ប្រអប់បិទបាំងបែបក្រឡា / Censor)")
            act_mosaic.triggered.connect(lambda: self.add_blur_box_item(norm_pos, "mosaic"))

            act_blackout = menu.addAction("⬛ Add Blackout Bar (បន្ទះខ្មៅបិទបាំង Subtitle)")
            act_blackout.triggered.connect(lambda: self.add_blur_box_item(norm_pos, "blackout"))

            menu.addSeparator()
            act_img = menu.addAction("🖼️ Add Image / Logo (បញ្ចូលរូបភាព/ឡូហ្គោ)...")
            act_img.triggered.connect(lambda: self._prompt_add_image(norm_pos))

            act_vid = menu.addAction("🎬 Add Video Overlay / PiP (បញ្ចូលវីដេអូបន្ថែម)...")
            act_vid.triggered.connect(lambda: self._prompt_add_video(norm_pos))

            menu.addSeparator()
            act_txt = menu.addAction("➕ Add Heading Text")
            act_txt.triggered.connect(lambda: self.add_text_item("New Heading", norm_pos))
            act_rect = menu.addAction("🟦 Add Rectangle")
            act_rect.triggered.connect(lambda: self.add_shape_item("rounded_rect", norm_pos=norm_pos))
            act_star = menu.addAction("⭐ Add Star Badge")
            act_star.triggered.connect(lambda: self.add_shape_item("star", "#f59e0b", norm_pos=norm_pos))
            menu.addSeparator()
            act_grid = menu.addAction("Toggle Grid Overlay")
            act_grid.triggered.connect(self.toggle_grid)
            act_rulers = menu.addAction("Toggle 4-Corner Guides")
            act_rulers.triggered.connect(self.toggle_rulers)

        # --- Photoshop CC Guides System ---
        menu.addSeparator()
        act_new_guide = menu.addAction("New Guide...")
        act_new_guide.triggered.connect(self.open_new_guide_dialog)

        act_guide_layout = menu.addAction("New Guide Layout...")
        act_guide_layout.triggered.connect(self.open_new_guide_layout_dialog)

        act_guide_shape = menu.addAction("New Guides From Shape")
        has_shape = len(self.selected_items) > 0
        act_guide_shape.setEnabled(has_shape)
        if has_shape:
            act_guide_shape.triggered.connect(self.create_guides_from_selected_shape)

        menu.addSeparator()
        act_lock_guides = menu.addAction("Lock Guides (ចាក់សោរបន្ទាត់ Guide)")
        act_lock_guides.setCheckable(True)
        act_lock_guides.setChecked(self.guides_locked)
        act_lock_guides.triggered.connect(self.toggle_lock_guides)

        act_clear_guides = menu.addAction("Clear Guides (លុបបន្ទាត់ Guide ទាំងអស់)")
        act_clear_guides.triggered.connect(self.clear_guides)

        act_show_guides = menu.addAction("Show Guides (Ctrl+;)")
        act_show_guides.setCheckable(True)
        act_show_guides.setChecked(self.show_guides)
        act_show_guides.triggered.connect(self.toggle_guides)

        menu.exec(QCursor.pos())

    # ------------------ DRAG & DROP INGESTION ------------------
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def toggle_grid(self):
        self.show_grid = not self.show_grid
        self.update()

    def toggle_rulers(self):
        self.show_rulers = not self.show_rulers
        self.update()

    # ------------------ PAINTING & RENDERING ------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # 1. Dark Studio Workspace Backdrop
        painter.fillRect(self.rect(), QColor("#0b0f17"))

        # 2. Get Canvas Geometry
        canvas_rect = self.get_canvas_rect()
        cw, ch = canvas_rect.width(), canvas_rect.height()

        # Canvas Drop Shadow
        shadow_rect = canvas_rect.adjusted(-2, -2, 4, 4)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 160))
        painter.drawRoundedRect(shadow_rect, 4, 4)

        # 3. Render Video Frame Background (or Cinema Pattern if no video)
        painter.save()
        painter.setClipRect(canvas_rect)

        if self._processed_frame_pixmap and not self._processed_frame_pixmap.isNull():
            cur_t = getattr(self, "current_time", 0.0)
            fit_mode = getattr(self, "video_fit_mode", "fill")
            off_x = getattr(self, "crop_offset_x", 0.0)
            off_y = getattr(self, "crop_offset_y", 0.0)
            v_scale = getattr(self, "video_scale", 1.0)
            flip_h = getattr(self, "video_flip_h", False)
            flip_v = getattr(self, "video_flip_v", False)
            rot_deg = getattr(self, "video_rotation_angle", 0.0)

            # 1. Dynamic Keyframe Animation Interpolation
            kf_state = self.get_keyframe_state_at(cur_t)
            if kf_state:
                v_scale = float(kf_state.get("scale", v_scale))
                off_x = float(kf_state.get("pos_x", off_x))
                off_y = float(kf_state.get("pos_y", off_y))
                if "flip_h" in kf_state:
                    flip_h = bool(kf_state["flip_h"])
                if "flip_v" in kf_state:
                    flip_v = bool(kf_state["flip_v"])
                if "rotation" in kf_state:
                    rot_deg = float(kf_state["rotation"])

            # 2. AI Dynamic Face & Speaker Tracking Offset (Auto Reframe)
            if getattr(self, "is_reframe_active", False) and getattr(self, "reframe_trajectory", None):
                cx = self.get_reframe_crop_x_at(cur_t)
                crop_w = int(self._processed_frame_pixmap.height() * (9.0 / 16.0))
                max_cx = max(1, self._processed_frame_pixmap.width() - crop_w)
                if cx is not None and max_cx > 0:
                    off_x = max(-1.0, min(1.0, (cx - (max_cx / 2.0)) / (max_cx / 2.0)))

            # 3. Transform frame pixmap for horizontal/vertical flip & rotation
            frame_pm = self._processed_frame_pixmap
            if flip_h or flip_v or rot_deg != 0:
                tr = QTransform()
                if flip_h:
                    tr.scale(-1, 1)
                if flip_v:
                    tr.scale(1, -1)
                if rot_deg != 0:
                    tr.rotate(rot_deg)
                frame_pm = frame_pm.transformed(tr, Qt.TransformationMode.SmoothTransformation)

            pw = frame_pm.width()
            ph = frame_pm.height()

            if fit_mode == "fill":
                # Center-Crop / Fill mode (Undistorted full screen, perfect for TikTok 9:16)
                base_scale = max(cw / max(1, pw), ch / max(1, ph))
                dw = pw * base_scale * max(0.5, v_scale)
                dh = ph * base_scale * max(0.5, v_scale)
                extra_x = max(20.0, (dw - cw) / 2.0 + (dw * 0.15))
                extra_y = max(20.0, (dh - ch) / 2.0 + (dh * 0.15))
                dx = (cw - dw) / 2.0 + (off_x * extra_x)
                dy = (ch - dh) / 2.0 + (off_y * extra_y)
                painter.fillRect(canvas_rect, QColor("#090c10"))
                target_draw_rect = QRectF(canvas_rect.left() + dx, canvas_rect.top() + dy, dw, dh)
                painter.drawPixmap(target_draw_rect.toRect(), frame_pm)

            elif fit_mode == "fit":
                # Letterbox / Pillarbox with Blurred Video Background (CapCut / Reels style)
                if self._blurred_frame_pixmap and not self._blurred_frame_pixmap.isNull():
                    painter.drawPixmap(canvas_rect.toRect(), self._blurred_frame_pixmap)
                else:
                    painter.drawPixmap(canvas_rect.toRect(), frame_pm)
                # 45% dark scrim over blurred backdrop for contrast
                painter.fillRect(canvas_rect, QColor(0, 0, 0, 115))

                base_scale = min(cw / max(1, pw), ch / max(1, ph))
                dw = pw * base_scale * max(0.5, v_scale)
                dh = ph * base_scale * max(0.5, v_scale)
                extra_x = max(20.0, abs(dw - cw) / 2.0 + (dw * 0.25))
                extra_y = max(20.0, abs(dh - ch) / 2.0 + (dh * 0.25))
                dx = (cw - dw) / 2.0 + (off_x * extra_x)
                dy = (ch - dh) / 2.0 + (off_y * extra_y)
                target_draw_rect = QRectF(canvas_rect.left() + dx, canvas_rect.top() + dy, dw, dh)
                painter.drawPixmap(target_draw_rect.toRect(), frame_pm)

            else:  # "black"
                painter.fillRect(canvas_rect, QColor("#000000"))
                base_scale = min(cw / max(1, pw), ch / max(1, ph))
                dw = pw * base_scale * max(0.5, v_scale)
                dh = ph * base_scale * max(0.5, v_scale)
                extra_x = max(20.0, abs(dw - cw) / 2.0 + (dw * 0.25))
                extra_y = max(20.0, abs(dh - ch) / 2.0 + (dh * 0.25))
                dx = (cw - dw) / 2.0 + (off_x * extra_x)
                dy = (ch - dh) / 2.0 + (off_y * extra_y)
                target_draw_rect = QRectF(canvas_rect.left() + dx, canvas_rect.top() + dy, dw, dh)
                painter.drawPixmap(target_draw_rect.toRect(), frame_pm)
        else:
            # Elegant Cinema Backdrop
            painter.fillRect(canvas_rect, QColor("#111827"))
            painter.setPen(QColor("#374151"))
            painter.setFont(QFont("Kantumruy Pro", 14, QFont.Weight.Bold))
            painter.drawText(canvas_rect, Qt.AlignmentFlag.AlignCenter, "🎬 Drag Video / Media Here\n(Canva Preview Canvas)")

        # 4. Optional Design Grid Overlay
        if self.show_grid:
            self._render_grid(painter, canvas_rect)

        # 5. Render All Canvas Items
        painter.translate(canvas_rect.topLeft())
        cur_t = getattr(self, "current_time", 0.0)
        dur = getattr(self, "duration", 0.0)
        sub_item = getattr(self, "_subtitle_item", None)
        is_playing = bool(getattr(self.parent(), "is_playing", False))
        for it in sorted(self.items, key=lambda x: x.z_index):
            # CC Subtitle has its own state; overlay items ONLY render when current time is within start_time -> end_time
            if it is sub_item:
                it.render(
                    painter, cw, ch,
                    is_selected=(it in self.selected_items and not is_playing),
                    bg_pixmap=self._processed_frame_pixmap,
                    current_time=cur_t
                )
            elif it.is_active_at(cur_t, dur):
                it.render(
                    painter, cw, ch,
                    is_selected=(it in self.selected_items and not is_playing),
                    bg_pixmap=self._processed_frame_pixmap,
                    current_time=cur_t
                )

        painter.restore()

        # 5c. AI AR Accessories (Sticker Follow Face) & Face Mesh Wireframe
        if getattr(self, "face_ar_enabled", False) and getattr(self, "_detected_faces", None):
            from services.video.face_tracking_service import FaceARPropsEngine
            FaceARPropsEngine.draw_ar_props_on_painter(
                painter,
                canvas_rect,
                self._detected_faces,
                prop_type=getattr(self, "face_ar_prop", "glasses"),
                custom_pixmap=getattr(self, "face_ar_custom_pixmap", None),
                anchor=getattr(self, "face_ar_anchor", "eyes"),
                scale_factor=getattr(self, "face_ar_scale", 1.0),
                offset_y=getattr(self, "face_ar_offset_y", 0.0)
            )

        if getattr(self, "face_mesh_overlay_enabled", False) and getattr(self, "_detected_faces", None):
            from services.video.face_tracking_service import FaceARPropsEngine
            FaceARPropsEngine.draw_face_mesh_wireframe(painter, canvas_rect, self._detected_faces)

        # 6. Canvas Outer Border (Matte Black / Accent) only when paused/editing
        if not is_playing:
            painter.setPen(QPen(QColor("#38bdf8"), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(canvas_rect)

        # 7. Snapping Guide Lines (Magenta / Cyan)
        self._render_snap_guides(painter)

        # 8. Marquee Selection Box
        if self._marquee_rect:
            painter.setPen(QPen(QColor("#0ea5e9"), 1, Qt.PenStyle.DashLine))
            painter.setBrush(QBrush(QColor(14, 165, 233, 40)))
            painter.drawRect(self._marquee_rect)

        # 8b. Photoshop CC User Guides (Cyan #00e5ff) & Dragging Overlay
        if self.show_guides:
            self._render_user_guides(painter, canvas_rect)

        # 9. Optional Rulers on top & left
        if self.show_rulers:
            self._render_rulers(painter, canvas_rect)

        # 10. Transform Mode Active Overlay & Badge
    def render_clean_canvas(self) -> QPixmap:
        """
        Renders a 100% clean, pristine cinematic frame of the canvas:
        - Exact resolution of the canvas (without outer workspace padding)
        - Video frame + aspect ratio crop or blur backdrop
        - Subtitles, stickers, text, images, and blur boxes WITHOUT selection borders or handles
        - NO outer blue borders, NO workspace padding, NO snapping lines
        Perfect for Fullscreen Monitor, snapshots, and 100% WYSIWYG export parity.
        """
        canvas_rect = self.get_canvas_rect()
        cw = max(10, int(canvas_rect.width()))
        ch = max(10, int(canvas_rect.height()))

        pix = QPixmap(cw, ch)
        pix.fill(QColor("#000000"))

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        draw_rect = QRectF(0, 0, cw, ch)

        # 1. Render Video Frame
        if self._processed_frame_pixmap and not self._processed_frame_pixmap.isNull():
            fit_mode = getattr(self, "video_fit_mode", "fill")
            off_x = getattr(self, "crop_offset_x", 0.0)
            off_y = getattr(self, "crop_offset_y", 0.0)
            v_scale = getattr(self, "video_scale", 1.0)
            flip_h = getattr(self, "video_flip_h", False)
            flip_v = getattr(self, "video_flip_v", False)
            rot_deg = getattr(self, "video_rotation_angle", 0.0)

            frame_pm = self._processed_frame_pixmap
            if flip_h or flip_v or rot_deg != 0:
                tr = QTransform()
                if flip_h:
                    tr.scale(-1, 1)
                if flip_v:
                    tr.scale(1, -1)
                if rot_deg != 0:
                    tr.rotate(rot_deg)
                frame_pm = frame_pm.transformed(tr, Qt.TransformationMode.SmoothTransformation)

            pw = frame_pm.width()
            ph = frame_pm.height()

            if fit_mode == "fill":
                base_scale = max(cw / max(1, pw), ch / max(1, ph))
                dw = pw * base_scale * max(0.5, v_scale)
                dh = ph * base_scale * max(0.5, v_scale)
                extra_x = max(20.0, (dw - cw) / 2.0 + (dw * 0.15))
                extra_y = max(20.0, (dh - ch) / 2.0 + (dh * 0.15))
                dx = (cw - dw) / 2.0 + (off_x * extra_x)
                dy = (ch - dh) / 2.0 + (off_y * extra_y)
                painter.fillRect(draw_rect, QColor("#090c10"))
                target_draw_rect = QRectF(dx, dy, dw, dh)
                painter.drawPixmap(target_draw_rect.toRect(), frame_pm)

            elif fit_mode == "fit":
                if self._blurred_frame_pixmap and not self._blurred_frame_pixmap.isNull():
                    painter.drawPixmap(draw_rect.toRect(), self._blurred_frame_pixmap)
                else:
                    painter.drawPixmap(draw_rect.toRect(), frame_pm)
                painter.fillRect(draw_rect, QColor(0, 0, 0, 115))

                base_scale = min(cw / max(1, pw), ch / max(1, ph))
                dw = pw * base_scale * max(0.5, v_scale)
                dh = ph * base_scale * max(0.5, v_scale)
                extra_x = max(20.0, abs(dw - cw) / 2.0 + (dw * 0.25))
                extra_y = max(20.0, abs(dh - ch) / 2.0 + (dh * 0.25))
                dx = (cw - dw) / 2.0 + (off_x * extra_x)
                dy = (ch - dh) / 2.0 + (off_y * extra_y)
                target_draw_rect = QRectF(dx, dy, dw, dh)
                painter.drawPixmap(target_draw_rect.toRect(), frame_pm)
            else:
                painter.fillRect(draw_rect, QColor("#000000"))
                base_scale = min(cw / max(1, pw), ch / max(1, ph))
                dw = pw * base_scale * max(0.5, v_scale)
                dh = ph * base_scale * max(0.5, v_scale)
                extra_x = max(20.0, abs(dw - cw) / 2.0 + (dw * 0.25))
                extra_y = max(20.0, abs(dh - ch) / 2.0 + (dh * 0.25))
                dx = (cw - dw) / 2.0 + (off_x * extra_x)
                dy = (ch - dh) / 2.0 + (off_y * extra_y)
                target_draw_rect = QRectF(dx, dy, dw, dh)
                painter.drawPixmap(target_draw_rect.toRect(), frame_pm)
        else:
            painter.fillRect(draw_rect, QColor("#000000"))

        # 2. Render All Active Canvas Items Cleanly (is_selected=False -> NO handles or borders)
        cur_t = getattr(self, "current_time", 0.0)
        dur = getattr(self, "duration", 0.0)
        sub_item = getattr(self, "_subtitle_item", None)
        for it in sorted(self.items, key=lambda x: x.z_index):
            if it is sub_item:
                it.render(
                    painter, cw, ch,
                    is_selected=False,
                    bg_pixmap=self._processed_frame_pixmap,
                    current_time=cur_t
                )
            elif it.is_active_at(cur_t, dur):
                it.render(
                    painter, cw, ch,
                    is_selected=False,
                    bg_pixmap=self._processed_frame_pixmap,
                    current_time=cur_t
                )

        # 3. Render AI AR Accessories & Face Mesh Wireframe Cleanly
        if getattr(self, "face_ar_enabled", False) and getattr(self, "_detected_faces", None):
            from services.video.face_tracking_service import FaceARPropsEngine
            FaceARPropsEngine.draw_ar_props_on_painter(
                painter,
                draw_rect,
                self._detected_faces,
                prop_type=getattr(self, "face_ar_prop", "glasses"),
                custom_pixmap=getattr(self, "face_ar_custom_pixmap", None),
                anchor=getattr(self, "face_ar_anchor", "eyes"),
                scale_factor=getattr(self, "face_ar_scale", 1.0),
                offset_y=getattr(self, "face_ar_offset_y", 0.0)
            )

        if getattr(self, "face_mesh_overlay_enabled", False) and getattr(self, "_detected_faces", None):
            from services.video.face_tracking_service import FaceARPropsEngine
            FaceARPropsEngine.draw_face_mesh_wireframe(painter, draw_rect, self._detected_faces)

        painter.end()
        return pix

    def _render_transform_overlay(self, painter: QPainter, canvas_rect: QRectF):
        """Draws subtle glowing border and top badge when Transform Tool is active."""
        # 1. Subtle cyan/sky transformation outline around canvas
        pen = QPen(QColor("#0284c7"), 2.0, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(canvas_rect)

        # 2. Sleek dark pill badge at top center
        badge_text = "✥ Transform Mode Active  •  Drag to Pan ↔ ↕  |  Wheel to Zoom"
        badge_font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        painter.setFont(badge_font)
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(badge_text)
        th = fm.height()

        bw = tw + 24
        bh = th + 10
        bx = canvas_rect.center().x() - (bw / 2.0)
        by = canvas_rect.top() + 12

        badge_rect = QRectF(bx, by, bw, bh)
        painter.setPen(QPen(QColor("#38bdf8"), 1.2))
        painter.setBrush(QColor(15, 23, 42, 230))
        painter.drawRoundedRect(badge_rect, 6, 6)

        painter.setPen(QColor("#e0f2fe"))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

    def _render_grid(self, painter: QPainter, canvas_rect: QRectF):
        """Draws subtle designer grid overlay."""
        painter.setPen(QPen(QColor(255, 255, 255, 25), 1, Qt.PenStyle.DotLine))
        step = 40.0 * self.zoom_level
        x = canvas_rect.left() + step
        while x < canvas_rect.right():
            painter.drawLine(QPointF(x, canvas_rect.top()), QPointF(x, canvas_rect.bottom()))
            x += step
        y = canvas_rect.top() + step
        while y < canvas_rect.bottom():
            painter.drawLine(QPointF(canvas_rect.left(), y), QPointF(canvas_rect.right(), y))
            y += step

    def _render_snap_guides(self, painter: QPainter):
        """Draws magnetic snapping guidelines across canvas."""
        pen = QPen(QColor("#06b6d4"), 1.5, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        for vx in self._snap_lines_v:
            painter.drawLine(QPointF(vx, 0), QPointF(vx, self.height()))
        for hy in self._snap_lines_h:
            painter.drawLine(QPointF(0, hy), QPointF(self.width(), hy))

    # ------------------ PHOTOSHOP CC GUIDES & RULERS ENGINE ------------------
    def _find_guide_at(self, pt: QPointF, tolerance: float = 6.0):
        """Returns ('h', index) or ('v', index) or None if mouse is near a guide line."""
        if not self.show_guides or self.guides_locked:
            return None
        rect = self.get_canvas_rect()
        cl, ct = rect.left(), rect.top()
        cw, ch = rect.width(), rect.height()

        # Check Horizontal Guides
        for i, gy_norm in enumerate(self.guides_h):
            py = ct + gy_norm * ch
            if abs(pt.y() - py) <= tolerance:
                return ("h", i)

        # Check Vertical Guides
        for i, gx_norm in enumerate(self.guides_v):
            px = cl + gx_norm * cw
            if abs(pt.x() - px) <= tolerance:
                return ("v", i)

        return None

    def _draw_guide_badge(self, painter: QPainter, pos: QPointF, text: str):
        """Draws a floating dark pill badge showing the guide's pixel coordinate."""
        painter.save()
        font = QFont("Consolas", 8, QFont.Weight.Bold)
        painter.setFont(font)
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(text) + 12
        th = 18
        bg_rect = QRectF(pos.x(), pos.y() - th / 2.0, tw, th)

        painter.setPen(QPen(QColor("#00e5ff"), 1))
        painter.setBrush(QBrush(QColor(15, 23, 42, 230)))
        painter.drawRoundedRect(bg_rect, 4, 4)

        painter.setPen(QColor("#ffffff"))
        painter.drawText(bg_rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

    def _render_user_guides(self, painter: QPainter, canvas_rect: QRectF):
        """Draws Photoshop-standard cyan (#00e5ff) persistent guides and drag indicators."""
        if not canvas_rect or canvas_rect.width() < 10:
            return

        cl, ct = canvas_rect.left(), canvas_rect.top()
        cw, ch = canvas_rect.width(), canvas_rect.height()
        r_sz = 18 if self.show_rulers else 0
        W, H = self.width(), self.height()

        pen_guide = QPen(QColor("#00e5ff"), 1, Qt.PenStyle.SolidLine)
        pen_hover = QPen(QColor("#ffffff"), 1.5, Qt.PenStyle.SolidLine)

        # 1. Horizontal Guides
        for i, gy_norm in enumerate(self.guides_h):
            py = ct + gy_norm * ch
            is_active = (self._active_guide == ("h", i)) or (self._hover_guide == ("h", i))
            painter.setPen(pen_hover if is_active else pen_guide)
            painter.drawLine(QPointF(0, py), QPointF(W, py))

            if is_active:
                v_h = getattr(self, "video_native_h", 1080)
                px_val = int(gy_norm * v_h)
                badge_txt = f"Y: {px_val}px ({gy_norm*100:.1f}%)"
                self._draw_guide_badge(painter, QPointF(r_sz + 12, py), badge_txt)

        # 2. Vertical Guides
        for i, gx_norm in enumerate(self.guides_v):
            px = cl + gx_norm * cw
            is_active = (self._active_guide == ("v", i)) or (self._hover_guide == ("v", i))
            painter.setPen(pen_hover if is_active else pen_guide)
            painter.drawLine(QPointF(px, 0), QPointF(px, H))

            if is_active:
                v_w = getattr(self, "video_native_w", 1920)
                px_val = int(gx_norm * v_w)
                badge_txt = f"X: {px_val}px ({gx_norm*100:.1f}%)"
                self._draw_guide_badge(painter, QPointF(px + 4, r_sz + 22), badge_txt)

        # 3. Guide Being Dragged from Ruler (Live Ghost)
        if self._interaction_mode in ("drag_new_guide_h", "drag_new_guide_v") and self._drag_guide_current_pos:
            pt = self._drag_guide_current_pos
            painter.setPen(QPen(QColor("#00e5ff"), 1.5, Qt.PenStyle.DashLine))
            if self._interaction_mode == "drag_new_guide_h":
                painter.drawLine(QPointF(0, pt.y()), QPointF(W, pt.y()))
                norm_y = max(0.0, min(1.0, (pt.y() - ct) / max(1.0, ch)))
                v_h = getattr(self, "video_native_h", 1080)
                px_val = int(norm_y * v_h)
                self._draw_guide_badge(painter, QPointF(r_sz + 14, pt.y()), f"Y: {px_val}px")
            else:
                painter.drawLine(QPointF(pt.x(), 0), QPointF(pt.x(), H))
                norm_x = max(0.0, min(1.0, (pt.x() - cl) / max(1.0, cw)))
                v_w = getattr(self, "video_native_w", 1920)
                px_val = int(norm_x * v_w)
                self._draw_guide_badge(painter, QPointF(pt.x() + 4, r_sz + 22), f"X: {px_val}px")

    def open_new_guide_dialog(self):
        """Opens Photoshop CC 'New Guide...' dialog."""
        dlg = NewGuideDialog(self, video_w=self.video_native_w, video_h=self.video_native_h)
        if dlg.exec():
            orient, norm_pos = dlg.get_guide_data()
            self.save_undo_state()
            if orient == "h":
                self.guides_h.append(round(norm_pos, 4))
                self.guides_h.sort()
            else:
                self.guides_v.append(round(norm_pos, 4))
                self.guides_v.sort()
            self.show_guides = True
            self.update()

    def open_new_guide_layout_dialog(self):
        """Opens Photoshop CC 'New Guide Layout...' dialog."""
        dlg = NewGuideLayoutDialog(self, video_w=self.video_native_w, video_h=self.video_native_h)
        if dlg.exec():
            h_guides, v_guides, clear_existing = dlg.get_generated_guides()
            self.save_undo_state()
            if clear_existing:
                self.guides_h.clear()
                self.guides_v.clear()
            self.guides_h = sorted(list(set(self.guides_h + h_guides)))
            self.guides_v = sorted(list(set(self.guides_v + v_guides)))
            self.show_guides = True
            self.update()

    def create_guides_from_selected_shape(self):
        """Creates 4 bounding guides around selected item + horizontal & vertical centers."""
        if not self.selected_items:
            return
        it = self.selected_items[0]
        self.save_undo_state()
        half_w = it.w / 2.0
        half_h = it.h / 2.0
        top = max(0.0, min(1.0, it.y - half_h))
        bot = max(0.0, min(1.0, it.y + half_h))
        left = max(0.0, min(1.0, it.x - half_w))
        right = max(0.0, min(1.0, it.x + half_w))

        for gy in [top, it.y, bot]:
            r_y = round(gy, 4)
            if r_y not in self.guides_h:
                self.guides_h.append(r_y)
        self.guides_h.sort()

        for gx in [left, it.x, right]:
            r_x = round(gx, 4)
            if r_x not in self.guides_v:
                self.guides_v.append(r_x)
        self.guides_v.sort()

        self.show_guides = True
        self.update()

    def toggle_guides(self):
        """Toggles guide visibility (Ctrl+;)."""
        self.show_guides = not self.show_guides
        self.update()

    def toggle_lock_guides(self):
        """Toggles guide locking to prevent accidental moving."""
        self.guides_locked = not self.guides_locked
        self.update()

    def clear_guides(self):
        """Clears all user guidelines."""
        self.save_undo_state()
        self.guides_h.clear()
        self.guides_v.clear()
        self.update()

    def _render_rulers(self, painter: QPainter, canvas_rect: QRectF):
        """Draws full 4-corner symmetrical pixel rulers & cinema guides (Top, Bottom, Left, Right)."""
        W, H = self.width(), self.height()
        r_sz = 18

        # 1. Background Bars on all 4 sides
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#111620"))
        painter.drawRect(0, 0, W, r_sz)                  # Top
        painter.drawRect(0, H - r_sz, W, r_sz)          # Bottom
        painter.drawRect(0, 0, r_sz, H)                  # Left
        painter.drawRect(W - r_sz, 0, r_sz, H)          # Right

        # 2. All 4 Corner Accent Boxes (៤ជ្រុង)
        painter.setBrush(QColor("#18212f"))
        painter.drawRect(0, 0, r_sz, r_sz)              # Top-Left
        painter.drawRect(W - r_sz, 0, r_sz, r_sz)      # Top-Right
        painter.drawRect(0, H - r_sz, r_sz, r_sz)      # Bottom-Left
        painter.drawRect(W - r_sz, H - r_sz, r_sz, r_sz)# Bottom-Right

        # 3. Dividing Lines
        pen_div = QPen(QColor("#2d3748"), 1)
        painter.setPen(pen_div)
        painter.drawLine(0, r_sz, W, r_sz)              # Top line
        painter.drawLine(0, H - r_sz, W, H - r_sz)      # Bottom line
        painter.drawLine(r_sz, 0, r_sz, H)              # Left line
        painter.drawLine(W - r_sz, 0, W - r_sz, H)      # Right line

        # 4. Corner Crosshairs / Brackets in all 4 corner boxes
        pen_corner = QPen(QColor("#38bdf8"), 1)
        painter.setPen(pen_corner)
        m = 5
        # Top-Left
        painter.drawLine(m, r_sz // 2, r_sz - m, r_sz // 2)
        painter.drawLine(r_sz // 2, m, r_sz // 2, r_sz - m)
        # Top-Right
        painter.drawLine(W - r_sz + m, r_sz // 2, W - m, r_sz // 2)
        painter.drawLine(W - r_sz // 2, m, W - r_sz // 2, r_sz - m)
        # Bottom-Left
        painter.drawLine(m, H - r_sz // 2, r_sz - m, H - r_sz // 2)
        painter.drawLine(r_sz // 2, H - r_sz + m, r_sz // 2, H - m)
        # Bottom-Right
        painter.drawLine(W - r_sz + m, H - r_sz // 2, W - m, H - r_sz // 2)
        painter.drawLine(W - r_sz // 2, H - r_sz + m, W - r_sz // 2, H - m)

        # 5. Ticks on all 4 sides
        painter.setPen(QColor("#64748b"))
        painter.setFont(QFont("Consolas", 7))

        # Horizontal Ticks (Top & Bottom)
        for x in range(r_sz, W - r_sz, 50):
            painter.drawLine(x, r_sz - 4, x, r_sz)
            painter.drawLine(x, H - r_sz, x, H - r_sz + 4)
            if (x - r_sz) % 100 == 0 and x < W - r_sz - 30:
                painter.drawText(x + 2, 11, str(x - r_sz))

        # Vertical Ticks (Left & Right)
        for y in range(r_sz, H - r_sz, 50):
            painter.drawLine(r_sz - 4, y, r_sz, y)
            painter.drawLine(W - r_sz, y, W - r_sz + 4, y)
            if (y - r_sz) % 100 == 0 and y < H - r_sz - 20:
                painter.drawText(2, y + 10, str(y - r_sz))

        # 6. Symmetrical 4-Corner Cinema Framing Brackets around the active canvas
        if canvas_rect and canvas_rect.width() > 40:
            painter.setPen(QPen(QColor("#38bdf8"), 1.5))
            cx, cy = canvas_rect.left(), canvas_rect.top()
            cr, cb = canvas_rect.right(), canvas_rect.bottom()
            c_len = 16
            # Top-Left ┌
            painter.drawLine(QPointF(cx, cy), QPointF(cx + c_len, cy))
            painter.drawLine(QPointF(cx, cy), QPointF(cx, cy + c_len))
            # Top-Right ┐
            painter.drawLine(QPointF(cr, cy), QPointF(cr - c_len, cy))
            painter.drawLine(QPointF(cr, cy), QPointF(cr, cy + c_len))
            # Bottom-Left └
            painter.drawLine(QPointF(cx, cb), QPointF(cx + c_len, cb))
            painter.drawLine(QPointF(cx, cb), QPointF(cx, cb - c_len))
            # Bottom-Right ┘
            painter.drawLine(QPointF(cr, cb), QPointF(cr - c_len, cb))
            painter.drawLine(QPointF(cr, cb), QPointF(cr, cb - c_len))
