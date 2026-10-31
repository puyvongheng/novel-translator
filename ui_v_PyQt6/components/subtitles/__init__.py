"""
Subtitles Component Package
"""

from ui_v_PyQt6.components.subtitles.subtitles_view import (
    SubtitlesView,
    VOICE_MODEL_OPTIONS,
    SPEED_OPTIONS,
)
from ui_v_PyQt6.components.subtitles.cc_model_benchmark_dialog import CCModelBenchmarkDialog

__all__ = [
    "SubtitlesView",
    "VOICE_MODEL_OPTIONS",
    "SPEED_OPTIONS",
    "CCModelBenchmarkDialog",
]
