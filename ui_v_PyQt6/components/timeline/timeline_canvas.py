"""
Timeline Canvas Component for PyQt6 / PySide6 Desktop Studio
Hardware-accelerated custom QPainter timeline canvas with 60fps rendering,
real video filmstrip thumbnails, audio waveform peaks, and rich CC subtitle blocks.
"""

import os
import math
import threading
from ui_v_PyQt6.qt_compat import (
    QWidget, QPainter, QPen, QBrush, QColor, QFont, 
    Qt, QCursor, QPoint, QImage, QPixmap, QTimer, QMenu, QAction,
    Signal, QToolTip, QInputDialog, QPainterPath, QRect, QRectF
)
from utils import format_timestamp


def format_duration_short(seconds: float) -> str:
    """Formats seconds into readable mm:ss or hh:mm:ss string"""
    s = max(0, int(round(seconds)))
    m = s // 60
    sec = s % 60
    h = m // 60
    if h > 0:
        return f"{h:02d}:{m%60:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


class TimelineCanvas(QWidget):
    """
    Hardware-accelerated custom QPainter timeline canvas:
    - Real Video Filmstrip thumbnails sampled across duration
    - Real / Simulated Audio Waveform peaks for Voice Dub Track
    - Rich CC Subtitle blocks with line badges and live highlighting
    - Multi-clip selection with Ctrl+Click and Shift+Click
    - Drag & Move subtitle clips left and right
    - Resize / Trim clip start and end with edge dragging
    - Double click to edit subtitle dialogue inline
    - Drag & Drop media (video, srt, audio) directly onto timeline
    - Deep zooming up to 25x (800 px/sec) with cursor-centered zoom
    - Right-click context menu on clips and empty timeline space
    - Multi-track visualization with high precision needle scrubbing
    """
    subtitles_modified = Signal()
    video_dropped = Signal(str)
    subtitle_dropped = Signal(str)
    audio_dropped = Signal(str)
    audio_tracks_modified = Signal()
    audio_selected = Signal(object)
    video_visibility_changed = Signal(bool)
    cc_visibility_changed = Signal(bool)
    audio_mute_changed = Signal(bool)
    overlay_visibility_changed = Signal(bool)
    overlay_selected = Signal(object)
    overlays_modified = Signal()
    mark_in_changed = Signal(object)
    mark_out_changed = Signal(object)
    split_requested = Signal(float)
    ripple_delete_requested = Signal()
    extract_range_requested = Signal(float, float)
    export_range_requested = Signal(float, float)
    keyframe_added = Signal(float)       # timestamp
    keyframe_selected = Signal(dict)     # keyframe dict
    keyframe_moved = Signal(int, float)  # (idx, new_time)
    keyframe_deleted = Signal(float)     # timestamp
    keyframes_modified = Signal(list)    # all keyframes
    auto_split_requested = Signal(float)
    merge_segments_requested = Signal()

    HEADER_W = 76

    def __init__(
        self,
        parent=None,
        on_seek=None,
        on_select_sub=None,
        on_select_multiple_subs=None,
        on_context_menu=None,
        on_add_sub_at_time=None,
        on_fix_overlaps=None,
        on_subtitles_modified=None,
        on_video_dropped=None,
        on_subtitle_dropped=None,
        on_audio_dropped=None,
        on_toggle_cc_visibility=None,
        on_toggle_audio_mute=None
    ):
        super().__init__(parent)
        self.on_seek = on_seek
        self.on_select_sub = on_select_sub
        self.on_select_multiple_subs = on_select_multiple_subs
        self.on_context_menu = on_context_menu
        self.on_add_sub_at_time = on_add_sub_at_time
        self.on_fix_overlaps = on_fix_overlaps
        self.on_subtitles_modified = on_subtitles_modified
        self.on_video_dropped = on_video_dropped
        self.on_subtitle_dropped = on_subtitle_dropped
        self.on_audio_dropped = on_audio_dropped
        self.on_toggle_cc_visibility = on_toggle_cc_visibility
        self.on_toggle_audio_mute = on_toggle_audio_mute

        self.duration = 100.0
        self.current_time = 0.0
        self.zoom = 1.0  # Pixels per second multiplier
        self.offset_x = 0
        self.offset_y = 0
        self._is_dragging_v_scrollbar = False
        self._v_scrollbar_drag_start_y = 0
        self._v_scrollbar_drag_start_offset_y = 0

        self.subtitles = []
        self.video_clips = []
        self.audio_tracks = []
        self.overlay_clips = []
        self.video_keyframes = []
        self.active_kf_idx = -1
        self.active_sub_idx = -1
        self.active_overlay_idx = -1
        self._hit_track = "cc"
        self.selected_indices = set()  # Set of selected subtitle indices

        # Track Visibility & Mute Toggles
        self.is_video_visible = True
        self.is_cc_visible = True
        self.is_audio_track_muted = False
        self.is_overlay_visible = True
        self._hovered_header_btn = None

        # Video Filmstrip Thumbnails Cache
        self.video_path = None
        self.video_thumbnails = []  # List of (timestamp, QPixmap)
        self._is_extracting_thumbs = False

        self.setMinimumHeight(162)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Interactive Drag / Trim / Move States
        self._dragging_playhead = False
        self._interaction_mode = None  # None, "scrub_playhead", "move", "trim_start", "trim_end", "marquee_select"
        self._drag_start_x = 0
        self._active_clip_idx = -1
        self._orig_positions = {}  # idx -> (start, end)
        self._orig_clip_start = 0.0
        self._orig_clip_end = 0.0
        self._has_clip_changed = False
        self._pressed_was_already_selected = False

        # Marquee / Rubber-band Selection States
        self._marquee_active = False
        self._marquee_start_pos = QPoint()
        self._marquee_current_pos = QPoint()
        # Mark In / Mark Out Range States
        self.mark_in = None
        self.mark_out = None

    def set_mark_in(self, t: float = None):
        """Sets Mark In point at specified time or current playhead (I)."""
        cur_t = self.current_time if t is None else float(t)
        self.mark_in = max(0.0, min(self.duration, round(cur_t, 3)))
        if self.mark_out is not None and self.mark_out <= self.mark_in:
            self.mark_out = None
            self.mark_out_changed.emit(None)
        self.mark_in_changed.emit(self.mark_in)
        self.update()

    def set_mark_out(self, t: float = None):
        """Sets Mark Out point at specified time or current playhead (O)."""
        cur_t = self.current_time if t is None else float(t)
        self.mark_out = max(0.0, min(self.duration, round(cur_t, 3)))
        if self.mark_in is not None and self.mark_in >= self.mark_out:
            self.mark_in = 0.0
            self.mark_in_changed.emit(0.0)
        self.mark_out_changed.emit(self.mark_out)
        self.update()

    def clear_in_out(self):
        """Clears Mark In and Mark Out points (Alt+X)."""
        self.mark_in = None
        self.mark_out = None
        self.mark_in_changed.emit(None)
        self.mark_out_changed.emit(None)
        self.update()

    def get_in_out_range(self):
        """Returns effective (start, end) range tuple."""
        in_t = self.mark_in if self.mark_in is not None else 0.0
        out_t = self.mark_out if self.mark_out is not None else self.duration
        if out_t < in_t:
            in_t, out_t = out_t, in_t
        return (in_t, out_t)

    def set_duration(self, dur: float):
        self.duration = max(1.0, dur)
        self.update()

    def set_current_time(self, t: float):
        self.current_time = max(0.0, min(self.duration, t))
        self.update()

    def set_data(self, subtitles=None, video_clips=None, audio_tracks=None, video_path=None, overlay_clips=None, video_keyframes=None):
        if subtitles is not None:
            self.subtitles = subtitles
        if video_clips is not None:
            self.video_clips = video_clips
        if audio_tracks is not None:
            self.audio_tracks = audio_tracks
        if overlay_clips is not None:
            self.overlay_clips = overlay_clips
        if video_keyframes is not None:
            self.video_keyframes = video_keyframes
        if video_path and video_path != self.video_path:
            self.load_video_thumbnails(video_path)
        self.update()

    def set_video_keyframes(self, keyframes):
        """Sets list of video keyframes for timeline diamond markers."""
        self.video_keyframes = keyframes if keyframes is not None else []
        self.update()

    def set_overlay_clips(self, overlay_clips):
        self.overlay_clips = overlay_clips if overlay_clips is not None else []
        self.update()

    def load_video_thumbnails(self, video_path: str):
        """Asynchronously extracts video thumbnails using ultra-fast OpenCV cleanly with high density."""
        if not video_path or not os.path.exists(video_path):
            return
        self.video_path = video_path
        if getattr(self, "_is_extracting_thumbs", False):
            return

        def worker():
            self._is_extracting_thumbs = True
            try:
                import cv2
                import hashlib
                import tempfile

                # Compute persistent cache key based on file path, size, and mtime
                try:
                    f_stat = os.stat(video_path)
                    cache_key = hashlib.md5(f"{video_path}_{f_stat.st_size}_{f_stat.st_mtime}".encode("utf-8")).hexdigest()
                except Exception:
                    cache_key = hashlib.md5(video_path.encode("utf-8")).hexdigest()

                thumb_dir = os.path.join(tempfile.gettempdir(), f"studio_thumbs_v2_{cache_key}")
                os.makedirs(thumb_dir, exist_ok=True)

                # Check if already fully cached on disk
                cached_files = sorted([
                    os.path.join(thumb_dir, f) for f in os.listdir(thumb_dir) 
                    if f.endswith(".jpg") and os.path.getsize(os.path.join(thumb_dir, f)) > 100
                ])

                if len(cached_files) >= 30:
                    thumbnails = []
                    for f_path in cached_files:
                        bname = os.path.splitext(os.path.basename(f_path))[0]
                        parts = bname.split("_")
                        try:
                            t_val = float(parts[1]) if len(parts) >= 2 else 0.0
                        except Exception:
                            t_val = 0.0
                        pix = QPixmap(f_path)
                        if not pix.isNull():
                            thumbnails.append((t_val, pix))
                    if thumbnails:
                        thumbnails.sort(key=lambda x: x[0])
                        self.video_thumbnails = thumbnails
                        QTimer.singleShot(0, self.update)
                        return

                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                    return

                fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
                total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
                v_dur = total_frames / fps if total_frames > 0 and fps > 0 else max(1.0, self.duration)

                # Fine sampling interval: every 10-15s across the movie
                if v_dur <= 120:
                    interval = 2.0
                elif v_dur <= 600:
                    interval = 4.0
                elif v_dur <= 1800:
                    interval = 8.0
                elif v_dur <= 3600:
                    interval = 12.0
                else:
                    interval = 15.0

                sample_times = []
                cur_t = 0.0
                while cur_t < v_dur:
                    sample_times.append(round(cur_t, 2))
                    cur_t += interval

                if len(sample_times) > 320:
                    step = len(sample_times) / 320.0
                    sample_times = [sample_times[int(i * step)] for i in range(320)]

                # Phase 1: Fast initial preview (24 coarse samples in <0.4s)
                coarse_step = max(1, len(sample_times) // 24)
                phase1_times = [sample_times[i] for i in range(0, len(sample_times), coarse_step)]

                phase1_thumbs = []
                for t in phase1_times:
                    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        small = cv2.resize(frame, (72, 40), interpolation=cv2.INTER_AREA)
                        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                        h, w, ch = rgb.shape
                        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
                        phase1_thumbs.append((t, qimg))

                def apply_phase1(p1_list):
                    if not self.video_thumbnails:
                        self.video_thumbnails = [(t, QPixmap.fromImage(q)) for t, q in p1_list]
                        self.update()

                if phase1_thumbs:
                    QTimer.singleShot(0, lambda: apply_phase1(phase1_thumbs))

                # Phase 2: Full dense scan across all scenes
                dense_thumbs = []
                sub_starts = []
                if self.subtitles:
                    sub_starts = [float(s.get("start", 0.0)) for s in self.subtitles if float(s.get("start", 0.0)) < v_dur]

                all_target_times = sorted(list(set(sample_times + sub_starts[:60])))
                if len(all_target_times) > 360:
                    all_target_times = sample_times

                for idx, t in enumerate(all_target_times):
                    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        small = cv2.resize(frame, (72, 40), interpolation=cv2.INTER_AREA)
                        out_f = os.path.join(thumb_dir, f"t_{t:07.2f}_{idx:04d}.jpg")
                        cv2.imwrite(out_f, small, [cv2.IMWRITE_JPEG_QUALITY, 80])
                        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                        h, w, ch = rgb.shape
                        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
                        dense_thumbs.append((t, qimg))

                cap.release()

                def apply_phase2(p2_list):
                    self.video_thumbnails = sorted([(t, QPixmap.fromImage(q)) for t, q in p2_list], key=lambda x: x[0])
                    self.update()

                if dense_thumbs:
                    QTimer.singleShot(0, lambda: apply_phase2(dense_thumbs))

            except Exception:
                pass
            finally:
                self._is_extracting_thumbs = False

        threading.Thread(target=worker, daemon=True).start()

    def ensure_visible_time(self, t: float):
        """Scrolls the timeline view if timestamp t is outside current visible area."""
        pps = self.get_pixels_per_sec()
        hw = self.HEADER_W
        vis_w = max(50, self.width() - hw)
        cur_x = int(t * pps)
        left_bound = self.offset_x + 40
        right_bound = self.offset_x + vis_w - 60
        if cur_x < left_bound or cur_x > right_bound:
            self.offset_x = max(0, int(cur_x - vis_w * 0.35))
            self.update()

    def set_selected_indices(self, indices):
        """Syncs selection set from subtitles table or external caller and centers line voice."""
        new_set = set(indices) if indices is not None else set()
        if new_set != self.selected_indices:
            self.selected_indices = new_set
            if self.selected_indices:
                self.active_sub_idx = min(self.selected_indices)
                if 0 <= self.active_sub_idx < len(self.subtitles):
                    st = float(self.subtitles[self.active_sub_idx].get("start", 0.0))
                    self.ensure_visible_time(st)
            else:
                self.active_sub_idx = -1
            self.update()

    def get_pixels_per_sec(self) -> float:
        """
        Calculates pixels per second with dynamic range:
        - Baseline: 35.0 px/s at 1.0x zoom (clear 3-second block is ~105px wide)
        - Supports deep zoom in up to 800 px/s (up to ~25x zoom for micro-level timing)
        - Supports zoom out down to 1.5 px/s for full-movie bird's-eye overview
        """
        pps = 35.0 * self.zoom
        return max(1.5, min(800.0, pps))

    def zoom_to(self, new_zoom: float, anchor_x: float = None):
        """Zooms smoothly centered on anchor_x (mouse cursor or canvas center)"""
        old_pps = self.get_pixels_per_sec()
        if anchor_x is None:
            anchor_x = (self.width() - self.HEADER_W) / 2.0 + self.HEADER_W
        canvas_anchor_x = max(0.0, anchor_x - self.HEADER_W)
        anchor_t = (canvas_anchor_x + self.offset_x) / old_pps

        self.zoom = max(0.05, min(25.0, new_zoom))
        new_pps = self.get_pixels_per_sec()

        # Keep anchor_t at the exact same screen position
        self.offset_x = max(0, int(anchor_t * new_pps - canvas_anchor_x))
        self.update()

        # Sync parent slider & label if available
        parent_widget = self.parent()
        if parent_widget:
            slider = getattr(parent_widget, "slider_zoom", None)
            if slider:
                slider.blockSignals(True)
                slider.setValue(int(self.zoom * 100))
                slider.blockSignals(False)
            lbl = getattr(parent_widget, "lbl_zoom_val", None)
            if lbl:
                lbl.setText(f"{int(self.zoom * 100)}%")

    def set_zoom(self, zoom_factor: float):
        self.zoom_to(zoom_factor)

    def toggle_video_visibility(self):
        """Toggles visibility of Video Track."""
        self.is_video_visible = not self.is_video_visible
        self.video_visibility_changed.emit(self.is_video_visible)
        self.update()

    def toggle_cc_visibility(self):
        """Toggles visibility of CC subtitles in video playback monitor."""
        self.is_cc_visible = not self.is_cc_visible
        self.cc_visibility_changed.emit(self.is_cc_visible)
        if self.on_toggle_cc_visibility:
            self.on_toggle_cc_visibility(self.is_cc_visible)
        self.update()

    def toggle_audio_mute(self):
        """Toggles muting of voice dubbing audio in playback."""
        self.is_audio_track_muted = not self.is_audio_track_muted
        self.audio_mute_changed.emit(self.is_audio_track_muted)
        if self.on_toggle_audio_mute:
            self.on_toggle_audio_mute(self.is_audio_track_muted)
        self.update()

    def toggle_overlay_visibility(self):
        """Toggles visibility of Overlays & Shapes track."""
        self.is_overlay_visible = not self.is_overlay_visible
        self.overlay_visibility_changed.emit(self.is_overlay_visible)
        self.update()

    def fit_to_window(self):
        """Fits the entire duration within the current canvas width"""
        w = max(400, self.width() - self.HEADER_W - 20)
        fit_pps = w / max(1.0, self.duration)
        fit_zoom = max(0.05, fit_pps / 35.0)
        self.offset_x = 0
        self.zoom_to(fit_zoom, anchor_x=self.HEADER_W)

    def wheelEvent(self, event):
        # 1. Ctrl + Wheel for cursor-centered deep zoom
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            anchor_x = event.position().x() if hasattr(event, "position") else event.pos().x()
            if delta > 0:
                self.zoom_to(self.zoom * 1.2, anchor_x=anchor_x)
            else:
                self.zoom_to(self.zoom / 1.2, anchor_x=anchor_x)
            return

        # 2. Shift + Wheel or horizontal tilt wheel: Horizontal timeline scrub
        if (event.modifiers() & Qt.KeyboardModifier.ShiftModifier) or event.angleDelta().x():
            delta_x = event.angleDelta().x() or event.angleDelta().y()
            self.offset_x = max(0, self.offset_x - delta_x)
            self.update()
            return

        # 3. Regular Vertical Wheel (Up / Down):
        # Smoothly scrolls up and down through multi-track layers (Video, CC Subtitles, Audio, Overlays)
        delta_y = event.angleDelta().y()
        layout = self._get_tracks_layout()
        max_scroll_y = layout.get("max_scroll_y", 0)

        if max_scroll_y > 0:
            # Vertical scroll through tracks
            self.offset_y = max(0, min(max_scroll_y, self.offset_y - delta_y))
            self.update()
        else:
            # If all tracks comfortably fit on screen, default mouse wheel to horizontal scrubbing
            self.offset_x = max(0, self.offset_x - delta_y)
            self.update()

    def _get_overlay_time_span(self, item):
        if hasattr(item, "start_time"):
            st = float(getattr(item, "start_time", 0.0))
            et = float(getattr(item, "end_time", 0.0))
            if et <= st:
                dur = getattr(self, "duration", 100.0) or 100.0
                et = min(dur, max(st + 1.0, st + 5.0))
                item.end_time = round(et, 3)
        else:
            st = float(item.get("start", 0.0))
            et = float(item.get("end", 0.0))
            if et <= st:
                dur = getattr(self, "duration", 100.0) or 100.0
                et = min(dur, max(st + 1.0, st + 5.0))
                item["end"] = round(et, 3)
        return st, max(st + 0.1, et)

    def _get_overlay_info(self, item):
        if hasattr(item, "item_type"):
            itype = getattr(item, "item_type", "image")
            name = getattr(item, "name", "") or getattr(item, "text", "") or itype.title()
        else:
            itype = item.get("type", "image")
            name = item.get("text", "") or item.get("name", "") or itype.title()
        return itype, name

    def _set_overlay_time_span(self, item, st, et):
        if hasattr(item, "start_time"):
            item.start_time = round(st, 3)
            item.end_time = round(et, 3)
        else:
            item["start"] = round(st, 3)
            item["end"] = round(et, 3)

    def _get_audio_items_for_timeline(self):
        """Returns unified list of audio items combining independent dropped tracks and subtitle dialogue lines."""
        items = []
        # 1. Independent dropped audio tracks (MP3/WAV music, sound effects, imported speech)
        for idx, trk in enumerate(self.audio_tracks):
            st = float(trk.get("start", 0.0))
            dur = float(trk.get("duration", 5.0))
            et = float(trk.get("end", st + dur))
            items.append({
                "is_track": True,
                "track_idx": idx,
                "start": st,
                "end": max(st + 0.1, et),
                "duration": dur,
                "name": trk.get("name", "Audio"),
                "path": trk.get("path", ""),
                "volume": float(trk.get("volume", 1.0)),
                "speed": float(trk.get("speed", 1.0)),
                "raw": trk
            })
        # 2. Dialogue dubbing lines from subtitles
        for idx, sub in enumerate(self.subtitles):
            st = float(sub.get("start", 0.0))
            et = float(sub.get("end", 0.0))
            dur = float(sub.get("audio_dur", 0.0))
            if dur > 0.1:
                et = max(et, st + dur)
            actor = sub.get("actor") or sub.get("speaker") or sub.get("character")
            if not actor:
                g = sub.get("gender")
                actor = "តួស្រី (Female)" if g == "female" else ("តួប្រុស (Male)" if g == "male" else "តួទូទៅ (Dialogue)")
            voice_name = sub.get("voice_name") or sub.get("voice") or ""
            gender = sub.get("gender") or ("female" if ("ស្រី" in actor or "Female" in actor) else ("male" if ("ប្រុស" in actor or "Male" in actor) else "dialogue"))
            has_audio = bool(sub.get("audio_file") or sub.get("audio_path"))
            items.append({
                "is_track": False,
                "sub_idx": idx,
                "start": st,
                "end": max(st + 0.1, et),
                "duration": max(0.1, et - st),
                "name": sub.get("khmer_text") or sub.get("orig_text") or f"Line #{idx+1}",
                "actor": actor,
                "voice_name": voice_name,
                "gender": gender,
                "has_audio": has_audio,
                "rate": sub.get("rate", "+0%"),
                "pitch": sub.get("pitch", "+0Hz"),
                "volume": 1.0,
                "speed": 1.0,
                "raw": sub
            })
        return items

    def _calculate_lanes(self, items, is_audio=False, is_overlay=False):
        """
        Computes dynamic lane allocation using interval graph scheduling.
        When dialogue, voice dubbing, or overlay clips overlap in time, overlapping clips
        dynamically branch into stacked sub-rows (Lane 1, Lane 2, etc.),
        preventing clips from colliding or hiding each other.
        Returns:
            dict: clip_idx -> lane_index (0-indexed)
            int: total_lanes count (at least 1)
        """
        if not items:
            return {}, 1

        entries = []
        for idx, item in enumerate(items):
            if is_overlay:
                s, e = self._get_overlay_time_span(item)
            elif is_audio and isinstance(item, dict) and "is_track" in item:
                s = float(item.get("start", 0.0))
                e = float(item.get("end", 0.0))
            else:
                s = float(item.get("start", 0.0))
                e = float(item.get("end", 0.0))
                if is_audio:
                    dur = float(item.get("audio_dur", 0.0))
                    if dur > 0.1:
                        e = max(e, s + dur)
            # Ensure a minimal positive duration for layout stability
            entries.append((idx, s, max(s + 0.05, e)))

        # Sort primarily by start time, then end time
        entries.sort(key=lambda x: (x[1], x[2]))

        lane_end_times = []  # lane_index -> last end time
        clip_to_lane = {}

        for idx, s, e in entries:
            assigned_lane = None
            for l_idx, l_end in enumerate(lane_end_times):
                if s >= l_end - 0.04:  # small tolerance for adjacent clips
                    assigned_lane = l_idx
                    lane_end_times[l_idx] = max(l_end, e)
                    break

            if assigned_lane is None:
                assigned_lane = len(lane_end_times)
                lane_end_times.append(e)

            clip_to_lane[idx] = assigned_lane

        total_lanes = max(1, len(lane_end_times))
        return clip_to_lane, total_lanes

    def _get_tracks_layout(self):
        """
        Calculates dynamic track vertical positions and heights based on overlapping lanes.
        """
        ruler_h = 26
        v_h = 46
        lane_h = 42

        cc_lane_map, cc_num_lanes = self._calculate_lanes(self.subtitles, is_audio=False)
        cc_h = cc_num_lanes * lane_h

        audio_items = self._get_audio_items_for_timeline()
        a_lane_map, a_num_lanes = self._calculate_lanes(audio_items, is_audio=True)
        a_h = a_num_lanes * lane_h

        ov_lane_map, ov_num_lanes = self._calculate_lanes(self.overlay_clips, is_overlay=True)
        ov_h = max(42, ov_num_lanes * lane_h)

        total_content_h = ruler_h + v_h + 3 + cc_h + 3 + a_h + 3 + ov_h + 12

        # Clamp vertical scroll offset
        h = self.height() if self.height() > 50 else 180
        max_scroll_y = max(0, total_content_h - h)
        if not hasattr(self, "offset_y"):
            self.offset_y = 0
        self.offset_y = max(0, min(max_scroll_y, self.offset_y))

        v_y = ruler_h - self.offset_y
        cc_y = v_y + v_h + 3
        a_y = cc_y + cc_h + 3
        ov_y = a_y + a_h + 3
        total_h = ov_y + ov_h + 12

        return {
            "v_y": v_y, "v_h": v_h,
            "cc_y": cc_y, "cc_h": cc_h, "cc_lane_map": cc_lane_map, "cc_num_lanes": cc_num_lanes,
            "a_y": a_y, "a_h": a_h, "a_lane_map": a_lane_map, "a_num_lanes": a_num_lanes,
            "ov_y": ov_y, "ov_h": ov_h, "ov_lane_map": ov_lane_map, "ov_num_lanes": ov_num_lanes,
            "lane_h": lane_h,
            "total_h": total_h,
            "total_content_h": total_content_h,
            "max_scroll_y": max_scroll_y
        }

    def _get_v_scrollbar_rect(self):
        """Returns (track_rect, thumb_rect) for vertical scrollbar when tracks exceed canvas height."""
        layout = self._get_tracks_layout()
        total_content_h = layout.get("total_content_h", 0)
        h = self.height()
        ruler_h = 26
        visible_h = h - ruler_h
        if total_content_h <= h or visible_h <= 10:
            return None, None

        bar_w = 6
        bar_x = self.width() - bar_w - 2
        bar_y = ruler_h + 2
        bar_h = visible_h - 4

        thumb_h = max(24, int(bar_h * (h / float(total_content_h))))
        max_scroll_y = max(1, total_content_h - h)
        thumb_y = bar_y + int((bar_h - thumb_h) * (self.offset_y / float(max_scroll_y)))

        return QRect(bar_x, bar_y, bar_w, bar_h), QRect(bar_x, thumb_y, bar_w, thumb_h)

    def _get_header_button_rects(self):
        """Returns dict of header action button QRects for hit testing and hover states"""
        layout = self._get_tracks_layout()
        btn_w = 26
        btn_h = 24
        bx = 42

        v_rect = QRect(bx, layout["v_y"] + (layout["v_h"] - btn_h) // 2, btn_w, btn_h)
        cc_rect = QRect(bx, layout["cc_y"] + (layout["lane_h"] - btn_h) // 2, btn_w, btn_h)
        a_rect = QRect(bx, layout["a_y"] + (layout["lane_h"] - btn_h) // 2, btn_w, btn_h)
        ov_rect = QRect(bx, layout["ov_y"] + (layout["lane_h"] - btn_h) // 2, btn_w, btn_h)

        return {
            "video_eye": v_rect,
            "cc_eye": cc_rect,
            "audio_speaker": a_rect,
            "overlay_eye": ov_rect
        }

    def _draw_camera_icon(self, painter: QPainter, x: int, y: int, color: QColor):
        """Draws rounded video camera icon matching modern NLE track icon"""
        painter.save()
        painter.setPen(QPen(color, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(x, y + 2, 14, 11, 3, 3)
        path = QPainterPath()
        path.moveTo(x + 14, y + 5)
        path.lineTo(x + 19, y + 2)
        path.lineTo(x + 19, y + 13)
        path.lineTo(x + 14, y + 10)
        painter.drawPath(path)
        painter.restore()

    def _draw_eye_icon(self, painter: QPainter, x: int, y: int, is_open: bool, color: QColor):
        """Draws eye icon: open eye if visible, or closed eyelid with lashes matching screenshot"""
        painter.save()
        painter.setPen(QPen(color, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        if is_open:
            path = QPainterPath()
            path.moveTo(x, y + 6)
            path.quadTo(x + 8, y, x + 16, y + 6)
            path.quadTo(x + 8, y + 12, x, y + 6)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QPoint(x + 8, y + 6), 2, 2)
        else:
            path = QPainterPath()
            path.moveTo(x + 1, y + 5)
            path.quadTo(x + 8, y + 9, x + 15, y + 5)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            painter.drawLine(x + 4, y + 8, x + 3, y + 11)
            painter.drawLine(x + 8, y + 9, x + 8, y + 12)
            painter.drawLine(x + 12, y + 8, x + 13, y + 11)
        painter.restore()

    def _draw_music_icon(self, painter: QPainter, x: int, y: int, color: QColor):
        """Draws double eighth note icon (🎵)"""
        painter.save()
        painter.setPen(QPen(color, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(QBrush(color))
        painter.drawEllipse(x + 1, y + 9, 5, 4)
        painter.drawEllipse(x + 9, y + 7, 5, 4)
        painter.drawLine(x + 5, y + 11, x + 5, y + 2)
        painter.drawLine(x + 13, y + 9, x + 13, y + 1)
        painter.setPen(QPen(color, 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawLine(x + 5, y + 2, x + 13, y + 1)
        painter.restore()

    def _draw_speaker_icon(self, painter: QPainter, x: int, y: int, is_muted: bool, color: QColor):
        """Draws speaker icon: speaker with waves if unmuted, or speaker with 'x' matching screenshot"""
        painter.save()
        painter.setPen(QPen(color, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(QBrush(color))
        path = QPainterPath()
        path.moveTo(x + 1, y + 4)
        path.lineTo(x + 4, y + 4)
        path.lineTo(x + 8, y + 1)
        path.lineTo(x + 8, y + 12)
        path.lineTo(x + 4, y + 9)
        path.lineTo(x + 1, y + 9)
        path.closeSubpath()
        painter.drawPath(path)

        if is_muted:
            painter.setPen(QPen(color, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(x + 11, y + 5, x + 15, y + 9)
            painter.drawLine(x + 15, y + 5, x + 11, y + 9)
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(x + 7, y + 3, 5, 7, -60 * 16, 120 * 16)
            painter.drawArc(x + 9, y + 1, 7, 11, -60 * 16, 120 * 16)
        painter.restore()

    def _draw_shapes_icon(self, painter: QPainter, x: int, y: int, color: QColor):
        """Draws overlapping rounded squares icon (shapes / layers matching screenshot)"""
        painter.save()
        painter.setPen(QPen(color, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(x, y + 3, 10, 10, 2.5, 2.5)
        path = QPainterPath()
        path.moveTo(x + 4, y + 3)
        path.lineTo(x + 4, y + 1)
        path.quadTo(x + 4, y, x + 5, y)
        path.lineTo(x + 13, y)
        path.quadTo(x + 14, y, x + 14, y + 1)
        path.lineTo(x + 14, y + 9)
        path.quadTo(x + 14, y + 10, x + 13, y + 10)
        path.lineTo(x + 10, y + 10)
        painter.drawPath(path)
        painter.restore()

    def _draw_cc_icon(self, painter: QPainter, x: int, y: int, color: QColor):
        """Draws subtitle / dialogue text badge icon"""
        painter.save()
        painter.setPen(QPen(color, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(x, y + 2, 16, 11, 3, 3)
        painter.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
        painter.setPen(color)
        painter.drawText(x + 2, y + 10, "CC")
        painter.restore()

    def _draw_white_handle(self, painter: QPainter, x: int, y: int, h: int):
        """
        Draws the signature white rounded pill handle [ | ] with dark vertical grip notch
        as shown in the user's reference screenshot on Audio and Overlay clips.
        """
        w = 10
        handle_h = min(18, max(12, h - 8))
        hy = y + (h - handle_h) // 2
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawRoundedRect(x, hy, w, handle_h, 3, 3)
        painter.setPen(QPen(QColor("#1e293b"), 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        slit_h = max(6, handle_h - 8)
        slit_y = hy + (handle_h - slit_h) // 2
        painter.drawLine(x + w // 2, slit_y, x + w // 2, slit_y + slit_h)
        painter.restore()

    def _draw_golden_handle(self, painter: QPainter, x: int, y: int, h: int, is_left: bool):
        """
        Draws the golden amber trim handle on Video filmstrip clips as shown in the screenshot.
        """
        w = 10
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#f59e0b")))
        if is_left:
            path = QPainterPath()
            path.moveTo(x + w, y)
            path.lineTo(x + 3, y)
            path.quadTo(x, y, x, y + 3)
            path.lineTo(x, y + h - 3)
            path.quadTo(x, y + h, x + 3, y + h)
            path.lineTo(x + w, y + h)
            path.closeSubpath()
            painter.drawPath(path)
        else:
            path = QPainterPath()
            path.moveTo(x, y)
            path.lineTo(x + w - 3, y)
            path.quadTo(x + w, y, x + w, y + 3)
            path.lineTo(x + w, y + h - 3)
            path.quadTo(x + w, y + h, x + w - 3, y + h)
            path.lineTo(x, y + h)
            path.closeSubpath()
            painter.drawPath(path)

        painter.setPen(QPen(QColor("#fef3c7"), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        slit_h = max(8, h - 14)
        slit_y = y + (h - slit_h) // 2
        painter.drawLine(x + w // 2, slit_y, x + w // 2, slit_y + slit_h)
        painter.restore()

    def _draw_keyframe_diamond(self, painter: QPainter, cx: int, cy: int, is_active: bool = False):
        """Draws a video editing keyframe diamond marker ◆ on timeline track."""
        painter.save()
        sz = 8 if is_active else 6
        path = QPainterPath()
        path.moveTo(cx, cy - sz)
        path.lineTo(cx + sz, cy)
        path.lineTo(cx, cy + sz)
        path.lineTo(cx - sz, cy)
        path.closeSubpath()

        if is_active:
            painter.setBrush(QBrush(QColor("#f59e0b")))  # Glowing Gold
            painter.setPen(QPen(QColor("#ffffff"), 2.0))
        else:
            painter.setBrush(QBrush(QColor("#38bdf8")))  # Sky Blue
            painter.setPen(QPen(QColor("#0369a1"), 1.2))

        painter.drawPath(path)
        painter.restore()

    def _hit_test_keyframe(self, pos_x: int, pos_y: int):
        """Hit-tests diamond keyframe points on Track 1 (Video). Returns (kf_index, keyframe_dict) or (-1, None)."""
        layout = self._get_tracks_layout()
        v_y = layout["v_y"]
        v_h = layout["v_h"]
        if not (v_y - 6 <= pos_y <= v_y + v_h + 6):
            return (-1, None)

        pps = self.get_pixels_per_sec()
        hw = self.HEADER_W
        for idx, kf in enumerate(getattr(self, "video_keyframes", [])):
            kt = float(kf.get("time", 0.0))
            kx = hw + int(kt * pps - self.offset_x)
            if abs(pos_x - kx) <= 10:
                return (idx, kf)
        return (-1, None)

    def _delete_keyframe_at_idx(self, idx: int):
        if 0 <= idx < len(getattr(self, "video_keyframes", [])):
            deleted_t = float(self.video_keyframes[idx].get("time", 0.0))
            del self.video_keyframes[idx]
            self.active_kf_idx = -1
            self.keyframe_deleted.emit(deleted_t)
            self.keyframes_modified.emit(self.video_keyframes)
            self.update()

    def _hit_test_clip(self, pos_x: int, pos_y: int):
        """
        Hit tests clips on dynamic multi-lane CC Track, Audio Track, and Overlays & Blur FX Track.
        Returns: (clip_idx, hit_part)
        where hit_part is 'left_edge', 'right_edge', 'body', or None.
        Sets self._hit_track to 'cc', 'audio', or 'overlay'.
        """
        if pos_x < self.HEADER_W:
            return (-1, None)

        layout = self._get_tracks_layout()
        pps = self.get_pixels_per_sec()
        lane_h = layout["lane_h"]

        # 1. Check CC Subtitles Track lanes
        if self.subtitles and self.is_cc_visible:
            cc_y = layout["cc_y"]
            cc_lane_map = layout["cc_lane_map"]
            for idx, sub in enumerate(self.subtitles):
                lane = cc_lane_map.get(idx, 0)
                item_y = cc_y + 3 + lane * lane_h
                item_h = lane_h - 6
                if item_y - 2 <= pos_y <= item_y + item_h + 2:
                    s = float(sub.get("start", 0.0))
                    e = float(sub.get("end", 0.0))
                    bx = self.HEADER_W + int(s * pps - self.offset_x)
                    bw = max(14, int((e - s) * pps))
                    if bx - 6 <= pos_x <= bx + bw + 6:
                        self._hit_track = "cc"
                        if pos_x <= bx + 16 or abs(pos_x - bx) <= 6:
                            return (idx, "left_edge")
                        if pos_x >= bx + bw - 16 or abs(pos_x - (bx + bw)) <= 6:
                            return (idx, "right_edge")
                        return (idx, "body")

        # 2. Check Audio Voice Dubbing & Dropped Music Track lanes
        audio_items = self._get_audio_items_for_timeline()
        if audio_items:
            a_y = layout["a_y"]
            a_lane_map = layout["a_lane_map"]
            for idx, a_it in enumerate(audio_items):
                lane = a_lane_map.get(idx, 0)
                item_y = a_y + 3 + lane * lane_h
                item_h = lane_h - 6
                if item_y - 2 <= pos_y <= item_y + item_h + 2:
                    s = a_it["start"]
                    e = a_it["end"]
                    ax = self.HEADER_W + int(s * pps - self.offset_x)
                    aw = max(14, int((e - s) * pps))
                    if ax - 6 <= pos_x <= ax + aw + 6:
                        self._hit_track = "audio"
                        if pos_x <= ax + 16 or abs(pos_x - ax) <= 6:
                            return (idx, "left_edge")
                        if pos_x >= ax + aw - 16 or abs(pos_x - (ax + aw)) <= 6:
                            return (idx, "right_edge")
                        return (idx, "body")

        # 3. Check Overlays & Blur FX Track lanes
        if self.overlay_clips and self.is_overlay_visible:
            ov_y = layout["ov_y"]
            ov_lane_map = layout["ov_lane_map"]
            for idx, item in enumerate(self.overlay_clips):
                lane = ov_lane_map.get(idx, 0)
                item_y = ov_y + 3 + lane * lane_h
                item_h = lane_h - 6
                if item_y - 2 <= pos_y <= item_y + item_h + 2:
                    st, et = self._get_overlay_time_span(item)
                    bx = self.HEADER_W + int(st * pps - self.offset_x)
                    bw = max(14, int((et - st) * pps))
                    if bx - 6 <= pos_x <= bx + bw + 6:
                        self._hit_track = "overlay"
                        if pos_x <= bx + 16 or abs(pos_x - bx) <= 6:
                            return (idx, "left_edge")
                        if pos_x >= bx + bw - 16 or abs(pos_x - (bx + bw)) <= 6:
                            return (idx, "right_edge")
                        return (idx, "body")

        return (-1, None)

    def mousePressEvent(self, event):
        self.setFocus()
        pos_x = int(event.position().x() if hasattr(event, "position") else event.pos().x())
        pos_y = int(event.position().y() if hasattr(event, "position") else event.pos().y())
        pps = self.get_pixels_per_sec()
        click_t = max(0.0, (pos_x - self.HEADER_W + self.offset_x) / pps)

        layout = self._get_tracks_layout()
        cc_y = layout["cc_y"]
        a_y = layout["a_y"]

        if event.button() == Qt.MouseButton.LeftButton:
            # Check Vertical Scrollbar click / drag
            bar_rect, thumb_rect = self._get_v_scrollbar_rect()
            if bar_rect and thumb_rect:
                if thumb_rect.contains(pos_x, pos_y):
                    self._is_dragging_v_scrollbar = True
                    self._v_scrollbar_drag_start_y = pos_y
                    self._v_scrollbar_drag_start_offset_y = self.offset_y
                    return
                elif bar_rect.contains(pos_x, pos_y):
                    ratio = (pos_y - bar_rect.y()) / float(bar_rect.height())
                    max_scroll_y = layout.get("max_scroll_y", 0)
                    self.offset_y = max(0, min(max_scroll_y, int(ratio * max_scroll_y)))
                    self.update()
                    return

            # 1. Left Track Header Buttons Clicked
            if pos_x < self.HEADER_W:
                btn_rects = self._get_header_button_rects()
                pt = QPoint(pos_x, pos_y)
                if btn_rects["video_eye"].contains(pt):
                    self.toggle_video_visibility()
                    return
                elif btn_rects["cc_eye"].contains(pt):
                    self.toggle_cc_visibility()
                    return
                elif btn_rects["audio_speaker"].contains(pt):
                    self.toggle_audio_mute()
                    return
                elif btn_rects["overlay_eye"].contains(pt):
                    self.toggle_overlay_visibility()
                # 1b. Check if clicked on a Video Keyframe Diamond!
            kf_idx, kf = self._hit_test_keyframe(pos_x, pos_y)
            if kf_idx >= 0:
                self.active_kf_idx = kf_idx
                self._interaction_mode = "move_keyframe"
                self._drag_start_x = pos_x
                self._orig_kf_time = float(kf.get("time", 0.0))
                self._seek_from_x(pos_x, scrubbing=False)
                self.keyframe_selected.emit(kf)
                self.update()
                return

            clip_idx, hit_part = self._hit_test_clip(pos_x, pos_y)

            # Handle Overlays & Blur FX Track click
            if self._hit_track == "overlay" and 0 <= clip_idx < len(self.overlay_clips):
                self.active_overlay_idx = clip_idx
                item = self.overlay_clips[clip_idx]
                st, et = self._get_overlay_time_span(item)
                self._orig_clip_start = st
                self._orig_clip_end = et
                self._drag_start_x = pos_x
                self._has_clip_changed = False
                if hit_part == "left_edge":
                    self._interaction_mode = "trim_overlay_start"
                    self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
                elif hit_part == "right_edge":
                    self._interaction_mode = "trim_overlay_end"
                    self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
                else:
                    self._interaction_mode = "move_overlay"
                    self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
                self.overlay_selected.emit(item)
                self.update()
                return

            # Handle Audio Voice Dubbing & Dropped Music Track click
            audio_items = self._get_audio_items_for_timeline()
            if self._hit_track == "audio" and audio_items and 0 <= clip_idx < len(audio_items):
                a_it = audio_items[clip_idx]
                self._active_audio_item = a_it
                self._active_clip_idx = clip_idx
                self._drag_start_x = pos_x
                self._orig_clip_start = float(a_it["start"])
                self._orig_clip_end = float(a_it["end"])
                self._has_clip_changed = False
                if hit_part == "left_edge":
                    self._interaction_mode = "trim_audio_start"
                    self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
                elif hit_part == "right_edge":
                    self._interaction_mode = "trim_audio_end"
                    self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
                else:
                    self._interaction_mode = "move_audio"
                    self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
                if a_it.get("is_track"):
                    self._active_audio_track_idx = a_it.get("track_idx", -1)
                else:
                    self._active_audio_track_idx = -1
                if not a_it.get("is_track") and a_it.get("sub_idx", -1) >= 0:
                    s_i = a_it["sub_idx"]
                    self.selected_indices = {s_i}
                    self.active_sub_idx = s_i
                    if self.on_select_sub:
                        self.on_select_sub(s_i)
                self.audio_selected.emit(a_it)
                self.update()
                return

            if hit_part in ("left_edge", "right_edge"):
                self._interaction_mode = "trim_start" if hit_part == "left_edge" else "trim_end"
                self._active_clip_idx = clip_idx
                self._drag_start_x = pos_x
                if 0 <= clip_idx < len(self.subtitles):
                    sub = self.subtitles[clip_idx]
                    self._orig_clip_start = float(sub.get("start", 0.0))
                    self._orig_clip_end = float(sub.get("end", 0.0))
                    self._has_clip_changed = False
                    self.selected_indices = {clip_idx}
                    self.active_sub_idx = clip_idx
                    if self.on_select_sub:
                        self.on_select_sub(clip_idx)
                    if self.on_select_multiple_subs:
                        self.on_select_multiple_subs([clip_idx])
                    self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
                    self.update()
                return

            elif hit_part == "body":
                self._interaction_mode = "move"
                self._active_clip_idx = clip_idx
                self._drag_start_x = pos_x
                self._has_clip_changed = False

                is_ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
                is_shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)

                if is_ctrl:
                    if clip_idx in self.selected_indices:
                        self.selected_indices.remove(clip_idx)
                    else:
                        self.selected_indices.add(clip_idx)
                    self._pressed_was_already_selected = False
                elif is_shift and self.active_sub_idx >= 0:
                    start_i = min(self.active_sub_idx, clip_idx)
                    end_i = max(self.active_sub_idx, clip_idx)
                    self.selected_indices = set(range(start_i, end_i + 1))
                    self._pressed_was_already_selected = False
                else:
                    if clip_idx in self.selected_indices and len(self.selected_indices) > 1:
                        # Keep selection so user can drag all selected items together
                        self._pressed_was_already_selected = True
                    else:
                        self.selected_indices = {clip_idx}
                        self._pressed_was_already_selected = False

                self.active_sub_idx = clip_idx if clip_idx in self.selected_indices else (min(self.selected_indices) if self.selected_indices else -1)
                if self.on_select_sub and self.active_sub_idx >= 0:
                    self.on_select_sub(self.active_sub_idx)
                if self.on_select_multiple_subs:
                    self.on_select_multiple_subs(list(self.selected_indices))

                self._orig_positions = {
                    i: (float(self.subtitles[i].get("start", 0.0)), float(self.subtitles[i].get("end", 0.0)))
                    for i in self.selected_indices if 0 <= i < len(self.subtitles)
                }
                self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
                self.update()
                return

            else:
                if pos_y <= 24:
                    self._interaction_mode = "scrub_playhead"
                    self._dragging_playhead = True
                    if not (event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)):
                        self.selected_indices.clear()
                        self.active_sub_idx = -1
                        if self.on_select_multiple_subs:
                            self.on_select_multiple_subs([])
                    self._seek_from_x(pos_x, scrubbing=False)
                    self.update()
                else:
                    self._interaction_mode = "marquee_select"
                    self._marquee_active = True
                    self._marquee_start_pos = QPoint(pos_x, pos_y)
                    self._marquee_current_pos = QPoint(pos_x, pos_y)
                    is_additive = bool(event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier))
                    if is_additive:
                        self._marquee_orig_selected = set(self.selected_indices)
                    else:
                        self._marquee_orig_selected = set()
                        self.selected_indices.clear()
                        self.active_sub_idx = -1
                        if self.on_select_multiple_subs:
                            self.on_select_multiple_subs([])
                    self.update()

        elif event.button() == Qt.MouseButton.RightButton:
            # Check if right-clicked on keyframe diamond
            kf_idx, kf = self._hit_test_keyframe(pos_x, pos_y)
            global_pos = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
            if kf_idx >= 0:
                menu = QMenu(self)
                menu.setStyleSheet("""
                    QMenu { background-color: #1a202c; border: 1px solid #2d3748; color: #e2e8f0; padding: 4px; border-radius: 6px; }
                    QMenu::item:selected { background-color: #0284c7; }
                """)
                menu.addAction(f"◆ Video Keyframe at {format_timestamp(kf['time'])}").setEnabled(False)
                menu.addSeparator()
                menu.addAction("🗑️ Delete Keyframe (លុប Keyframe)").triggered.connect(lambda: self._delete_keyframe_at_idx(kf_idx))
                menu.exec(global_pos)
                return

            # Check if right-clicked on Video Track empty area
            if layout["v_y"] <= pos_y <= layout["v_y"] + layout["v_h"]:
                menu = QMenu(self)
                menu.setStyleSheet("""
                    QMenu { background-color: #1a202c; border: 1px solid #2d3748; color: #e2e8f0; padding: 4px; border-radius: 6px; }
                    QMenu::item:selected { background-color: #0284c7; }
                """)
                menu.addAction("🎬 Video Track Options").setEnabled(False)
                menu.addSeparator()
                menu.addAction("◆ Add Video Keyframe at Playhead").triggered.connect(lambda: self.keyframe_added.emit(self.current_time))
                menu.exec(global_pos)
                return

            clip_idx, _ = self._hit_test_clip(pos_x, pos_y)
            if getattr(self, "_hit_track", "") == "overlay" and 0 <= clip_idx < len(self.overlay_clips):
                self._show_overlay_context_menu(clip_idx, global_pos)
            elif getattr(self, "_hit_track", "") == "audio":
                audio_items = self._get_audio_items_for_timeline()
                if audio_items and 0 <= clip_idx < len(audio_items):
                    self._show_audio_context_menu(audio_items[clip_idx], global_pos)
                else:
                    self._show_empty_context_menu(click_t, global_pos)
            elif clip_idx >= 0 and clip_idx < len(self.subtitles):
                if clip_idx not in self.selected_indices:
                    self.selected_indices = {clip_idx}
                    self.active_sub_idx = clip_idx
                    if self.on_select_sub:
                        self.on_select_sub(clip_idx)
                    if self.on_select_multiple_subs:
                        self.on_select_multiple_subs(list(self.selected_indices))
                    self.update()

                if self.on_context_menu:
                    self.on_context_menu(clip_idx, global_pos)
            else:
                self._show_empty_context_menu(click_t, global_pos)

    def mouseMoveEvent(self, event):
        pos_x = int(event.position().x() if hasattr(event, "position") else event.pos().x())
        pos_y = int(event.position().y() if hasattr(event, "position") else event.pos().y())
        pps = self.get_pixels_per_sec()

        # Handle Vertical Scrollbar dragging
        if getattr(self, "_is_dragging_v_scrollbar", False):
            dy = pos_y - self._v_scrollbar_drag_start_y
            bar_rect, thumb_rect = self._get_v_scrollbar_rect()
            if bar_rect and thumb_rect:
                bar_travel = max(1, bar_rect.height() - thumb_rect.height())
                layout = self._get_tracks_layout()
                max_scroll_y = layout.get("max_scroll_y", 0)
                d_offset = int((dy / float(bar_travel)) * max_scroll_y)
                self.offset_y = max(0, min(max_scroll_y, self._v_scrollbar_drag_start_offset_y + d_offset))
                self.update()
                return

        # Handle header button hover
        if pos_x < self.HEADER_W:
            btn_rects = self._get_header_button_rects()
            pt = QPoint(pos_x, pos_y)
            matched_btn = None
            for name, rect in btn_rects.items():
                if rect.contains(pt):
                    matched_btn = name
                    break

            if matched_btn != self._hovered_header_btn:
                self._hovered_header_btn = matched_btn
                self.update()

            global_pt = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
            if matched_btn == "video_eye":
                self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                QToolTip.showText(global_pt, "👁️ បិទ/បើក បង្ហាញ Master Video Track", self)
            elif matched_btn == "cc_eye":
                self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                QToolTip.showText(global_pt, "👁️ បិទ/បើក បង្ហាញ CC Subtitles Track", self)
            elif matched_btn == "audio_speaker":
                self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                QToolTip.showText(global_pt, "🔊 Mute / Unmute Audio Voice Dub Track", self)
            elif matched_btn == "overlay_eye":
                self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                QToolTip.showText(global_pt, "👁️ បិទ/បើក បង្ហាញ Overlays & Shapes Track", self)
            else:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            return
        else:
            if self._hovered_header_btn is not None:
                self._hovered_header_btn = None
                self.update()

        if self._interaction_mode == "marquee_select":
            self._marquee_current_pos = QPoint(pos_x, pos_y)
            rect = QRect(self._marquee_start_pos, self._marquee_current_pos).normalized()

            layout = self._get_tracks_layout()
            cc_y = layout["cc_y"]
            cc_lane_map = layout["cc_lane_map"]
            lane_h = layout["lane_h"]

            hit_subs = set()
            for idx, sub in enumerate(self.subtitles):
                lane = cc_lane_map.get(idx, 0)
                item_y = cc_y + 3 + lane * lane_h
                item_h = lane_h - 6
                s = float(sub.get("start", 0.0))
                e = float(sub.get("end", 0.0))
                bx = self.HEADER_W + int(s * pps - self.offset_x)
                bw = max(14, int((e - s) * pps))
                clip_rect = QRect(bx, item_y, bw, item_h)
                if rect.intersects(clip_rect):
                    hit_subs.add(idx)

            self.selected_indices = self._marquee_orig_selected | hit_subs
            if self.selected_indices:
                self.active_sub_idx = min(self.selected_indices)
            else:
                self.active_sub_idx = -1
            self.update()
            return

        if self._interaction_mode == "scrub_playhead":
            self._seek_from_x(pos_x, scrubbing=True)
            return

        elif self._interaction_mode == "move":
            delta_x = pos_x - self._drag_start_x
            if abs(delta_x) > 3:
                self._pressed_was_already_selected = False
            delta_t = delta_x / pps

            if self._orig_positions:
                min_start = min(s for s, e in self._orig_positions.values())
                if min_start + delta_t < 0:
                    delta_t = -min_start

                for idx, (orig_s, orig_e) in self._orig_positions.items():
                    if 0 <= idx < len(self.subtitles):
                        dur = orig_e - orig_s
                        new_s = max(0.0, round(orig_s + delta_t, 3))
                        new_e = round(new_s + dur, 3)
                        self.subtitles[idx]["start"] = new_s
                        self.subtitles[idx]["end"] = new_e

                self._has_clip_changed = True

                if 0 <= self._active_clip_idx < len(self.subtitles):
                    act_sub = self.subtitles[self._active_clip_idx]
                    global_pt = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
                    count_sel = len(self._orig_positions)
                    if count_sel > 1:
                        t_info = f"↔️ Move ({count_sel} Clips): {format_timestamp(act_sub['start']).split(',')[0]} ➔ {format_timestamp(act_sub['end']).split(',')[0]}"
                    else:
                        t_info = f"↔️ Move: {format_timestamp(act_sub['start']).split(',')[0]} ➔ {format_timestamp(act_sub['end']).split(',')[0]}"
                    QToolTip.showText(global_pt, t_info, self)
                    self._seek_from_x(self.HEADER_W + int(act_sub["start"] * pps - self.offset_x))

                self.update()
            return

        elif self._interaction_mode == "trim_start":
            delta_x = pos_x - self._drag_start_x
            delta_t = delta_x / pps

            if 0 <= self._active_clip_idx < len(self.subtitles):
                sub = self.subtitles[self._active_clip_idx]
                max_s = self._orig_clip_end - 0.15
                new_s = max(0.0, min(max_s, round(self._orig_clip_start + delta_t, 3)))
                sub["start"] = new_s
                self._has_clip_changed = True

                global_pt = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
                dur = sub["end"] - new_s
                QToolTip.showText(global_pt, f"✂️ Trim Start: {format_timestamp(new_s)} (Dur: {dur:.2f}s)", self)
                self._seek_from_x(self.HEADER_W + int(new_s * pps - self.offset_x))
                self.update()
            return

        elif self._interaction_mode == "trim_end":
            delta_x = pos_x - self._drag_start_x
            delta_t = delta_x / pps

            if 0 <= self._active_clip_idx < len(self.subtitles):
                sub = self.subtitles[self._active_clip_idx]
                min_e = self._orig_clip_start + 0.15
                new_e = max(min_e, round(self._orig_clip_end + delta_t, 3))
                sub["end"] = new_e
                self._has_clip_changed = True

                global_pt = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
                dur = new_e - sub["start"]
                QToolTip.showText(global_pt, f"✂️ Trim End: {format_timestamp(new_e)} (Dur: {dur:.2f}s)", self)
                self._seek_from_x(self.HEADER_W + int(new_e * pps - self.offset_x))
                self.update()
            return

        elif self._interaction_mode == "move_overlay":
            delta_x = pos_x - self._drag_start_x
            delta_t = delta_x / pps
            if 0 <= self.active_overlay_idx < len(self.overlay_clips):
                item = self.overlay_clips[self.active_overlay_idx]
                dur = self._orig_clip_end - self._orig_clip_start
                new_s = max(0.0, round(self._orig_clip_start + delta_t, 3))
                new_e = round(new_s + dur, 3)
                self._set_overlay_time_span(item, new_s, new_e)
                self._has_clip_changed = True
                global_pt = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
                _, iname = self._get_overlay_info(item)
                QToolTip.showText(global_pt, f"↔️ Move Overlay ({iname}): {format_timestamp(new_s).split(',')[0]} ➔ {format_timestamp(new_e).split(',')[0]}", self)
                self.overlays_modified.emit()
                self.update()
            return

        elif self._interaction_mode == "trim_overlay_start":
            delta_x = pos_x - self._drag_start_x
            delta_t = delta_x / pps
            if 0 <= self.active_overlay_idx < len(self.overlay_clips):
                item = self.overlay_clips[self.active_overlay_idx]
                max_s = self._orig_clip_end - 0.2
                new_s = max(0.0, min(max_s, round(self._orig_clip_start + delta_t, 3)))
                self._set_overlay_time_span(item, new_s, self._orig_clip_end)
                self._has_clip_changed = True
                global_pt = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
                dur = self._orig_clip_end - new_s
                QToolTip.showText(global_pt, f"✂️ Trim Overlay Start: {format_timestamp(new_s)} (Dur: {dur:.2f}s)", self)
                self.overlays_modified.emit()
                self.update()
            return

        elif self._interaction_mode == "trim_overlay_end":
            delta_x = pos_x - self._drag_start_x
            delta_t = delta_x / pps
            if 0 <= self.active_overlay_idx < len(self.overlay_clips):
                item = self.overlay_clips[self.active_overlay_idx]
                min_e = self._orig_clip_start + 0.2
                new_e = max(min_e, round(self._orig_clip_end + delta_t, 3))
                self._set_overlay_time_span(item, self._orig_clip_start, new_e)
                self._has_clip_changed = True
                global_pt = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
                dur = new_e - self._orig_clip_start
                QToolTip.showText(global_pt, f"✂️ Trim Overlay End: {format_timestamp(new_e)} (Dur: {dur:.2f}s)", self)
                self.overlays_modified.emit()
                self.update()
            return

        elif self._interaction_mode == "move_audio" and hasattr(self, "_active_audio_item") and self._active_audio_item:
            delta_x = pos_x - self._drag_start_x
            delta_t = delta_x / pps
            a_it = self._active_audio_item
            dur = self._orig_clip_end - self._orig_clip_start
            new_s = max(0.0, round(self._orig_clip_start + delta_t, 3))
            new_e = round(new_s + dur, 3)
            if a_it.get("is_track"):
                a_it["raw"]["start"] = new_s
                a_it["raw"]["end"] = new_e
                self._has_clip_changed = True
                self.update()
            elif a_it.get("sub_idx", -1) >= 0:
                s_i = a_it["sub_idx"]
                self.subtitles[s_i]["start"] = new_s
                self.subtitles[s_i]["end"] = new_e
                self._has_clip_changed = True
                self.update()
            global_pt = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
            t_info = f"↔️ Move Audio ({a_it['name'][:16]}): {format_timestamp(new_s).split(',')[0]} ➔ {format_timestamp(new_e).split(',')[0]}"
            QToolTip.showText(global_pt, t_info, self)
            return

        elif self._interaction_mode == "trim_audio_start" and hasattr(self, "_active_audio_item") and self._active_audio_item:
            delta_x = pos_x - self._drag_start_x
            delta_t = delta_x / pps
            a_it = self._active_audio_item
            new_s = max(0.0, min(self._orig_clip_end - 0.2, round(self._orig_clip_start + delta_t, 3)))
            if a_it.get("is_track"):
                a_it["raw"]["start"] = new_s
                self._has_clip_changed = True
                self.update()
            elif a_it.get("sub_idx", -1) >= 0:
                s_i = a_it["sub_idx"]
                self.subtitles[s_i]["start"] = new_s
                self._has_clip_changed = True
                self.update()
            global_pt = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
            QToolTip.showText(global_pt, f"✂️ Trim Audio Start: {format_timestamp(new_s)}", self)
            return

        elif self._interaction_mode == "trim_audio_end" and hasattr(self, "_active_audio_item") and self._active_audio_item:
            delta_x = pos_x - self._drag_start_x
            delta_t = delta_x / pps
            a_it = self._active_audio_item
            new_e = max(self._orig_clip_start + 0.2, round(self._orig_clip_end + delta_t, 3))
            if a_it.get("is_track"):
                a_it["raw"]["end"] = new_e
                self._has_clip_changed = True
                self.update()
            elif a_it.get("sub_idx", -1) >= 0:
                s_i = a_it["sub_idx"]
                self.subtitles[s_i]["end"] = new_e
                self._has_clip_changed = True
                self.update()
            global_pt = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
            QToolTip.showText(global_pt, f"✂️ Trim Audio End: {format_timestamp(new_e)}", self)
            return

        elif self._interaction_mode == "move_keyframe" and 0 <= getattr(self, "active_kf_idx", -1) < len(getattr(self, "video_keyframes", [])):
            delta_x = pos_x - self._drag_start_x
            delta_t = delta_x / pps
            new_t = max(0.0, min(self.duration, round(self._orig_kf_time + delta_t, 3)))
            kf = self.video_keyframes[self.active_kf_idx]
            kf["time"] = new_t
            self.video_keyframes.sort(key=lambda x: float(x.get("time", 0.0)))
            self.active_kf_idx = self.video_keyframes.index(kf)
            self._has_clip_changed = True
            self.keyframe_moved.emit(self.active_kf_idx, new_t)
            self.keyframes_modified.emit(self.video_keyframes)
            self._seek_from_x(pos_x, scrubbing=True)
            global_pt = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
            QToolTip.showText(global_pt, f"◆ Video Keyframe: {format_timestamp(new_t)}", self)
            self.update()
            return

        # Check keyframe diamond hover
        kf_idx, kf = self._hit_test_keyframe(pos_x, pos_y)
        if kf_idx >= 0:
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            kt = float(kf.get("time", 0.0))
            sc = float(kf.get("scale", 1.0))
            global_pt = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
            QToolTip.showText(global_pt, f"◆ Keyframe at {format_timestamp(kt)} (Zoom: {sc:.2f}x)", self)
            return

        clip_idx, hit_part = self._hit_test_clip(pos_x, pos_y)
        if hit_part in ("left_edge", "right_edge"):
            self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
        elif hit_part == "body":
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        elif pos_y <= 24:
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.CrossCursor))

    def mouseReleaseEvent(self, event):
        if getattr(self, "_is_dragging_v_scrollbar", False):
            self._is_dragging_v_scrollbar = False
            self.update()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            QToolTip.hideText()

            if self._interaction_mode == "marquee_select":
                dist = (self._marquee_current_pos - self._marquee_start_pos).manhattanLength()
                self._marquee_active = False
                self._interaction_mode = None
                if dist <= 4:
                    self._seek_from_x(self._marquee_start_pos.x(), scrubbing=False)
                    if not (event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)):
                        self.selected_indices.clear()
                        self.active_sub_idx = -1
                
                if self.selected_indices:
                    self.active_sub_idx = min(self.selected_indices)
                    if self.on_select_sub:
                        self.on_select_sub(self.active_sub_idx)
                if self.on_select_multiple_subs:
                    self.on_select_multiple_subs(list(self.selected_indices))
                self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
                self.update()
                return

            if self._interaction_mode == "move" and getattr(self, "_pressed_was_already_selected", False) and not self._has_clip_changed:
                if 0 <= self._active_clip_idx < len(self.subtitles):
                    self.selected_indices = {self._active_clip_idx}
                    self.active_sub_idx = self._active_clip_idx
                    if self.on_select_sub:
                        self.on_select_sub(self._active_clip_idx)
                    if self.on_select_multiple_subs:
                        self.on_select_multiple_subs([self._active_clip_idx])
            self._pressed_was_already_selected = False

            if self._has_clip_changed:
                if self._interaction_mode in ("move_audio", "trim_audio_start", "trim_audio_end"):
                    self.audio_tracks_modified.emit()
                    if hasattr(self, "on_subtitles_modified") and self.on_subtitles_modified:
                        self.on_subtitles_modified()
                elif self.subtitles:
                    selected_objects = [self.subtitles[i] for i in self.selected_indices if 0 <= i < len(self.subtitles)]
                    self.subtitles.sort(key=lambda x: float(x.get("start", 0.0)))
                    new_selected = set()
                    for obj in selected_objects:
                        if obj in self.subtitles:
                            new_selected.add(self.subtitles.index(obj))
                    self.selected_indices = new_selected
                    if new_selected:
                        self.active_sub_idx = min(new_selected)

                    self.subtitles_modified.emit()
                    if hasattr(self, "on_subtitles_modified") and self.on_subtitles_modified:
                        self.on_subtitles_modified()

            was_scrubbing_playhead = self._dragging_playhead or (self._interaction_mode == "scrub_playhead")
            if was_scrubbing_playhead:
                pos_x = int(event.position().x() if hasattr(event, "position") else event.pos().x())
                self._seek_from_x(pos_x, scrubbing=False)

            self._interaction_mode = None
            self._dragging_playhead = False
            self._has_clip_changed = False
            self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
            self.update()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos_x = int(event.position().x() if hasattr(event, "position") else event.pos().x())
            pos_y = int(event.position().y() if hasattr(event, "position") else event.pos().y())
            clip_idx, _ = self._hit_test_clip(pos_x, pos_y)

            # 1. Double Click on Audio Voice Dubbing or Music Track -> Open CapCut Voice Effects Studio!
            if getattr(self, "_hit_track", "") == "audio":
                audio_items = self._get_audio_items_for_timeline()
                if audio_items and 0 <= clip_idx < len(audio_items):
                    a_it = audio_items[clip_idx]
                    st = float(a_it.get("start", 0.0))
                    if self.on_seek:
                        self.on_seek(st)
                    from ui_v_PyQt6.components.timeline.capcut_voice_dialog import CapCutVoiceDialog
                    dlg = CapCutVoiceDialog(a_it, parent=self.window() or self)
                    if dlg.exec():
                        if getattr(dlg, "apply_scope", "clip") in ("character", "all"):
                            win = self.window()
                            if hasattr(win, "apply_batch_voice_effect"):
                                win.apply_batch_voice_effect(
                                    fx_key=dlg.selected_effect,
                                    scope=dlg.apply_scope,
                                    target_char=dlg.target_character
                                )
                        if a_it.get("is_track"):
                            self.audio_tracks_modified.emit()
                        else:
                            if hasattr(self, "on_subtitles_modified") and self.on_subtitles_modified:
                                self.on_subtitles_modified()
                        self.audio_selected.emit(a_it)
                        self.update()
                    return

            # 2. Double Click on Subtitles CC Track -> Edit Dialogue Text
            elif 0 <= clip_idx < len(self.subtitles):
                sub = self.subtitles[clip_idx]
                st = float(sub.get("start", 0.0))
                if self.on_seek:
                    self.on_seek(st)

                cur_km = sub.get("khmer_text") or sub.get("orig_text") or sub.get("text", "")
                time_str = f"{format_timestamp(sub.get('start', 0.0))} ➔ {format_timestamp(sub.get('end', 0.0))}"

                new_text, ok = QInputDialog.getMultiLineText(
                    self,
                    f"📝 កែសម្រួលអត្ថបទបន្ទាត់ #{clip_idx + 1}",
                    f"⏱️ ពេលវេលា: {time_str}\n\nបញ្ចូលអត្ថបទខ្មែរ (Khmer Dialogue):",
                    cur_km
                )
                if ok and new_text.strip():
                    sub["khmer_text"] = new_text.strip()
                    sub["status"] = "edited"
                    self.subtitles_modified.emit()
                    if hasattr(self, "on_subtitles_modified") and self.on_subtitles_modified:
                        self.on_subtitles_modified()
                    self.update()
            else:
                layout = self._get_tracks_layout()
                pps = self.get_pixels_per_sec()
                click_t = max(0.0, min(self.duration, round((pos_x - self.HEADER_W + self.offset_x) / pps, 3)))
                if layout["v_y"] <= pos_y <= layout["v_y"] + layout["v_h"] and pos_x >= self.HEADER_W:
                    self.keyframe_added.emit(click_t)
                    self.update()
                    return
                elif self.on_add_sub_at_time:
                    self.on_add_sub_at_time(click_t)

    def _get_player_canvas(self):
        """Resolves the player canvas reliably from window, parent hierarchy, or application widgets."""
        w = self.window()
        if w and hasattr(w, "player_view") and hasattr(w.player_view, "canvas"):
            return w.player_view.canvas

        p = self.parent()
        while p:
            if hasattr(p, "player_view") and hasattr(p.player_view, "canvas"):
                return p.player_view.canvas
            if hasattr(p, "canvas") and hasattr(p.canvas, "add_image_item"):
                return p.canvas
            p = p.parent()

        from ui_v_PyQt6.qt_compat import QApplication
        for top in QApplication.topLevelWidgets():
            if hasattr(top, "player_view") and hasattr(top.player_view, "canvas"):
                return top.player_view.canvas
        return None

    def add_audio_track(self, file_path: str, start_time: float = 0.0) -> dict:
        """Adds an independent audio track (MP3, WAV, etc.) to the Timeline with duration probe."""
        if not file_path or not os.path.exists(file_path):
            return None
        from utils.media_utils import get_video_info
        info = get_video_info(file_path)
        a_dur = float(info.get("duration", 0.0) or 5.0)
        if a_dur < 0.1:
            a_dur = 5.0

        st = max(0.0, float(start_time))
        entry = {
            "id": f"aud_{int(time.time()*1000)}",
            "name": os.path.basename(file_path),
            "path": file_path,
            "start": round(st, 3),
            "end": round(st + a_dur, 3),
            "duration": round(a_dur, 3),
            "volume": 1.0,
            "speed": 1.0,
            "is_bgm": True
        }
        self.audio_tracks.append(entry)
        if st + a_dur > self.duration:
            self.duration = round(st + a_dur, 3)
        self.audio_tracks_modified.emit()
        self.audio_dropped.emit(file_path)
        if hasattr(self, "on_audio_dropped") and self.on_audio_dropped:
            self.on_audio_dropped(file_path)
        self.update()
        return entry

    def add_image_overlay(self, file_path: str, start_time: float = 0.0):
        """Adds an image, sticker, or animated GIF overlay at the given timeline time."""
        canvas = self._get_player_canvas()
        if not canvas:
            return None
        st = max(0.0, float(start_time))
        item = canvas.add_image_item(file_path)
        if item:
            item.start_time = round(st, 3)
            item.end_time = round(st + 5.0, 3)
            canvas.canvas_modified.emit()
            canvas.update()
            self.overlays_modified.emit()
            self.update()
        return item

    def add_video_overlay(self, file_path: str, start_time: float = 0.0):
        """Adds a Picture-in-Picture (PiP) video clip overlay at the given timeline time."""
        canvas = self._get_player_canvas()
        if not canvas:
            return None
        st = max(0.0, float(start_time))
        item = canvas.add_video_item(file_path)
        if item:
            item.start_time = round(st, 3)
            item.end_time = round(st + 5.0, 3)
            canvas.canvas_modified.emit()
            canvas.update()
            self.overlays_modified.emit()
            self.update()
        return item

    def _show_audio_context_menu(self, a_it: dict, global_pos):
        """Right-click context menu for adjusting volume, speed, and removal of audio tracks."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1a202c;
                border: 1px solid #2d3748;
                border-radius: 6px;
                padding: 4px;
                color: #e2e8f0;
            }
            QMenu::item {
                padding: 6px 14px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #0284c7;
                color: #ffffff;
            }
        """)

        title = a_it.get("name", "Audio Track")
        menu.addAction(f"🎵 Audio: {title[:25]}").setEnabled(False)
        menu.addSeparator()

        # 1. CapCut Voice Effects Studio Dialog
        def _open_capcut_dialog():
            from ui_v_PyQt6.components.timeline.capcut_voice_dialog import CapCutVoiceDialog
            dlg = CapCutVoiceDialog(a_it, parent=self.window() or self)
            if dlg.exec():
                if getattr(dlg, "apply_scope", "clip") in ("character", "all"):
                    win = self.window()
                    if hasattr(win, "apply_batch_voice_effect"):
                        win.apply_batch_voice_effect(
                            fx_key=dlg.selected_effect,
                            scope=dlg.apply_scope,
                            target_char=dlg.target_character
                        )
                if a_it.get("is_track"):
                    self.audio_tracks_modified.emit()
                else:
                    if hasattr(self, "on_subtitles_modified") and self.on_subtitles_modified:
                        self.on_subtitles_modified()
                self.audio_selected.emit(a_it)
                self.update()
        menu.addAction("🎛️ CapCut Voice Effects Studio (កែសំឡេង CapCut)...").triggered.connect(_open_capcut_dialog)

        # 2. Quick CapCut Voice Effects Submenu (18 presets)
        m_effects = menu.addMenu("✨ CapCut Voice Effects (កែសំឡេងភ្លាមៗ)")
        from services.dubbing.audio_effects import CAPCUT_VOICE_EFFECTS, apply_voice_effect_to_file, preview_voice_effect
        raw_dict = a_it.get("raw") if isinstance(a_it.get("raw"), dict) else a_it
        cur_fx = raw_dict.get("voice_effect", "none") or "none"

        for fx_k, fx_label, _ in CAPCUT_VOICE_EFFECTS:
            pfx = "✓ " if fx_k == cur_fx else "   "
            def _apply_fx(k=fx_k):
                raw = a_it.get("raw") if isinstance(a_it.get("raw"), dict) else a_it
                raw["voice_effect"] = k
                a_it["voice_effect"] = k
                aud_p = raw.get("orig_path") or raw.get("path") or raw.get("orig_audio") or raw.get("audio_file") or raw.get("audio_path") or a_it.get("path")
                if aud_p and os.path.exists(aud_p):
                    if not raw.get("orig_path") and not raw.get("orig_audio"):
                        if a_it.get("is_track"):
                            raw["orig_path"] = aud_p
                        else:
                            raw["orig_audio"] = aud_p
                    orig_file = raw.get("orig_path") or raw.get("orig_audio") or aud_p
                    if k != "none":
                        new_p = apply_voice_effect_to_file(orig_file, k)
                        if a_it.get("is_track"):
                            raw["path"] = new_p
                            a_it["path"] = new_p
                        else:
                            raw["audio_file"] = new_p
                            raw["audio_path"] = new_p
                    else:
                        if a_it.get("is_track"):
                            raw["path"] = orig_file
                            a_it["path"] = orig_file
                        else:
                            raw["audio_file"] = orig_file
                            raw["audio_path"] = orig_file
                    preview_voice_effect(aud_p, k)

                if a_it.get("is_track"):
                    self.audio_tracks_modified.emit()
                else:
                    if hasattr(self, "on_subtitles_modified") and self.on_subtitles_modified:
                        self.on_subtitles_modified()
                self.audio_selected.emit(a_it)
                self.update()
            m_effects.addAction(f"{pfx}{fx_label}").triggered.connect(_apply_fx)

        # 3. Open Properties Inspector
        menu.addAction("🛠️ បើកផ្ទាំង Properties Inspector...").triggered.connect(lambda: self.audio_selected.emit(a_it))
        menu.addSeparator()

        # Volume Submenu
        m_vol = menu.addMenu("🔊 កម្រិតសំឡេង (Volume)")
        vol_presets = [
            ("25% (បន្ថយខ្លាំង)", 0.25),
            ("50% (បន្ថយពាក់កណ្តាល)", 0.50),
            ("75% (បន្ថយបន្តិច)", 0.75),
            ("100% (ធម្មតា / Normal)", 1.0),
            ("125% (បន្ថែមបន្តិច)", 1.25),
            ("150% (បន្ថែមខ្លាំង)", 1.50),
            ("200% (ទ្វេដង / Max Boost)", 2.00),
            ("🔇 Mute (បិទសំឡេង 0%)", 0.0),
        ]
        curr_vol = a_it.get("volume", 1.0)
        for label, val in vol_presets:
            prefix = "✓ " if abs(curr_vol - val) < 0.01 else "   "
            def _set_v(v=val):
                if a_it.get("is_track"):
                    a_it["raw"]["volume"] = v
                    self.audio_tracks_modified.emit()
                else:
                    sub = a_it.get("raw")
                    if sub:
                        pct = int(round((v - 1.0) * 100))
                        sub["volume"] = f"+{pct}%" if pct >= 0 else f"{pct}%"
                        if hasattr(self, "on_subtitles_modified") and self.on_subtitles_modified:
                            self.on_subtitles_modified()
                self.update()
            m_vol.addAction(f"{prefix}{label}").triggered.connect(_set_v)

        # Speed Submenu
        m_speed = menu.addMenu("⚡ ល្បឿនសំឡេង (Speech Speed)")
        speed_presets = [
            ("0.5x (Slow / យឺតខ្លាំង)", 0.5),
            ("0.75x (Slightly Slow / យឺតបន្តិច)", 0.75),
            ("1.0x (Normal / ធម្មតា)", 1.0),
            ("1.25x (Faster / លឿនបន្តិច)", 1.25),
            ("1.5x (Fast / លឿន)", 1.5),
            ("2.0x (Double Speed / លឿនទ្វេដង)", 2.0),
        ]
        curr_spd = a_it.get("speed", 1.0)
        for label, val in speed_presets:
            prefix = "✓ " if abs(curr_spd - val) < 0.01 else "   "
            def _set_s(s=val):
                if a_it.get("is_track"):
                    a_it["raw"]["speed"] = s
                    orig_dur = a_it.get("duration", 5.0)
                    a_it["raw"]["end"] = round(a_it["raw"]["start"] + (orig_dur / s), 3)
                    self.audio_tracks_modified.emit()
                else:
                    sub = a_it.get("raw")
                    if sub:
                        pct = int(round((s - 1.0) * 100))
                        sub["rate"] = f"+{pct}%" if pct >= 0 else f"{pct}%"
                        if hasattr(self, "on_subtitles_modified") and self.on_subtitles_modified:
                            self.on_subtitles_modified()
                self.update()
            m_speed.addAction(f"{prefix}{label}").triggered.connect(_set_s)

        # Dialogue Line Specific Actions (Assign Character, Play Voice, etc.)
        if not a_it.get("is_track"):
            sub = a_it.get("raw")
            s_idx = a_it.get("sub_idx", -1)

            # Character assignment submenu
            m_char = menu.addMenu("🎭 កំណត់តួអង្គ (Assign Character)")
            char_presets = [
                ("👨 តួប្រុស (Male)", "តួប្រុស (Male)", "male"),
                ("👩 តួស្រី (Female)", "តួស្រី (Female)", "female"),
                ("🧒 កូនក្មេង (Kid)", "កូនក្មេង (Kid)", "kid"),
                ("👥 តួទូទៅ (Dialogue)", "តួទូទៅ (Dialogue)", "male"),
            ]
            cur_actor = a_it.get("actor", "")
            for c_lbl, c_name, c_gender in char_presets:
                pfx = "✓ " if c_name in cur_actor else "   "
                def _set_char(cn=c_name, cg=c_gender):
                    if sub:
                        sub["actor"] = cn
                        sub["character"] = cn
                        sub["gender"] = cg
                        sub.pop("audio_file", None)
                        sub.pop("audio_path", None)
                        if hasattr(self, "on_subtitles_modified") and self.on_subtitles_modified:
                            self.on_subtitles_modified()
                        self.update()
                m_char.addAction(f"{pfx}{c_lbl}").triggered.connect(_set_char)

            def _custom_char():
                txt, ok = QInputDialog.getText(self, "Custom Character", "បញ្ចូលឈ្មោះតួអង្គ (Character Name):", text=cur_actor)
                if ok and txt.strip() and sub:
                    sub["actor"] = txt.strip()
                    sub["character"] = txt.strip()
                    sub.pop("audio_file", None)
                    sub.pop("audio_path", None)
                    if hasattr(self, "on_subtitles_modified") and self.on_subtitles_modified:
                        self.on_subtitles_modified()
                    self.update()
            m_char.addAction("✏️ ឈ្មោះតួអង្គផ្ទាល់ខ្លួន (Custom Name)...").triggered.connect(_custom_char)

            # Play audio preview
            if a_it.get("has_audio"):
                def _play_line_voice():
                    aud_path = sub.get("audio_file") or sub.get("audio_path")
                    if aud_path and os.path.exists(aud_path):
                        from utils import play_audio_file
                        play_audio_file(aud_path)
                menu.addAction("🔊 ចាក់ស្តាប់សំឡេងតួនេះ (Play Voice Line)").triggered.connect(_play_line_voice)

        menu.addSeparator()

        # Delete Audio Option (if it's a dropped audio track)
        if a_it.get("is_track"):
            def _remove_track():
                trk = a_it.get("raw")
                if trk in self.audio_tracks:
                    self.audio_tracks.remove(trk)
                    self.audio_tracks_modified.emit()
                    self.update()
            menu.addAction("🗑️ Delete Audio Track (លុបបទភ្លេង/សំឡេង)").triggered.connect(_remove_track)

        menu.exec(global_pos)

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

    def dropEvent(self, event):
        if not event.mimeData().hasUrls():
            return

        pps = self.get_pixels_per_sec()
        drop_x = int(event.position().x() if hasattr(event, "position") else event.pos().x())
        click_t = max(0.0, (drop_x - self.HEADER_W + self.offset_x) / pps)

        for url in event.mimeData().urls():
            local_path = url.toLocalFile()
            if not local_path or not os.path.exists(local_path):
                continue

            ext = os.path.splitext(local_path)[1].lower()
            if ext in [".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm", ".ts"]:
                if self.video_path and os.path.exists(self.video_path):
                    # Master video is already open -> Add dropped video as PiP video overlay clip
                    self.add_video_overlay(local_path, click_t)
                    event.acceptProposedAction()
                    break
                else:
                    self.video_dropped.emit(local_path)
                    if hasattr(self, "on_video_dropped") and self.on_video_dropped:
                        self.on_video_dropped(local_path)
                    event.acceptProposedAction()
                    break
            elif ext in [".srt", ".vtt", ".ass", ".ssa", ".txt"]:
                self.subtitle_dropped.emit(local_path)
                if hasattr(self, "on_subtitle_dropped") and self.on_subtitle_dropped:
                    self.on_subtitle_dropped(local_path)
                event.acceptProposedAction()
                break
            elif ext in [".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"]:
                # Add audio track directly to Timeline
                self.add_audio_track(local_path, click_t)
                event.acceptProposedAction()
                break
            elif ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"]:
                # Add image/sticker/GIF overlay directly to Timeline
                self.add_image_overlay(local_path, click_t)
                event.acceptProposedAction()
                break

    def _seek_from_x(self, x: int, scrubbing: bool = False):
        pixels_per_sec = self.get_pixels_per_sec()
        seek_t = (x - self.HEADER_W + self.offset_x) / pixels_per_sec
        seek_t = max(0.0, min(self.duration, seek_t))
        if self.on_seek:
            try:
                self.on_seek(seek_t, from_player=False, scrubbing=scrubbing)
            except TypeError:
                self.on_seek(seek_t)

    def _show_overlay_context_menu(self, clip_idx: int, global_pos):
        """Context menu when right-clicking on an overlay / blur box clip on Track 4."""
        if not (0 <= clip_idx < len(self.overlay_clips)):
            return
        item = self.overlay_clips[clip_idx]
        self.active_overlay_idx = clip_idx
        self.overlay_selected.emit(item)
        self.update()

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1a202c;
                border: 1px solid #2d3748;
                border-radius: 6px;
                padding: 4px;
                color: #e2e8f0;
            }
            QMenu::item {
                padding: 6px 14px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #0284c7;
                color: #ffffff;
            }
        """)

        _, name = self._get_overlay_info(item)
        menu.addAction(f"🎨 Clip: {name}").setEnabled(False)
        menu.addSeparator()

        itype = getattr(item, "item_type", "")
        if itype in ("blur_box", "blur", "mosaic", "glass", "blackout"):
            def _open_style_dlg():
                from ui_v_PyQt6.components.player.blur_style_dialog import BlurBoxStyleDialog
                canvas = None
                p = self.parent()
                while p:
                    if hasattr(p, "player_view") and hasattr(p.player_view, "canvas"):
                        canvas = p.player_view.canvas
                        break
                    p = p.parent()
                dlg = BlurBoxStyleDialog(item, canvas, self)
                dlg.exec()
                self.overlays_modified.emit()
                self.update()
            menu.addAction("🎨 Customize Style & Frosted Glass (កែសម្រួល Style & Opacity)...").triggered.connect(_open_style_dlg)
            menu.addSeparator()

        m_srt = menu.addMenu("⏱️ កំណត់ម៉ោងតាម Subtitle / SRT")

        def _snap_curr():
            cur_t = self.current_time
            if self.subtitles:
                target = None
                for s in self.subtitles:
                    if float(s.get("start", 0.0)) <= cur_t <= float(s.get("end", 0.0)):
                        target = s
                        break
                if not target:
                    target = min(self.subtitles, key=lambda s: abs(float(s.get("start", 0.0)) - cur_t))
                if target:
                    self._set_overlay_time_span(item, float(target.get("start", 0.0)), float(target.get("end", 0.0)))
                    self.overlays_modified.emit()
                    self.update()

        def _replicate_all():
            """Replicates this blur/overlay box for EVERY individual subtitle dialogue line."""
            canvas = None
            p = self.parent()
            while p:
                if hasattr(p, "player_view") and hasattr(p.player_view, "canvas"):
                    canvas = p.player_view.canvas
                    break
                p = p.parent()
            if canvas and hasattr(canvas, "replicate_selected_for_all_subtitles"):
                canvas.selected_items = [item]
                canvas.replicate_selected_for_all_subtitles()
                self.overlays_modified.emit()
                self.update()

        def _snap_all():
            """Snaps this overlay to cover the entire video timeline (0.0 to end)."""
            tot_d = float(self.duration or 3600.0)
            self._set_overlay_time_span(item, 0.0, tot_d)
            self.overlays_modified.emit()
            self.update()

        m_srt.addAction("🎯 ដាក់ម៉ោងតាម Subtitle បច្ចុប្បន្ន (Snap to Current Subtitle Line)").triggered.connect(_snap_curr)
        m_srt.addAction("⚡ បង្កើតតាមគ្រប់បន្ទាត់ Subtitles ទាំងអស់ (Sync Every Subtitle Line - មិនចេញពេលចន្លោះស្ងាត់)").triggered.connect(_replicate_all)
        m_srt.addAction("🎬 ពង្រីកគ្របដណ្ដប់ទាំងមូល (Continuous Cover All 0:00 ➔ ចុងក្រោយ)").triggered.connect(_snap_all)

        menu.addSeparator()
        def _delete_overlay():
            if item in self.overlay_clips:
                self.overlay_clips.remove(item)
                self.active_overlay_idx = -1
                self.overlays_modified.emit()
                self.update()
        menu.addAction("🗑️ Delete Clip (លុបចោល)").triggered.connect(_delete_overlay)

        menu.exec(global_pos)

    def _show_empty_context_menu(self, click_t: float, global_pos: QPoint):
        """Context menu when right-clicking on timeline with comprehensive editing tools"""
        menu = QMenu(self)
        t_str = format_timestamp(click_t).split(",")[0]

        # 1. Primary Timeline Actions
        act_split = menu.addAction(f"✂️ Split at Playhead (S) [ត្រង់ {t_str}]")
        act_split.triggered.connect(self.split_at_playhead)

        menu.addSeparator()
        act_mark_in = menu.addAction(f"📍 Set Mark In (I) [ត្រង់ {t_str}]")
        act_mark_in.triggered.connect(lambda: self.set_mark_in(click_t))

        act_mark_out = menu.addAction(f"📍 Set Mark Out (O) [ត្រង់ {t_str}]")
        act_mark_out.triggered.connect(lambda: self.set_mark_out(click_t))

        if self.mark_in is not None or self.mark_out is not None:
            act_clear_io = menu.addAction("✖ Clear In/Out Points (Alt+X)")
            act_clear_io.triggered.connect(self.clear_in_out)

        menu.addSeparator()
        act_extract = menu.addAction("🎯 Extract Selected Range (យកតែផ្នែកជ្រើស)")
        act_extract.triggered.connect(lambda: self.extract_range_requested.emit(*self.get_in_out_range()))

        act_ripple = menu.addAction("🗑️ Ripple Delete (Shift+Del / X) [លុប & បិទចន្លោះ]")
        act_ripple.triggered.connect(self.ripple_delete_selected)

        act_exp_clip = menu.addAction("🎬 Export Selected Clip / Range (Export តែមួយ)")
        act_exp_clip.triggered.connect(lambda: self.export_range_requested.emit(*self.get_in_out_range()))

        menu.addSeparator()

        # 2. Auto-Split Submenu
        m_auto_split = menu.addMenu("⏱️ Auto Split by Duration (បំបែកស្វ័យប្រវត្ត)")
        m_auto_split.addAction("⏱️ រៀងរាល់ 5 នាទី (Every 5 mins)").triggered.connect(lambda: self.auto_split_requested.emit(5.0))
        m_auto_split.addAction("⏱️ រៀងរាល់ 10 នាទី (Every 10 mins)").triggered.connect(lambda: self.auto_split_requested.emit(10.0))
        m_auto_split.addAction("⏱️ រៀងរាល់ 30 នាទី (Every 30 mins)").triggered.connect(lambda: self.auto_split_requested.emit(30.0))
        def _prompt_custom_split():
            val, ok = QInputDialog.getDouble(self, "Auto Split", "បញ្ចូលចំនួននាទី (Enter minutes per segment):", 5.0, 0.5, 300.0, 1)
            if ok and val > 0:
                self.auto_split_requested.emit(val)
        m_auto_split.addAction("⚙️ កំណត់នាទីតាមចិត្ត (Custom mins)...").triggered.connect(_prompt_custom_split)

        act_batch_exp = menu.addAction("📦 Batch Export All Segments (Export ជាច្រើន File)")
        act_batch_exp.triggered.connect(lambda: self.export_range_requested.emit(-1.0, -1.0))

        act_merge_seg = menu.addAction("🔗 Merge Selected Segments (ផ្គុំជា Video តែមួយ)")
        act_merge_seg.triggered.connect(self.merge_segments_requested.emit)

        menu.addSeparator()
        act_add = menu.addAction(f"➕ Add Subtitle Line at {t_str}")
        act_add.triggered.connect(lambda: self._on_add_line_at(click_t))

        act_sel_all = menu.addAction("✨ Select All Subtitles (Ctrl+A)")
        act_sel_all.triggered.connect(self.select_all_subtitles)

        if self.selected_indices:
            act_del_sel = menu.addAction(f"🗑️ Delete Selected Subtitles ({len(self.selected_indices)} Items) [Del]")
            act_del_sel.triggered.connect(self.delete_selected_subtitles)
            act_clear_sel = menu.addAction("❌ Deselect All (Esc)")
            act_clear_sel.triggered.connect(self.clear_selection)

        menu.addSeparator()
        m_add_media = menu.addMenu("🎬 Add Media & Overlay at this Time")

        def _get_canvas():
            p = self.parent()
            while p:
                if hasattr(p, "player_view") and hasattr(p.player_view, "canvas"):
                    return p.player_view.canvas
                p = p.parent()
            return None

        def _add_img_to_tl():
            from ui_v_PyQt6.qt_compat import QFileDialog
            path, _ = QFileDialog.getOpenFileName(
                self, "Select Image or GIF to Add", "",
                "Images & GIFs (*.png *.jpg *.jpeg *.webp *.gif *.bmp *.svg)"
            )
            if path and os.path.exists(path):
                self.add_image_overlay(path, click_t)

        def _add_glass_to_tl(mode="glass"):
            canvas = _get_canvas()
            if not canvas:
                return
            from ui_v_PyQt6.components.player.canvas_item import CanvasItem
            labels = {"glass": "Frosted Glass", "blur": "Blur Box", "mosaic": "Mosaic Censor", "blackout": "Blackout Bar"}
            new_item = CanvasItem(
                item_type="blur_box",
                x=0.5, y=0.5, w=0.35, h=0.15,
                blur_mode=mode,
                blur_strength=25,
                corner_radius=10 if mode == "glass" else 0,
                name=labels.get(mode, "Blur Box"),
                start_time=round(click_t, 3),
                end_time=round(click_t + 5.0, 3)
            )
            canvas.items.append(new_item)
            canvas.selected_items = [new_item]
            canvas.canvas_modified.emit()
            canvas.update()
            self.overlays_modified.emit()
            self.update()

        def _add_audio_to_tl():
            from ui_v_PyQt6.qt_compat import QFileDialog
            path, _ = QFileDialog.getOpenFileName(
                self, "Select Audio File to Add", "",
                "Audio Files (*.mp3 *.wav *.m4a *.aac *.ogg *.flac)"
            )
            if path and os.path.exists(path):
                self.add_audio_track(path, click_t)

        m_add_media.addAction("🖼️ Add Image / Sticker / GIF (រូបភាព/GIF)...").triggered.connect(_add_img_to_tl)
        m_add_media.addAction("✨ Add Frosted Glass Box (កញ្ចក់ព្រិល)").triggered.connect(lambda: _add_glass_to_tl("glass"))
        m_add_media.addAction("🌫️ Add Smooth Blur Box (ប្រអប់ព្រិល)").triggered.connect(lambda: _add_glass_to_tl("blur"))
        m_add_media.addAction("🔲 Add Mosaic Pixelate Box (ប្រអប់ការ៉ូ Censor)").triggered.connect(lambda: _add_glass_to_tl("mosaic"))
        m_add_media.addAction("⬛ Add Blackout Bar (បន្ទះខ្មៅបិទ Subtitle)").triggered.connect(lambda: _add_glass_to_tl("blackout"))
        m_add_media.addAction("🎵 Load Audio Soundtrack (ផ្ទុកសំឡេងចូល)...").triggered.connect(_add_audio_to_tl)

        menu.addSeparator()
        if self.on_fix_overlaps:
            act_fix = menu.addAction("🔧 Fix All Overlaps (កែបន្ទាត់ជាន់គ្នា)")
            act_fix.triggered.connect(self.on_fix_overlaps)
            menu.addSeparator()

        act_zoom_in = menu.addAction("🔍 Zoom In (+)")
        act_zoom_in.triggered.connect(lambda: self.zoom_to(self.zoom * 1.5))

        act_zoom_out = menu.addAction("🔍 Zoom Out (-)")
        act_zoom_out.triggered.connect(lambda: self.zoom_to(self.zoom / 1.5))

        act_zoom_reset = menu.addAction("🎯 Reset Zoom (1.0x Normal)")
        act_zoom_reset.triggered.connect(lambda: self.zoom_to(1.0))

        act_zoom_fit = menu.addAction("📐 Fit Entire Video to Window")
        act_zoom_fit.triggered.connect(self.fit_to_window)

        menu.addSeparator()
        act_jump_start = menu.addAction("⏮️ Jump to Start (00:00:00)")
        act_jump_start.triggered.connect(lambda: self.on_seek(0.0) if self.on_seek else None)

        menu.exec(global_pos)

    def _on_add_line_at(self, click_t: float):
        if self.on_add_sub_at_time:
            self.on_add_sub_at_time(click_t)
        elif self.on_seek:
            self.on_seek(click_t)

    def split_at_playhead(self) -> bool:
        """
        Razor Tool (Cut / Split `S` / `C` / `Ctrl+B`):
        Splits subtitle & triggers video clip cut at current playhead position.
        """
        cur_t = getattr(self, "current_time", 0.0)
        self.split_requested.emit(cur_t)

        target_idx = -1
        for i, sub in enumerate(self.subtitles):
            st = float(sub.get("start", 0.0))
            et = float(sub.get("end", st + 0.1))
            if st + 0.05 < cur_t < et - 0.05:
                target_idx = i
                break

        if target_idx >= 0:
            orig_sub = self.subtitles[target_idx]
            orig_st = float(orig_sub.get("start", 0.0))
            orig_et = float(orig_sub.get("end", orig_st + 0.1))

            part1 = dict(orig_sub)
            part1["end"] = round(cur_t, 3)

            part2 = dict(orig_sub)
            part2["start"] = round(cur_t, 3)
            part2["end"] = orig_et
            part2["index"] = target_idx + 2

            self.subtitles[target_idx] = part1
            self.subtitles.insert(target_idx + 1, part2)

            for idx, s in enumerate(self.subtitles):
                s["index"] = idx + 1

            self.subtitles_modified.emit()
            if hasattr(self, "on_subtitles_modified") and self.on_subtitles_modified:
                self.on_subtitles_modified()

        self.update()
        return True

    def ripple_delete_selected(self) -> bool:
        """
        Ripple Delete (Shift+Delete / X):
        Removes selected subtitles or Mark In/Out range, and shifts subsequent items left to close the gap.
        """
        from services.video.segment_editor import SegmentEditorService
        in_t, out_t = None, None

        if self.mark_in is not None and self.mark_out is not None and self.mark_out > self.mark_in:
            in_t, out_t = self.mark_in, self.mark_out
            self.clear_in_out()
        elif self.selected_indices:
            sel_subs = [self.subtitles[i] for i in self.selected_indices if 0 <= i < len(self.subtitles)]
            if sel_subs:
                in_t = min(float(s.get("start", 0.0)) for s in sel_subs)
                out_t = max(float(s.get("end", 0.0)) for s in sel_subs)
                self.selected_indices.clear()
        elif 0 <= self.active_sub_idx < len(self.subtitles):
            sub = self.subtitles[self.active_sub_idx]
            in_t = float(sub.get("start", 0.0))
            out_t = float(sub.get("end", in_t + 0.1))

        if in_t is None or out_t is None or out_t <= in_t:
            return False

        new_subs, new_clips, shift = SegmentEditorService.ripple_delete_range(
            self.subtitles, self.video_clips, in_t, out_t
        )
        self.subtitles = new_subs
        self.video_clips = new_clips
        self.duration = max(1.0, round(self.duration - shift, 3))
        self.subtitles_modified.emit()
        self.ripple_delete_requested.emit()
        if hasattr(self, "on_subtitles_modified") and self.on_subtitles_modified:
            self.on_subtitles_modified()
        self.update()
        return True

    def select_all_subtitles(self):
        """Selects all subtitles on timeline (Ctrl+A)."""
        if not self.subtitles:
            return
        self.selected_indices = set(range(len(self.subtitles)))
        self.active_sub_idx = 0
        if self.on_select_sub:
            self.on_select_sub(0)
        if self.on_select_multiple_subs:
            self.on_select_multiple_subs(list(self.selected_indices))
        self.update()

    def clear_selection(self):
        """Clears all subtitle selection (Esc)."""
        self.selected_indices.clear()
        self.active_sub_idx = -1
        if self.on_select_multiple_subs:
            self.on_select_multiple_subs([])
        self.update()

    def delete_selected_subtitles(self):
        """Batch deletes all currently selected subtitle clips from timeline (Delete/Backspace)."""
        if not self.selected_indices or not self.subtitles:
            return
        to_del = sorted(self.selected_indices, reverse=True)
        for idx in to_del:
            if 0 <= idx < len(self.subtitles):
                del self.subtitles[idx]
        for idx, s in enumerate(self.subtitles):
            s["index"] = idx + 1
        self.selected_indices.clear()
        self.active_sub_idx = -1
        if self.on_select_multiple_subs:
            self.on_select_multiple_subs([])
        self.subtitles_modified.emit()
        if hasattr(self, "on_subtitles_modified") and self.on_subtitles_modified:
            self.on_subtitles_modified()
        self.update()

    def keyPressEvent(self, event):
        mods = event.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        alt = bool(mods & Qt.KeyboardModifier.AltModifier)
        key = event.key()

        # 'S', 'C', or 'Ctrl+B' triggers Razor Cut (Split at playhead)
        if (key in (Qt.Key.Key_S, Qt.Key.Key_C) and not ctrl and not alt) or (ctrl and key == Qt.Key.Key_B):
            if self.split_at_playhead():
                event.accept()
                return

        # 'I' triggers Mark In
        if key == Qt.Key.Key_I and not ctrl and not alt:
            self.set_mark_in()
            event.accept()
            return

        # 'O' triggers Mark Out
        if key == Qt.Key.Key_O and not ctrl and not alt:
            self.set_mark_out()
            event.accept()
            return

        # Alt+X triggers Clear In/Out Range
        if alt and key == Qt.Key.Key_X:
            self.clear_in_out()
            event.accept()
            return

        # Shift+Delete or 'X' triggers Ripple Delete
        if (shift and key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace)) or (key == Qt.Key.Key_X and not ctrl and not alt):
            if self.ripple_delete_selected():
                event.accept()
                return

        # Ctrl+A triggers Select All Subtitles
        if ctrl and key == Qt.Key.Key_A:
            self.select_all_subtitles()
            event.accept()
            return

        # Delete or Backspace batch deletes selected clips
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and not shift:
            if self.selected_indices:
                self.delete_selected_subtitles()
                event.accept()
                return

        # Escape clears selection
        if key == Qt.Key.Key_Escape:
            if self.selected_indices:
                self.clear_selection()
                event.accept()
                return

        super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        hw = self.HEADER_W
        pixels_per_sec = self.get_pixels_per_sec()

        # 1. Base Canvas Background (Obsidian Navy tone matching screenshot)
        painter.fillRect(0, 0, w, h, QColor("#0c0f17"))

        layout = self._get_tracks_layout()
        v_y = layout["v_y"]
        v_h = layout["v_h"]
        cc_y = layout["cc_y"]
        cc_h = layout["cc_h"]
        cc_lane_map = layout["cc_lane_map"]
        cc_num_lanes = layout["cc_num_lanes"]
        a_y = layout["a_y"]
        a_h = layout["a_h"]
        a_lane_map = layout["a_lane_map"]
        a_num_lanes = layout["a_num_lanes"]
        ov_y = layout["ov_y"]
        ov_h = layout["ov_h"]
        ov_lane_map = layout["ov_lane_map"]
        ov_num_lanes = layout["ov_num_lanes"]
        lane_h = layout["lane_h"]
        total_h = layout["total_h"]

        if self.minimumHeight() != 120:
            self.setMinimumHeight(120)

        ruler_h = 24

        # Horizontal track rows background (clipped below top ruler)
        painter.save()
        painter.setClipRect(QRect(0, ruler_h, w, h - ruler_h))
        painter.fillRect(hw, v_y, w - hw, v_h, QColor("#0d111d"))
        painter.fillRect(hw, cc_y, w - hw, cc_h, QColor("#0d111d"))
        painter.fillRect(hw, a_y, w - hw, a_h, QColor("#0d111d"))
        painter.fillRect(hw, ov_y, w - hw, ov_h, QColor("#0d111d"))

        # Horizontal subtle track divider lines
        painter.setPen(QPen(QColor("#181d2c"), 1))
        painter.drawLine(0, v_y + v_h, w, v_y + v_h)
        painter.drawLine(0, cc_y + cc_h, w, cc_y + cc_h)
        painter.drawLine(0, a_y + a_h, w, a_y + a_h)
        painter.drawLine(0, ov_y + ov_h, w, ov_y + ov_h)
        painter.restore()

        # ---------------- SCROLLABLE CLIPS & RULER AREA ----------------
        # 1. Top Ruler (Fixed Y: 0 to 24)
        painter.fillRect(hw, 0, w - hw, ruler_h, QColor("#111522"))
        painter.setPen(QPen(QColor("#1e2538"), 1))
        painter.drawLine(hw, ruler_h, w, ruler_h)

        step_sec = 1 if pixels_per_sec > 120 else (2 if pixels_per_sec > 60 else (5 if pixels_per_sec > 25 else (10 if pixels_per_sec > 10 else 30)))
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#64748b"))

        start_sec = max(0, int(self.offset_x / pixels_per_sec))
        end_sec = int((self.offset_x + (w - hw)) / pixels_per_sec) + 1

        for sec in range(start_sec, end_sec):
            x = hw + int(sec * pixels_per_sec - self.offset_x)
            if sec % step_sec == 0:
                painter.drawLine(x, ruler_h - 10, x, ruler_h)
                t_str = format_timestamp(sec).split(",")[0]
                painter.drawText(x + 4, ruler_h - 4, t_str)
            elif sec % max(1, step_sec // 5) == 0:
                painter.drawLine(x, ruler_h - 5, x, ruler_h)

        # --- Mark In / Mark Out Range Highlight on Ruler & Tracks ---
        in_t = self.mark_in if self.mark_in is not None else (0.0 if self.mark_out is not None else None)
        out_t = self.mark_out if self.mark_out is not None else (self.duration if self.mark_in is not None else None)

        if in_t is not None and out_t is not None and out_t > in_t:
            x_in = hw + int(in_t * pixels_per_sec - self.offset_x)
            x_out = hw + int(out_t * pixels_per_sec - self.offset_x)

            fill_x = max(hw, x_in)
            fill_w = max(0, min(w, x_out) - fill_x)
            if fill_w > 0:
                painter.fillRect(fill_x, ruler_h, fill_w, h - ruler_h, QColor(56, 189, 248, 30))
                painter.fillRect(fill_x, 0, fill_w, ruler_h, QColor(56, 189, 248, 55))

            # Mark In Bracket '['
            if hw <= x_in <= w:
                painter.setPen(QPen(QColor("#38bdf8"), 2.2))
                painter.drawLine(x_in, 0, x_in, h)
                painter.drawLine(x_in, 2, min(w, x_in + 8), 2)
                painter.drawLine(x_in, ruler_h - 2, min(w, x_in + 8), ruler_h - 2)
                painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
                painter.setPen(QColor("#ffffff"))
                painter.drawText(x_in + 4, 16, f"IN: {format_duration_short(in_t)}")

            # Mark Out Bracket ']'
            if hw <= x_out <= w:
                painter.setPen(QPen(QColor("#38bdf8"), 2.2))
                painter.drawLine(x_out, 0, x_out, h)
                painter.drawLine(max(hw, x_out - 8), 2, x_out, 2)
                painter.drawLine(max(hw, x_out - 8), ruler_h - 2, x_out, ruler_h - 2)
                painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
                painter.setPen(QColor("#ffffff"))
                painter.drawText(max(hw, x_out - 72), 16, f"OUT: {format_duration_short(out_t)}")

            # Duration Pill in Ruler
            mid_x = (x_in + x_out) // 2
            if hw + 50 <= mid_x <= w - 50 and (x_out - x_in) >= 80:
                range_txt = f"Range: {format_duration_short(out_t - in_t)}"
                painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
                fm = painter.fontMetrics()
                pill_w = fm.horizontalAdvance(range_txt) + 12
                pill_x = mid_x - pill_w // 2
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(14, 165, 233, 220)))
                painter.drawRoundedRect(pill_x, 3, pill_w, 18, 4, 4)
                painter.setPen(QColor("#ffffff"))
                painter.drawText(QRect(pill_x, 3, pill_w, 18), Qt.AlignmentFlag.AlignCenter, range_txt)

        # 2. Clips Area (Clipped below ruler so vertically scrolling tracks slide under the ruler)
        painter.save()
        painter.setClipRect(QRect(hw, ruler_h, w - hw, h - ruler_h))

        # --- Track 1: Video Filmstrip Clip(s) ---
        if self.video_clips and len(self.video_clips) > 1:
            # Multi-segment video clips
            for c_idx, clip in enumerate(self.video_clips):
                c_start_t = float(clip.get("timeline_start", 0.0))
                c_dur = float(clip.get("duration", 0.0))
                cx1 = hw + int(c_start_t * pixels_per_sec - self.offset_x)
                cw = max(4, int(c_dur * pixels_per_sec))
                if cx1 + cw <= hw or cx1 >= w:
                    continue
                draw_x = max(hw, cx1)
                draw_w = cw - (draw_x - cx1)
                painter.fillRect(draw_x, v_y + 2, draw_w, v_h - 4, QColor("#1a1e29"))

                c_border = QColor("#f59e0b" if c_idx % 2 == 0 else "#38bdf8")
                painter.setPen(QPen(c_border, 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(cx1, v_y + 2, cw, v_h - 4, 4, 4)

                if draw_w >= 36:
                    c_name = clip.get("name") or f"Part {c_idx+1:02d}"
                    c_badge = f"🎬 {c_name} ({format_duration_short(c_dur)})"
                    painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
                    painter.setPen(QColor("#fef08a"))
                    painter.drawText(QRect(draw_x + 6, v_y + 4, draw_w - 12, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, c_badge)
        else:
            # Single master video clip
            vid_start_x = hw + int(0 - self.offset_x)
            vid_w = max(4, int(self.duration * pixels_per_sec))
            if vid_start_x + vid_w > hw:
                clip_x = max(hw, vid_start_x)
                clip_w = vid_w - (clip_x - vid_start_x)
                # Clip container
                painter.fillRect(clip_x, v_y + 2, clip_w, v_h - 4, QColor("#1a1e29"))

                # Draw Video Filmstrip Thumbnails if available
                if self.video_thumbnails:
                    painter.save()
                    # Clip strictly inside the video container
                    painter.setClipRect(clip_x, v_y + 2, clip_w, v_h - 4)

                    sorted_thumbs = self.video_thumbnails
                    n_thumbs = len(sorted_thumbs)
                    thumb_w = 72
                    clip_end_x = vid_start_x + vid_w

                    for idx in range(n_thumbs):
                        t_val, pix = sorted_thumbs[idx]
                        tx = hw + int(t_val * pixels_per_sec - self.offset_x)

                        # End of current shot / scene
                        if idx + 1 < n_thumbs:
                            next_t, _ = sorted_thumbs[idx + 1]
                            next_tx = hw + int(next_t * pixels_per_sec - self.offset_x)
                        else:
                            next_tx = clip_end_x

                        # Skip if entirely out of viewport
                        if next_tx < hw or tx > w:
                            continue

                        # When zoomed out or span <= thumb_w, draw single thumbnail
                        if next_tx <= tx + thumb_w:
                            painter.drawPixmap(tx, v_y + 2, pix)
                        else:
                            # Continuous filmstrip: tile the thumbnail across [tx, next_tx)
                            # so there are ZERO black voids!
                            tile_x = max(tx, hw - thumb_w)
                            while tile_x < next_tx and tile_x < w:
                                painter.drawPixmap(tile_x, v_y + 2, pix)
                                tile_x += thumb_w

                        # Crisp 1px scene boundary line between shots
                        if hw <= next_tx <= w and idx + 1 < n_thumbs:
                            painter.setPen(QPen(QColor(15, 23, 42, 220), 1.5))
                            painter.drawLine(next_tx, v_y + 2, next_tx, v_y + v_h - 2)

                    painter.restore()
                else:
                    # Decorative filmstrip sprockets
                    painter.setPen(QColor("#334155"))
                    for sp_x in range(clip_x, min(w, clip_x + clip_w), 22):
                        painter.fillRect(sp_x, v_y + 3, 8, 4, QColor("#334155"))
                        painter.fillRect(sp_x, v_y + v_h - 7, 8, 4, QColor("#334155"))

                # Golden / Amber Border
                painter.setPen(QPen(QColor("#f59e0b"), 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(vid_start_x, v_y + 2, vid_w, v_h - 4, 6, 6)

                # Draw Master Video duration badge
                if clip_w >= 80:
                    v_title = os.path.basename(self.video_path) if self.video_path else "Master Video"
                    if len(v_title) > 24:
                        v_title = v_title[:21] + "..."
                    v_badge_txt = f"🎬 {v_title} (⏱️ {format_duration_short(self.duration)})"
                    painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
                    fm = painter.fontMetrics()
                    v_bw = min(clip_w - 24, fm.horizontalAdvance(v_badge_txt) + 16)
                    v_bx = clip_x + 14
                    v_by = v_y + 6
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(QColor(15, 23, 42, 210)))
                    painter.drawRoundedRect(v_bx, v_by, v_bw, 20, 4, 4)
                    painter.setPen(QColor("#fef08a"))
                    painter.drawText(QRect(v_bx, v_by, v_bw, 20), Qt.AlignmentFlag.AlignCenter, v_badge_txt)

                # Left & Right Golden Trim Handles with notch
                if vid_start_x >= hw - 12:
                    self._draw_golden_handle(painter, vid_start_x, v_y + 2, v_h - 4, is_left=True)
                if vid_start_x + vid_w <= w + 12:
                    self._draw_golden_handle(painter, vid_start_x + vid_w - 12, v_y + 2, v_h - 4, is_left=False)

        # Draw Video Keyframe Diamond Markers (◆) on Video Track
        if getattr(self, "video_keyframes", None):
            for kf_idx, kf in enumerate(self.video_keyframes):
                kt = float(kf.get("time", 0.0))
                kx = hw + int(kt * pixels_per_sec - self.offset_x)
                if hw - 10 <= kx <= w + 10:
                    ky = v_y + v_h // 2
                    is_active = (abs(kt - self.current_time) <= 0.08) or (kf_idx == getattr(self, "active_kf_idx", -1))
                    self._draw_keyframe_diamond(painter, kx, ky, is_active=is_active)

        # --- Track 2: CC Subtitles Track ---
        if self.subtitles and self.is_cc_visible:
            painter.setFont(QFont("Kantumruy Pro", 8))
            for idx, sub in enumerate(self.subtitles):
                s = sub.get("start", 0.0)
                e = sub.get("end", 0.0)
                bx = hw + int(s * pixels_per_sec - self.offset_x)
                bw = max(14, int((e - s) * pixels_per_sec))

                if bx + bw < hw or bx > w:
                    continue

                lane = cc_lane_map.get(idx, 0)
                item_y = cc_y + 3 + lane * lane_h
                item_h = lane_h - 6

                is_selected = (idx in self.selected_indices) or (idx == self.active_sub_idx)
                is_active = (s <= self.current_time <= e)

                if is_selected:
                    bg_color = QColor("#0284c7")
                    border_color = QColor("#facc15")
                    border_w = 2
                elif is_active:
                    bg_color = QColor("#d97706")
                    border_color = QColor("#fde047")
                    border_w = 1.5
                else:
                    bg_color = QColor("#1e293b")
                    border_color = QColor("#38bdf8")
                    border_w = 1.2

                painter.setPen(QPen(border_color, border_w))
                painter.setBrush(QBrush(bg_color))
                painter.drawRoundedRect(bx, item_y, bw, item_h, 8, 8)

                # Dialogue Text + Duration in minutes
                txt = sub.get("khmer_text") or sub.get("orig_text") or sub.get("text") or ""
                dur_str = format_duration_short(e - s)
                label_text = f"#{idx+1} {txt} ({dur_str})"
                if bw > 36:
                    painter.setPen(QColor("#ffffff"))
                    painter.drawText(bx + 18, item_y + 22, label_text[:38])

                # White Trim Handles [ | ]
                if bw >= 28:
                    self._draw_white_handle(painter, bx + 2, item_y, item_h)
                    self._draw_white_handle(painter, bx + bw - 12, item_y, item_h)

        # --- Track 3: Audio Voice Dubbing & Dropped Music Tracks ---
        audio_items = self._get_audio_items_for_timeline()
        if audio_items:
            for idx, a_it in enumerate(audio_items):
                s = a_it["start"]
                e = a_it["end"]
                ax = hw + int(s * pixels_per_sec - self.offset_x)
                aw = max(14, int((e - s) * pixels_per_sec))

                if ax + aw < hw or ax > w:
                    continue

                lane = a_lane_map.get(idx, 0)
                item_y = a_y + 3 + lane * lane_h
                item_h = lane_h - 6

                is_track = a_it.get("is_track", False)
                sub_idx = a_it.get("sub_idx", -1)
                is_selected = (not is_track and ((sub_idx in self.selected_indices) or (sub_idx == self.active_sub_idx))) or (is_track and (idx == getattr(self, "_active_audio_track_idx", -1)))
                is_active = (s <= self.current_time <= e)

                # Smooth slate blue / emerald pill fill & border matching screenshot
                if is_track:
                    if is_selected:
                        abg = QColor("#065f46")
                        aborder = QColor("#34d399")
                        aborder_w = 2
                    elif is_active:
                        abg = QColor("#047857")
                        aborder = QColor("#6ee7b7")
                        aborder_w = 1.8
                    else:
                        abg = QColor("#064e3b")
                        aborder = QColor("#10b981")
                        aborder_w = 1.4
                else:
                    actor = a_it.get("actor", "")
                    gender = a_it.get("gender", "")
                    is_female = ("ស្រី" in actor or "Female" in actor or gender == "female")
                    is_kid = ("កូនក្មេង" in actor or "Kid" in actor or "Child" in actor)
                    is_spk = ("តួអង្គ" in actor or "Speaker" in actor)

                    if is_selected:
                        abg = QColor("#0c3f6e") if not is_female else QColor("#500724")
                        aborder = QColor("#facc15")
                        aborder_w = 2.2
                    elif is_active:
                        if is_female:
                            abg = QColor("#9d174d")
                            aborder = QColor("#f472b6")
                        elif is_kid:
                            abg = QColor("#92400e")
                            aborder = QColor("#fbbf24")
                        elif is_spk:
                            abg = QColor("#6b21a8")
                            aborder = QColor("#c084fc")
                        else:
                            abg = QColor("#0369a1")
                            aborder = QColor("#38bdf8")
                        aborder_w = 1.8
                    else:
                        if is_female:
                            abg = QColor("#4c0519")
                            aborder = QColor("#be185d")
                        elif is_kid:
                            abg = QColor("#451a03")
                            aborder = QColor("#b45309")
                        elif is_spk:
                            abg = QColor("#3b0764")
                            aborder = QColor("#7e22ce")
                        elif "ប្រុស" in actor or "Male" in actor:
                            abg = QColor("#082f49")
                            aborder = QColor("#0284c7")
                        else:
                            abg = QColor("#0f172a")
                            aborder = QColor("#334155")
                        aborder_w = 1.4

                painter.setPen(QPen(aborder, aborder_w))
                painter.setBrush(QBrush(abg))
                painter.drawRoundedRect(ax, item_y, aw, item_h, 8, 8)

                # Audio Waveform Amplitude Bars
                wave_step = 3
                center_y = item_y + item_h // 2
                is_fem = (not is_track and ("ស្រី" in a_it.get("actor", "") or a_it.get("gender") == "female"))
                wave_color = QColor("#facc15" if is_selected else ("#a7f3d0" if is_track else ("#fbcfe8" if is_fem else "#bae6fd")))
                painter.setPen(QPen(wave_color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                start_bar_x = ax + (15 if aw >= 32 else 4)
                end_bar_x = ax + aw - (15 if aw >= 32 else 4)

                if end_bar_x > start_bar_x:
                    bar_count = max(1, int((end_bar_x - start_bar_x) / wave_step))
                    for b_i in range(bar_count):
                        sin_val = math.sin((b_i / float(max(1, bar_count))) * math.pi)
                        amp = int(sin_val * (item_h * 0.40) * (0.35 + 0.65 * ((b_i * 17 + 5) % 11) / 11.0))
                        amp = max(2, amp)
                        bar_x = start_bar_x + b_i * wave_step
                        painter.drawLine(bar_x, center_y - amp, bar_x, center_y + amp)

                # Audio Badge Title with duration in minutes & volume
                if aw >= 50:
                    dur_str = format_duration_short(e - s)
                    vol_val = a_it.get("volume", 1.0)
                    vol_txt = f" 🔊{int(vol_val*100)}%" if vol_val != 1.0 else ""
                    spd_val = a_it.get("speed", 1.0)
                    spd_txt = f" ⚡{spd_val}x" if spd_val != 1.0 else ""
                    raw_obj = a_it.get("raw") if isinstance(a_it.get("raw"), dict) else a_it
                    cur_fx = raw_obj.get("voice_effect") or a_it.get("voice_effect", "none")
                    fx_txt = ""
                    if cur_fx and cur_fx not in ("none", "original"):
                        from services.dubbing.audio_effects import get_voice_effect_icon
                        fx_txt = f" ✨{get_voice_effect_icon(cur_fx)}{cur_fx}"

                    if is_track:
                        name_txt = a_it.get("name", "Audio")
                        if len(name_txt) > 18:
                            name_txt = name_txt[:16] + ".."
                        a_label = f"🎵 {name_txt} (⏱️ {dur_str}{vol_txt}{spd_txt}{fx_txt})"
                    else:
                        actor_txt = a_it.get("actor") or "Voice"
                        if len(actor_txt) > 12:
                            actor_txt = actor_txt[:10] + ".."
                        name_txt = a_it.get("name", "Line")
                        if len(name_txt) > 14:
                            name_txt = name_txt[:12] + ".."
                        has_aud = a_it.get("has_audio", False)
                        aud_icon = "🔊" if has_aud else "🎙️"
                        a_label = f"{aud_icon} [{actor_txt}] {name_txt} (⏱️ {dur_str}{vol_txt}{spd_txt}{fx_txt})"

                    painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                    fm = painter.fontMetrics()
                    a_bw = min(aw - 28, fm.horizontalAdvance(a_label) + 12)
                    a_bx = ax + 14
                    a_by = item_y + 3
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(QColor(10, 15, 30, 180)))
                    painter.drawRoundedRect(a_bx, a_by, a_bw, item_h - 6, 3, 3)
                    painter.setPen(QColor("#ffffff"))
                    painter.drawText(QRect(a_bx, a_by, a_bw, item_h - 6), Qt.AlignmentFlag.AlignCenter, a_label)

                # White Trim Handles [ | ]
                if aw >= 28:
                    self._draw_white_handle(painter, ax + 2, item_y, item_h)
                    self._draw_white_handle(painter, ax + aw - 12, item_y, item_h)

        # --- Track 4: Overlays & Shapes Track ---
        if self.overlay_clips and self.is_overlay_visible:
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            for idx, item in enumerate(self.overlay_clips):
                st, et = self._get_overlay_time_span(item)
                ox = hw + int(st * pixels_per_sec - self.offset_x)
                ow = max(14, int((et - st) * pixels_per_sec))

                if ox + ow < hw or ox > w:
                    continue

                lane = ov_lane_map.get(idx, 0)
                item_y = ov_y + 3 + lane * lane_h
                item_h = lane_h - 6

                itype, iname = self._get_overlay_info(item)
                is_selected = (idx == self.active_overlay_idx)
                is_active = (st <= self.current_time <= et)

                # Violet / Purple Pill Container matching screenshot
                if is_selected:
                    bg_col = QColor("#7c3aed")
                    border_col = QColor("#facc15")
                    border_w = 2
                elif is_active:
                    bg_col = QColor("#7969f5")
                    border_col = QColor("#c4b5fd")
                    border_w = 1.8
                else:
                    bg_col = QColor("#6858e8")
                    border_col = QColor("#8579f2")
                    border_w = 1.4

                painter.setPen(QPen(border_col, border_w))
                painter.setBrush(QBrush(bg_col))
                painter.drawRoundedRect(ox, item_y, ow, item_h, 8, 8)

                # Translucent label badge inside with duration
                if ow >= 32:
                    dur_str = format_duration_short(et - st)
                    raw_name = iname if iname else itype.title()
                    display_name = f"{raw_name} ({dur_str})"
                    fm = painter.fontMetrics()
                    txt_w = fm.horizontalAdvance(display_name)
                    badge_w = min(ow - 28, txt_w + 14)
                    badge_x = ox + 14
                    badge_y = item_y + 4
                    badge_h = item_h - 8

                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(QColor(20, 10, 45, 110)))
                    painter.drawRoundedRect(badge_x, badge_y, badge_w, badge_h, 4, 4)

                    painter.setPen(QColor("#ffffff"))
                    painter.drawText(QRect(badge_x, badge_y, badge_w, badge_h), Qt.AlignmentFlag.AlignCenter, display_name)

                # White Trim Handles [ | ]
                if ow >= 28:
                    self._draw_white_handle(painter, ox + 2, item_y, item_h)
                    self._draw_white_handle(painter, ox + ow - 12, item_y, item_h)

        # --- Playhead Vertical Needle Line ---
        px = hw + int(self.current_time * pixels_per_sec - self.offset_x)
        if hw <= px <= w:
            painter.setPen(QPen(QColor(255, 255, 255, 240), 1.6))
            painter.drawLine(px, 0, px, h)

            # Playhead Top Arrow Indicator
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#ffffff")))
            poly = [QPoint(px - 6, 0), QPoint(px + 6, 0), QPoint(px, 12)]
            painter.drawPolygon(poly)

        # --- Marquee / Rubber-band Selection Box ---
        if self._marquee_active and self._interaction_mode == "marquee_select":
            m_rect = QRect(self._marquee_start_pos, self._marquee_current_pos).normalized()
            track_area = QRect(hw, 24, w - hw, h - 24)
            draw_rect = m_rect.intersected(track_area)
            if not draw_rect.isEmpty():
                painter.save()
                # Translucent cyan selection fill
                painter.fillRect(draw_rect, QColor(14, 165, 233, 45))
                # Dashed neon border
                m_pen = QPen(QColor("#38bdf8"), 1.5, Qt.PenStyle.DashLine)
                painter.setPen(m_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(draw_rect)
                painter.restore()

        painter.restore()

        # ---------------- 2. FIXED LEFT TRACK HEADER COLUMN ----------------
        painter.fillRect(0, 0, hw, h, QColor("#101321"))
        # Right border separating header from timeline tracks
        painter.setPen(QPen(QColor("#1e2438"), 1))
        painter.drawLine(hw, 0, hw, h)

        # Top ruler corner block
        painter.fillRect(0, 0, hw, 24, QColor("#141829"))
        painter.drawLine(0, 24, hw, 24)

        # Clip track headers below ruler so scrolling headers slide under the corner
        painter.save()
        painter.setClipRect(QRect(0, 24, hw, h - 24))

        # Divider lines between track rows inside the header
        painter.setPen(QPen(QColor("#181d2c"), 1))
        painter.drawLine(0, v_y + v_h, hw, v_y + v_h)
        painter.drawLine(0, cc_y + cc_h, hw, cc_y + cc_h)
        painter.drawLine(0, a_y + a_h, hw, a_y + a_h)
        painter.drawLine(0, ov_y + ov_h, hw, ov_y + ov_h)

        btn_rects = self._get_header_button_rects()

        def _draw_hdr_btn(rect: QRect, is_hovered: bool):
            painter.save()
            painter.setPen(QPen(QColor("#333d59" if is_hovered else "#222a3d"), 1))
            painter.setBrush(QBrush(QColor("#242b3e" if is_hovered else "#171c2b")))
            painter.drawRoundedRect(rect, 5, 5)
            painter.restore()

        # Row 1: Video Track Header
        self._draw_camera_icon(painter, 12, v_y + (v_h - 18) // 2, QColor("#94a3b8"))
        v_btn = btn_rects["video_eye"]
        _draw_hdr_btn(v_btn, self._hovered_header_btn == "video_eye")
        self._draw_eye_icon(painter, v_btn.x() + 5, v_btn.y() + 6, self.is_video_visible,
                            QColor("#a5b4fc" if self.is_video_visible else "#64748b"))

        # Row 2: CC Subtitles Track Header
        self._draw_cc_icon(painter, 12, cc_y + (lane_h - 18) // 2, QColor("#94a3b8"))
        cc_btn = btn_rects["cc_eye"]
        _draw_hdr_btn(cc_btn, self._hovered_header_btn == "cc_eye")
        self._draw_eye_icon(painter, cc_btn.x() + 5, cc_btn.y() + 6, self.is_cc_visible,
                            QColor("#a5b4fc" if self.is_cc_visible else "#64748b"))

        # Row 3: Audio Voice Dub Track Header
        self._draw_music_icon(painter, 12, a_y + (lane_h - 18) // 2, QColor("#94a3b8"))
        a_btn = btn_rects["audio_speaker"]
        _draw_hdr_btn(a_btn, self._hovered_header_btn == "audio_speaker")
        self._draw_speaker_icon(painter, a_btn.x() + 5, a_btn.y() + 6, self.is_audio_track_muted,
                                QColor("#f87171" if self.is_audio_track_muted else "#a5b4fc"))

        # Row 4: Overlays & Shapes Track Header
        self._draw_shapes_icon(painter, 12, ov_y + (lane_h - 18) // 2, QColor("#94a3b8"))
        ov_btn = btn_rects["overlay_eye"]
        _draw_hdr_btn(ov_btn, self._hovered_header_btn == "overlay_eye")
        self._draw_eye_icon(painter, ov_btn.x() + 5, ov_btn.y() + 6, self.is_overlay_visible,
                            QColor("#a5b4fc" if self.is_overlay_visible else "#64748b"))

        painter.restore()

        # ---------------- 3. VERTICAL SCROLLBAR ----------------
        bar_rect, thumb_rect = self._get_v_scrollbar_rect()
        if bar_rect and thumb_rect:
            painter.fillRect(bar_rect, QColor(255, 255, 255, 12))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(56, 189, 248, 160 if getattr(self, "_is_dragging_v_scrollbar", False) else 100)))
            painter.drawRoundedRect(thumb_rect, 3, 3)

        painter.end()
