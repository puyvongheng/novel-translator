"""
Panel Components Package for AI Khmer Movie Studio Qt Edition
Organized by functional studio panels:
- header: Studio Top Navigation & Action Bar
- player: Video Monitor & Playback Controls
- timeline: Multi-Track Zooming Timeline Editor & 60fps Canvas
- subtitles: Virtualized Subtitles Table & Dialogue Timing Editor
- dubbing_export: Multi-Track Audio Mixing, Watermark & Video Export
- quick_speech: Custom Text AI Voice Generation & MP3 Export
- downloader: Video Downloader & Live Console Diagnostics
"""

from ui_v_PyQt6.components.header import HeaderView
from ui_v_PyQt6.components.player import PlayerView, ObjectPropertiesPanel
from ui_v_PyQt6.components.timeline import TimelineCanvas, TimelineEditor, CapCutVoiceDialog
from ui_v_PyQt6.components.subtitles import SubtitlesView, VOICE_MODEL_OPTIONS, SPEED_OPTIONS
from ui_v_PyQt6.components.dubbing_export import DubbingExportView
from ui_v_PyQt6.components.quick_speech import QuickSpeechView
from ui_v_PyQt6.components.downloader import VideoDownloaderView
from ui_v_PyQt6.components.srt_splitter import SrtSplitterView
from ui_v_PyQt6.components.video_tools import VideoToolsView
from ui_v_PyQt6.components.branding import BrandingView
from ui_v_PyQt6.components.shortcuts_dialog import KeyboardShortcutsDialog

from ui_v_PyQt6.components.docking import StudioDockWidget, StudioDockContainer, StudioDockTitleBar
from ui_v_PyQt6.components.media_ai_panel import MediaAiPanel
from ui_v_PyQt6.components.responsive import (
    FlowLayout, AdaptiveToolbar, AdaptiveToolButton, Priority, 
    OverflowMenuManager, ResponsivePanel, ResponsiveBreakpoint, ResponsiveGrid
)

__all__ = [
    "HeaderView",
    "PlayerView",
    "ObjectPropertiesPanel",
    "TimelineCanvas",
    "TimelineEditor",
    "CapCutVoiceDialog",
    "SubtitlesView",
    "VOICE_MODEL_OPTIONS",
    "SPEED_OPTIONS",
    "DubbingExportView",
    "QuickSpeechView",
    "VideoDownloaderView",
    "SrtSplitterView",
    "VideoToolsView",
    "BrandingView",
    "KeyboardShortcutsDialog",
    "StudioDockWidget",
    "StudioDockContainer",
    "StudioDockTitleBar",
    "MediaAiPanel",
    "FlowLayout",
    "AdaptiveToolbar",
    "AdaptiveToolButton",
    "Priority",
    "OverflowMenuManager",
    "ResponsivePanel",
    "ResponsiveBreakpoint",
    "ResponsiveGrid",
]

