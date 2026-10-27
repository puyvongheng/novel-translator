"""
Auto Reframe Dialog (16:9 to 9:16 TikTok / Shorts)
Provides 5-Stage Smart Auto Reframe:
  1. Detect Face & Person (MediaPipe + Local Haar Cascades + OpenCV HOG Person Detector)
  2. Track Position (X, Y) across frames
  3. Smart Decision Engine: 1 Person vs Multi-Person Group vs Active Speaker
  4. Anti-Dizziness Camera Stabilizer (Dead-Zone Pan Dead-Band + SciPy Steadicam Motion Smoothing)
  5. Keyframe Generation & Direct Vertical 9:16 Video Export
"""

import os
from ui_v_PyQt6.qt_compat import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QComboBox, QSlider, QProgressBar, QGroupBox, QRadioButton, 
    QButtonGroup, QCheckBox, Qt, Signal, QThread, QMessageBox, QFileDialog, QFrame
)
from services.video.auto_reframe import AutoReframeEngine, MEDIAPIPE_AVAILABLE, SCIPY_AVAILABLE


class AutoReframeWorker(QThread):
    progress = Signal(float, str)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, video_path: str, mode: str, smoothness: float, dead_zone_ratio: float = 0.15):
        super().__init__()
        self.video_path = video_path
        self.mode = mode
        self.smoothness = smoothness
        self.dead_zone_ratio = dead_zone_ratio
        self.engine = AutoReframeEngine()

    def run(self):
        try:
            res = self.engine.analyze_video(
                video_path=self.video_path,
                target_aspect_w=9,
                target_aspect_h=16,
                mode=self.mode,
                smoothness=self.smoothness,
                dead_zone_ratio=self.dead_zone_ratio,
                sample_interval=2,
                progress_callback=lambda pct, msg: self.progress.emit(pct, msg)
            )
            self.finished.emit(res)
        except Exception as e:
            self.error.emit(str(e))

    def cancel(self):
        self.engine.request_stop()


class AutoReframeExportWorker(QThread):
    progress = Signal(float, str)
    finished = Signal(bool, str)
    error = Signal(str)

    def __init__(self, video_path: str, trajectory: list, output_path: str, use_gpu: bool = True):
        super().__init__()
        self.video_path = video_path
        self.trajectory = trajectory
        self.output_path = output_path
        self.use_gpu = use_gpu
        self.engine = AutoReframeEngine()

    def run(self):
        try:
            ok = self.engine.render_reframe_video(
                video_path=self.video_path,
                trajectory=self.trajectory,
                output_path=self.output_path,
                target_w=1080,
                target_h=1920,
                use_gpu=self.use_gpu,
                progress_callback=lambda pct, msg: self.progress.emit(pct, msg)
            )
            self.finished.emit(ok, self.output_path)
        except Exception as e:
            self.error.emit(str(e))

    def cancel(self):
        self.engine.request_stop()


