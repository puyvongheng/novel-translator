"""
AI Voice Dubbing Services Package
Handles multi-model dialogue voice synthesis, timing alignment, audio effects, and ducking.
"""

from services.dubbing.dubbing_engine import DubbingEngine
from services.dubbing.cloning import (
    CLONED_VOICES_FILE,
    get_cloned_voices,
    save_cloned_voice,
    delete_cloned_voice,
    analyze_voice_sample,
    extract_reference_acoustic_profile,
)
from services.dubbing.audio_effects import (
    PRESET_EFFECTS,
    CAPCUT_VOICE_EFFECTS,
    build_voice_filters,
    apply_audio_effects,
    apply_voice_effect_to_file,
    preview_voice_effect,
)
from services.dubbing.timing_ducking import (
    calculate_auto_rate,
    get_audio_duration,
    fit_audio_to_duration,
    change_audio_speed,
    merge_dub_with_movie,
)
from services.dubbing.track_assembler import (
    generate_segment_files,
    assemble_dubbed_audio,
    assemble_synchronized_timeline,
    mix_movie_with_dubbed_audio,
)

__all__ = [
    "DubbingEngine",
    # Cloning
    "CLONED_VOICES_FILE",
    "get_cloned_voices",
    "save_cloned_voice",
    "delete_cloned_voice",
    "analyze_voice_sample",
    "extract_reference_acoustic_profile",
    # Effects
    "PRESET_EFFECTS",
    "build_voice_filters",
    "apply_audio_effects",
    # Timing & Ducking
    "calculate_auto_rate",
    "get_audio_duration",
    "fit_audio_to_duration",
    "merge_dub_with_movie",
    # Track Assembly
    "generate_segment_files",
    "assemble_dubbed_audio",
    "assemble_synchronized_timeline",
]

