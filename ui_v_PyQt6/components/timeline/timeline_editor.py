"""
Timeline Editor Component for PyQt6 / PySide6 Desktop Studio
Dedicated multi-track timeline editor widget with interactive canvas,
zoom controllers, track visualization, and clip scrubbing.
"""

from ui_v_PyQt6.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QGroupBox, QPushButton, QComboBox, Qt, Signal,
    QMenu, QInputDialog, QFrame
)
from ui_v_PyQt6.components.timeline.timeline_canvas import TimelineCanvas


class TimelineEditor(QWidget):
    """
    Multi-Track Timeline Editor Component:
    - Multi-track visualization: Video Track, CC Track, Audio Tracks
    - Hardware-accelerated 60fps Timeline Canvas with live playhead
    - Dynamic zooming (Ctrl + Mouse Wheel, Extended 25x Slider, Quick Zoom Buttons)
    - Playback Speed Selector (0.5x to 2.0x) and Master Volume Slider (0% to 150%)
    - Bidirectional clip selection (Ctrl+Click, Shift+Click multi-select)
    - Full Drag & Move, Trim/Resize, and Double-Click editing
    - Drag & Drop media loading
    - Full Right-Click context menus
    - Razor split (S), Mark In/Out (I/O), Ripple delete, and Batch Export
    """
    subtitles_modified = Signal()
    video_dropped = Signal(str)
    subtitle_dropped = Signal(str)
    audio_dropped = Signal(str)
    audio_tracks_modified = Signal()
    audio_selected = Signal(object)
    cc_visibility_changed = Signal(bool)
    audio_mute_changed = Signal(bool)
    overlay_selected = Signal(object)
    overlays_modified = Signal()
    speed_changed = Signal(float)
    volume_changed = Signal(float)
    split_requested = Signal(float)
    mark_in_changed = Signal(object)
    mark_out_changed = Signal(object)
    ripple_delete_requested = Signal()
    extract_range_requested = Signal(float, float)
    export_range_requested = Signal(float, float)
    auto_split_requested = Signal(float)
    merge_segments_requested = Signal()
    keyframe_added = Signal(float)
    keyframe_selected = Signal(dict)
    keyframe_moved = Signal(int, float)
    keyframe_deleted = Signal(float)
    keyframes_modified = Signal(list)

    def __init__(
        self,
        parent=None,
        on_seek=None,
        on_select_sub=None,
        on_select_multiple_subs=None,
        on_context_menu=None,
        on_hide_clicked=None,
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
        self.on_hide_clicked = on_hide_clicked
        self.on_add_sub_at_time = on_add_sub_at_time
        self.on_fix_overlaps = on_fix_overlaps
        self.on_subtitles_modified = on_subtitles_modified
        self.on_video_dropped = on_video_dropped
        self.on_subtitle_dropped = on_subtitle_dropped
        self.on_audio_dropped = on_audio_dropped
        self.on_toggle_cc_visibility = on_toggle_cc_visibility
        self.on_toggle_audio_mute = on_toggle_audio_mute

        self.setAcceptDrops(True)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(4)

        # Container Card Frame (Title badge removed for clean and compact layout)
        group_timeline = QFrame()
        group_timeline.setObjectName("timeline_card")
        group_timeline.setStyleSheet("""
            QFrame#timeline_card {
                background-color: #161922;
                border: 1px solid #262c3b;
                border-radius: 8px;
            }
        """)
        tl_layout = QVBoxLayout(group_timeline)
        tl_layout.setContentsMargins(6, 6, 6, 6)
        tl_layout.setSpacing(4)

        # Tool handles initialized as None for backward compatibility
        self.btn_split = None
        self.btn_mark_in = None
        self.btn_mark_out = None
        self.btn_ripple_del = None
        self.btn_auto_split = None
        self.btn_range_tools = None
        self.combo_speed = None
        self.btn_mute = None
        self.slider_volume = None
        self.lbl_volume_val = None
        self.slider_zoom = None
        self.lbl_zoom_val = None
        self.btn_zoom_out = None
        self.btn_zoom_in = None
        self.btn_zoom_reset = None
        self.btn_zoom_fit = None
        self.btn_hide = None
        self._is_muted = False
        self._prev_vol_val = 100

        # Interactive 60fps Canvas
        self.canvas = TimelineCanvas(
            self,
            on_seek=self.on_seek,
            on_select_sub=self.on_select_sub,
            on_select_multiple_subs=self.on_select_multiple_subs,
            on_context_menu=self.on_context_menu,
            on_add_sub_at_time=self.on_add_sub_at_time,
            on_fix_overlaps=self.on_fix_overlaps,
            on_subtitles_modified=self.on_subtitles_modified,
            on_video_dropped=self.on_video_dropped,
            on_subtitle_dropped=self.on_subtitle_dropped,
            on_audio_dropped=self.on_audio_dropped,
            on_toggle_cc_visibility=self.on_toggle_cc_visibility,
            on_toggle_audio_mute=self.on_toggle_audio_mute
        )
        self.canvas.subtitles_modified.connect(self.subtitles_modified.emit)
        self.canvas.video_dropped.connect(self.video_dropped.emit)
        self.canvas.subtitle_dropped.connect(self.subtitle_dropped.emit)
        self.canvas.audio_dropped.connect(self.audio_dropped.emit)
        self.canvas.audio_tracks_modified.connect(self.audio_tracks_modified.emit)
        self.canvas.audio_selected.connect(self.audio_selected.emit)
        self.canvas.cc_visibility_changed.connect(self.cc_visibility_changed.emit)
        self.canvas.audio_mute_changed.connect(self.audio_mute_changed.emit)
        self.canvas.overlay_selected.connect(self.overlay_selected.emit)
        self.canvas.overlays_modified.connect(self.overlays_modified.emit)

        # Forward timeline editing signals
        self.canvas.split_requested.connect(self.split_requested.emit)
        self.canvas.mark_in_changed.connect(self.mark_in_changed.emit)
        self.canvas.mark_out_changed.connect(self.mark_out_changed.emit)
        self.canvas.ripple_delete_requested.connect(self.ripple_delete_requested.emit)
        self.canvas.extract_range_requested.connect(self.extract_range_requested.emit)
        self.canvas.export_range_requested.connect(self.export_range_requested.emit)
        self.canvas.auto_split_requested.connect(self.auto_split_requested.emit)
        self.canvas.merge_segments_requested.connect(self.merge_segments_requested.emit)

        # Forward video keyframe signals
        self.canvas.keyframe_added.connect(self.keyframe_added.emit)
        self.canvas.keyframe_selected.connect(self.keyframe_selected.emit)
        self.canvas.keyframe_moved.connect(self.keyframe_moved.emit)
        self.canvas.keyframe_deleted.connect(self.keyframe_deleted.emit)
        self.canvas.keyframes_modified.connect(self.keyframes_modified.emit)

        tl_layout.addWidget(self.canvas)
        main_layout.addWidget(group_timeline)

    # ------------------ SPEED & VOLUME CONTROLLERS ------------------
    def _on_speed_combo_changed(self, text: str):
        try:
            spd = float(text.replace("x", "").replace("X", "").strip())
        except Exception:
            spd = 1.0
        self.speed_changed.emit(spd)

    def set_playback_speed(self, speed: float):
        if getattr(self, "combo_speed", None):
            txt = f"{speed:.1f}x" if speed != 1.25 and speed != 0.75 else f"{speed}x"
            self.combo_speed.blockSignals(True)
            idx = self.combo_speed.findText(txt)
            if idx >= 0:
                self.combo_speed.setCurrentIndex(idx)
            else:
                self.combo_speed.setCurrentText(txt)
            self.combo_speed.blockSignals(False)

    def _on_volume_slider_changed(self, val: int):
        if getattr(self, "lbl_volume_val", None):
            self.lbl_volume_val.setText(f"{val}%")
        if val == 0:
            if getattr(self, "btn_mute", None):
                self.btn_mute.setText("🔇")
            self._is_muted = True
        else:
            if getattr(self, "btn_mute", None):
                self.btn_mute.setText("🔊")
            self._is_muted = False
            self._prev_vol_val = val
        self.volume_changed.emit(val / 100.0)

    def _on_mute_clicked(self):
        if getattr(self, "slider_volume", None):
            if self._is_muted:
                self._is_muted = False
                val = self._prev_vol_val if self._prev_vol_val > 0 else 100
                self.slider_volume.setValue(val)
            else:
                self._is_muted = True
                self._prev_vol_val = max(10, self.slider_volume.value())
                self.slider_volume.setValue(0)

    def set_volume(self, vol: float):
        if getattr(self, "slider_volume", None):
            val = int(round(vol * 100))
            self.slider_volume.blockSignals(True)
            self.slider_volume.setValue(max(0, min(150, val)))
            if getattr(self, "lbl_volume_val", None):
                self.lbl_volume_val.setText(f"{val}%")
            if getattr(self, "btn_mute", None):
                self.btn_mute.setText("🔇" if val == 0 else "🔊")
            self.slider_volume.blockSignals(False)

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
        self.canvas.dropEvent(event)

    def _on_zoom_slider_changed(self, val: int):
        factor = val / 100.0
        if getattr(self, "lbl_zoom_val", None):
            self.lbl_zoom_val.setText(f"{val}%")
        self.canvas.zoom_to(factor)

    def zoom_in(self):
        self.canvas.zoom_to(self.canvas.zoom * 1.3)

    def zoom_out(self):
        self.canvas.zoom_to(self.canvas.zoom / 1.3)

    def zoom_reset(self):
        self.canvas.zoom_to(1.0)

    def zoom_fit(self):
        self.canvas.fit_to_window()

    def set_duration(self, dur: float):
        self.canvas.set_duration(dur)

    def set_current_time(self, t: float):
        self.canvas.set_current_time(t)

    def set_data(self, subtitles=None, video_clips=None, audio_tracks=None, video_path=None, overlay_clips=None, video_keyframes=None):
        self.canvas.set_data(subtitles=subtitles, video_clips=video_clips, audio_tracks=audio_tracks, video_path=video_path, overlay_clips=overlay_clips, video_keyframes=video_keyframes)

    def set_overlay_clips(self, overlay_clips):
        self.canvas.set_overlay_clips(overlay_clips)

    def set_zoom(self, zoom_factor: float):
        self.canvas.zoom_to(zoom_factor)

    def _on_add_kf_clicked(self):
        self.keyframe_added.emit(self.canvas.current_time)

    def _on_prev_kf_clicked(self):
        cur_t = self.canvas.current_time
        prev_kfs = [k for k in getattr(self.canvas, "video_keyframes", []) if float(k.get("time", 0.0)) < cur_t - 0.05]
        if prev_kfs:
            target = max(prev_kfs, key=lambda x: float(x.get("time", 0.0)))
            t = float(target.get("time", 0.0))
            self.canvas.set_current_time(t)
            if self.on_seek:
                self.on_seek(t)

    def _on_next_kf_clicked(self):
        cur_t = self.canvas.current_time
        next_kfs = [k for k in getattr(self.canvas, "video_keyframes", []) if float(k.get("time", 0.0)) > cur_t + 0.05]
        if next_kfs:
            target = min(next_kfs, key=lambda x: float(x.get("time", 0.0)))
            t = float(target.get("time", 0.0))
            self.canvas.set_current_time(t)
            if self.on_seek:
                self.on_seek(t)

    def _on_del_kf_clicked(self):
        cur_t = self.canvas.current_time
        for idx, kf in enumerate(getattr(self.canvas, "video_keyframes", [])):
            if abs(float(kf.get("time", 0.0)) - cur_t) <= 0.08:
                self.canvas._delete_keyframe_at_idx(idx)
                break

    def set_video_keyframes(self, keyframes):
        self.canvas.set_video_keyframes(keyframes)
