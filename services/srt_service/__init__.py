"""
SRT Service Package
Unified, modular architecture for audio extraction, speech recognition (Faster-Whisper & FunASR),
automatic CUDA/CPU fallback, subtitle normalization, and .srt generation.
"""

from services.srt_service.audio_extractor import AudioExtractor
from services.srt_service.whisper_runtime import WhisperModelLoader, is_cuda_runtime_available
from services.srt_service.whisper_transcriber import WhisperTranscriber
from services.srt_service.whisperx_transcriber import WhisperXTranscriber
from services.srt_service.funasr_transcriber import FunASRTranscriber
from services.srt_service.speaker_verification import SpeakerVerificationService
from services.srt_service.srt_formatter import SrtFormatter
from services.srt_service.srt_pipeline import capture_video_subtitles
from services.srt_service.gender_splitter import GenderSrtSplitter

__all__ = [
    "AudioExtractor",
    "WhisperModelLoader",
    "is_cuda_runtime_available",
    "WhisperTranscriber",
    "WhisperXTranscriber",
    "FunASRTranscriber",
    "SpeakerVerificationService",
    "SrtFormatter",
    "capture_video_subtitles",
    "GenderSrtSplitter",
]