class AutoReframeDialog(QDialog):
    """
    Studio Dialog for AI Face Tracking & Smart Auto Reframe (TikTok 9:16)
    """
    reframe_applied = Signal(dict)  # emits { "keyframes": [...], "trajectory": [...] }
    video_selected = Signal(str)

    def __init__(self, *args, parent=None, video_path: str = None, **kwargs):
        actual_parent = parent
        actual_video_path = video_path

        # Gracefully handle any positional arguments (e.g. (video_path, parent) or (parent, video_path))
        if args:
            for a in args:
                if isinstance(a, str) and not actual_video_path:
                    actual_video_path = a
                elif isinstance(a, QWidget) and not actual_parent:
                    actual_parent = a

        super().__init__(actual_parent)
        self.setWindowTitle("🤖 Smart Auto Reframe (TikTok / Shorts 9:16)")
        self.setFixedWidth(560)
        self.setStyleSheet("""
            QDialog {
                background-color: #12161f;
                color: #e2e8f0;
            }
            QLabel {
                color: #cbd5e1;
                font-size: 11px;
            }
            QGroupBox {
                border: 1px solid #283344;
                border-radius: 6px;
                margin-top: 10px;
                padding: 10px;
                background-color: #161b24;
                font-weight: bold;
                color: #38bdf8;
                font-size: 11px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QPushButton {
                background-color: #1e2636;
                border: 1px solid #334155;
                border-radius: 5px;
                color: #e2e8f0;
                padding: 7px 14px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #283548;
                border-color: #38bdf8;
                color: #ffffff;
            }
            QCheckBox {
                color: #e2e8f0;
                font-size: 11px;
                font-weight: 600;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
        """)

        self.video_path = actual_video_path
        self.analysis_result = None
        self._worker = None
        self._export_worker = None

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header Title
        lbl_head = QLabel("🎬 Smart Auto Reframe Engine (16:9 ➔ 9:16)")
        lbl_head.setStyleSheet("font-size: 14px; font-weight: bold; color: #38bdf8;")
        layout.addWidget(lbl_head)

        lbl_desc = QLabel(
            "ស្វែងរកមនុស្ស/មុខ ➔ សម្រេចចិត្តចាប់ប្លង់ 1 នាក់ ឬច្រើននាក់ ➔ "
            "រក្សាប្លង់ស្ងប់ (Dead-Zone Stabilizer) កុំឱ្យវិលមុខ ➔ រំកិល Camera យ៉ាងរលូនដូច Hollywood Gimbal។"
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #94a3b8; font-size: 11px; margin-bottom: 2px;")
        layout.addWidget(lbl_desc)

        # 0. VIDEO SOURCE SELECTION BAR
        grp_video = QGroupBox("📁 វីដេអូចម្បង (Source Video)")
        lay_video = QHBoxLayout(grp_video)
        lay_video.setSpacing(8)
        display_name = os.path.basename(self.video_path) if (self.video_path and os.path.exists(self.video_path)) else "(មិនទាន់ជ្រើសរើសវីដេអូ - សូមចុច Browse)"
        self.lbl_video_name = QLabel(display_name)
        self.lbl_video_name.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 11px;")
        lay_video.addWidget(self.lbl_video_name, 1)

        self.btn_browse_video = QPushButton("📂 Browse Video...")
        self.btn_browse_video.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 4px;
                padding: 4px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0284c7;
                color: #ffffff;
            }
        """)
        self.btn_browse_video.clicked.connect(self._browse_video)
        lay_video.addWidget(self.btn_browse_video)
        layout.addWidget(grp_video)

        # 1. TRACKING & DECISION MODE GROUP
        grp_mode = QGroupBox("🧠 Smart Decision Engine (ការសម្រេចចិត្តចាប់ប្លង់)")
        lay_mode = QVBoxLayout(grp_mode)
        lay_mode.setSpacing(6)

        self.btn_group_mode = QButtonGroup(self)

        # Mode 1: Smart Auto (Recommended)
        self.radio_smart = QRadioButton("🤖 Smart Auto Framing (សម្រេចស្វ័យប្រវត្តិ: ចាប់ប្លង់ 1 នាក់ ឬ ច្រើននាក់ ឬ អ្នកនិយាយ)")
        self.radio_smart.setChecked(True)
        self.radio_smart.setStyleSheet("color: #38bdf8; font-weight: bold;")
        self.btn_group_mode.addButton(self.radio_smart, 1)
        lay_mode.addWidget(self.radio_smart)

        # Mode 2: Follow Speaker
        self.radio_speaker = QRadioButton("🗣️ Follow Speaker (ផ្ដោតលើអ្នកកំពុងនិយាយ / Lip MAR)")
        self.btn_group_mode.addButton(self.radio_speaker, 2)
        lay_mode.addWidget(self.radio_speaker)

        # Mode 3: Multi-Person Group
        self.radio_multi = QRadioButton("👥 Multi-Person Group Always (ចាប់ប្លង់មនុស្សច្រើននាក់ជានិច្ច)")
        self.btn_group_mode.addButton(self.radio_multi, 3)
        lay_mode.addWidget(self.radio_multi)

        # Mode 4: Primary Face / 1 Person
        self.radio_face = QRadioButton("👤 Single Person / Primary (ផ្ដោតលើមនុស្សចម្បង 1 នាក់)")
        self.btn_group_mode.addButton(self.radio_face, 4)
        lay_mode.addWidget(self.radio_face)

        layout.addWidget(grp_mode)

        # 2. ANTI-DIZZINESS DEAD-ZONE STABILIZER GROUP
        grp_stability = QGroupBox("🛡️ Anti-Dizziness Camera Stabilizer (បច្ចេកវិទ្យាកុំឱ្យវិលមុខ)")
        lay_stability = QVBoxLayout(grp_stability)
        lay_stability.setSpacing(6)

        self.chk_dead_zone = QCheckBox("រក្សាប្លង់ស្ងប់ (Dead-Zone Pan Dead-Band) មិនឱ្យ Camera ញ័រតាមក្បាលតិចតួច")
        self.chk_dead_zone.setChecked(True)
        self.chk_dead_zone.toggled.connect(self._on_dead_zone_toggled)
        lay_stability.addWidget(self.chk_dead_zone)

        h_dz_lbl = QHBoxLayout()
        h_dz_lbl.addWidget(QLabel("Dead-Zone Window (ទំហំប្លង់ស្ងប់):"))
        self.lbl_dz_val = QLabel("15% (ស្មើ ~162px ក្នុង 1080p)")
        self.lbl_dz_val.setStyleSheet("color: #38bdf8; font-weight: bold;")
        h_dz_lbl.addWidget(self.lbl_dz_val)
        lay_stability.addLayout(h_dz_lbl)

        self.slider_dead_zone = QSlider(Qt.Orientation.Horizontal)
        self.slider_dead_zone.setRange(5, 30)
        self.slider_dead_zone.setValue(15)
        self.slider_dead_zone.valueChanged.connect(self._on_dead_zone_changed)
        lay_stability.addWidget(self.slider_dead_zone)

        layout.addWidget(grp_stability)

        # 3. CAMERA MOTION SMOOTHING GROUP (SCIPY)
        grp_smooth = QGroupBox("🌊 Steadicam Motion Smoothing (SciPy)")
        lay_smooth = QVBoxLayout(grp_smooth)
        lay_smooth.setSpacing(6)

        h_smooth_lbl = QHBoxLayout()
        h_smooth_lbl.addWidget(QLabel("Camera Motion Smoothness:"))
        self.lbl_smooth_val = QLabel("0.85 (Hollywood Steadicam Gliding)")
        self.lbl_smooth_val.setStyleSheet("color: #38bdf8; font-weight: bold;")
        h_smooth_lbl.addWidget(self.lbl_smooth_val)
        lay_smooth.addLayout(h_smooth_lbl)

        self.slider_smooth = QSlider(Qt.Orientation.Horizontal)
        self.slider_smooth.setRange(20, 100)
        self.slider_smooth.setValue(85)
        self.slider_smooth.valueChanged.connect(self._on_smooth_changed)
        lay_smooth.addWidget(self.slider_smooth)

        layout.addWidget(grp_smooth)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #1e2636;
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);
                border-radius: 4px;
            }
        """)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 11px;")
        self.lbl_status.hide()
        layout.addWidget(self.lbl_status)

        # 4. ACTION BUTTONS
        h_actions = QHBoxLayout()
        h_actions.setSpacing(8)

        self.btn_cancel = QPushButton("បោះបង់ (Cancel)")
        self.btn_cancel.clicked.connect(self.reject)
        h_actions.addWidget(self.btn_cancel)

        h_actions.addStretch()

        self.btn_apply = QPushButton("🔍 វិភាគ & ដាក់ Keyframes លើ Timeline")
        self.btn_apply.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: bold;
                border: 1px solid #38bdf8;
                padding: 7px 16px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
        """)
        self.btn_apply.clicked.connect(self._start_analysis)
        h_actions.addWidget(self.btn_apply)

        self.btn_export = QPushButton("🎬 Export 9:16 TikTok MP4")
        self.btn_export.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: #ffffff;
                font-weight: bold;
                border: 1px solid #10b981;
                padding: 7px 16px;
            }
            QPushButton:hover {
                background-color: #047857;
            }
        """)
        self.btn_export.clicked.connect(self._start_export)
        self.btn_export.setEnabled(False)
        h_actions.addWidget(self.btn_export)

        layout.addLayout(h_actions)

    def _on_dead_zone_toggled(self, checked: bool):
        self.slider_dead_zone.setEnabled(checked)
        if not checked:
            self.lbl_dz_val.setText("Disabled (0px)")
        else:
            self._on_dead_zone_changed(self.slider_dead_zone.value())

    def _on_dead_zone_changed(self, val: int):
        px = int(1080 * (val / 100.0))
        self.lbl_dz_val.setText(f"{val}% (ស្មើ ~{px}px ក្នុង 1080p)")

    def _on_smooth_changed(self, val: int):
        f = val / 100.0
        if f >= 0.8:
            tag = "Hollywood Steadicam Gliding"
        elif f >= 0.5:
            tag = "Natural Smooth Tracking"
        else:
            tag = "Responsive / Quick Cuts"
        self.lbl_smooth_val.setText(f"{f:.2f} ({tag})")

    def _get_mode_str(self) -> str:
        if self.radio_smart.isChecked():
            return "smart"
        elif self.radio_speaker.isChecked():
            return "speaker"
        elif self.radio_multi.isChecked():
            return "multi"
        return "face"

    def _browse_video(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video for Smart Auto Reframe",
            "",
            "Video Files (*.mp4 *.mkv *.mov *.avi *.webm)"
        )
        if f:
            self.video_path = f
            self.lbl_video_name.setText(os.path.basename(f))
            self.video_selected.emit(f)

    def _start_analysis(self):
        if not self.video_path or not os.path.exists(self.video_path):
            self._browse_video()
            if not self.video_path or not os.path.exists(self.video_path):
                QMessageBox.warning(self, "No Video", "សូមជ្រើសរើសវីដេអូជាមុនសិន មុននឹងចាប់ផ្ដើម Auto Reframe!")
                return

        mode = self._get_mode_str()
        smooth = self.slider_smooth.value() / 100.0
        dz_ratio = (self.slider_dead_zone.value() / 100.0) if self.chk_dead_zone.isChecked() else 0.0

        self.btn_apply.setEnabled(False)
        self.progress_bar.show()
        self.lbl_status.show()
        self.lbl_status.setText("កំពុងដំណើរការ Smart Detection & Anti-Dizziness Tracking...")

        self._worker = AutoReframeWorker(self.video_path, mode, smooth, dead_zone_ratio=dz_ratio)
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()

    def _on_worker_progress(self, pct: float, msg: str):
        self.progress_bar.setValue(int(pct * 100))
        self.lbl_status.setText(msg)

    def _on_worker_finished(self, result: dict):
        self.btn_apply.setEnabled(True)
        self.progress_bar.hide()
        self.lbl_status.setText("✅ Smart Auto Reframe ជោគជ័យ!")
        self.analysis_result = result

        if result and "keyframes" in result:
            self.btn_export.setEnabled(True)
            self.reframe_applied.emit(result)

            stats = result.get("stats", {})
            dcounts = stats.get("decision_counts", {})
            steady_pct = stats.get("locked_steady_pct", 0.0)
            single_cnt = dcounts.get("single", 0)
            group_cnt = dcounts.get("group", 0)
            speaker_cnt = dcounts.get("speaker", 0)

            msg = (
                f"🎉 Smart Auto Reframe ត្រូវបានវិភាគជោគជ័យ!\n\n"
                f"📊 ស្ថិតិនៃការសម្រេចចិត្តចាប់ប្លង់:\n"
                f"• ប្លង់មនុស្សម្នាក់ (Single Person): {single_cnt} ដង\n"
                f"• ប្លង់មនុស្សច្រើននាក់ (Group Framing): {group_cnt} ដង\n"
                f"• ប្លង់អ្នកកំពុងនិយាយ (Speaker Focus): {speaker_cnt} ដង\n"
                f"• ប្លង់ស្ងប់មិនញ័រ (Camera Locked Steady): {steady_pct}% (មិនធ្វើឱ្យអ្នកមើលវិលមុខ)\n\n"
                f"បានបង្កើត {len(result['keyframes'])} Camera Keyframes ដាក់លើ Timeline រួចរាល់!\n"
                "អ្នកអាចចុច 'Export 9:16 TikTok MP4' ដើម្បី Render វីដេអូចេញបានភ្លាមៗ!"
            )

            QMessageBox.information(self, "Smart Reframe Complete", msg)

    def _on_worker_error(self, err_msg: str):
        self.btn_apply.setEnabled(True)
        self.progress_bar.hide()
        self.lbl_status.setText(f"❌ កំហុស: {err_msg}")
        QMessageBox.critical(self, "Error", f"Auto Reframe Error:\n{err_msg}")

    def _start_export(self):
        if not self.analysis_result or "trajectory" not in self.analysis_result:
            return

        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save 9:16 TikTok Vertical Video",
            os.path.splitext(self.video_path)[0] + "_tiktok_9_16.mp4",
            "MP4 Video (*.mp4)"
        )
        if not out_path:
            return

        self.btn_export.setEnabled(False)
        self.progress_bar.show()
        self.lbl_status.show()
        self.lbl_status.setText("កំពុង Render វីដេអូបញ្ឈរ 9:16 TikTok...")

        self._export_worker = AutoReframeExportWorker(
            video_path=self.video_path,
            trajectory=self.analysis_result["trajectory"],
            output_path=out_path
        )
        self._export_worker.progress.connect(self._on_worker_progress)
        self._export_worker.finished.connect(self._on_export_finished)
        self._export_worker.error.connect(self._on_worker_error)
        self._export_worker.start()

    def _on_export_finished(self, ok: bool, path: str):
        self.btn_export.setEnabled(True)
        self.progress_bar.hide()
        if ok:
            self.lbl_status.setText("🎉 Render ជោគជ័យ!")
            QMessageBox.information(
                self,
                "Export Complete",
                f"វីដេអូ TikTok 9:16 ត្រូវបាន Render រួចរាល់:\n\n{path}"
            )
            self.accept()
        else:
            self.lbl_status.setText("❌ Export បរាជ័យ!")

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(1000)
        if self._export_worker and self._export_worker.isRunning():
            self._export_worker.cancel()
            self._export_worker.wait(1000)
        super().closeEvent(event)
