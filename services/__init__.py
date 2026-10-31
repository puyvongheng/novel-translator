"""
Core Services Unified Package for AI Khmer Movie Studio
Organized into domain subfolders:
- services.translation: Text translation services
- services.speech: Speech recognition & TTS services
- services.dubbing: AI voice dubbing & audio ducking
- services.video: Video burning & render pipelines
"""

from services.translation import TranslationService, is_khmer_text
from services.speech import (
    SpeechRecognitionEngine,
    EdgeTTSModel,
    GeminiTTSModel,
    GoogleCloudTTSModel,
    generate_voice_file
)
from services.dubbing import DubbingEngine
from services.video import SubtitleBurner, ChunkedPipeline, VideoChunk, SegmentEditorService
from services.srt_service import (
    AudioExtractor,
    WhisperModelLoader,
    WhisperTranscriber,
    FunASRTranscriber,
    SpeakerVerificationService,
    SrtFormatter,
    capture_video_subtitles
)

__all__ = [
    "TranslationService",
    "is_khmer_text",
    "SpeechRecognitionEngine",
    "EdgeTTSModel",
    "GeminiTTSModel",
    "GoogleCloudTTSModel",
    "generate_voice_file",
    "DubbingEngine",
    "SubtitleBurner",
    "ChunkedPipeline",
    "VideoChunk",
    "SegmentEditorService",
    "AudioExtractor",
    "WhisperModelLoader",
    "WhisperTranscriber",
    "FunASRTranscriber",
    "SpeakerVerificationService",
    "SrtFormatter",
    "capture_video_subtitles",
    "DownloaderService"
]

from services.downloader import DownloaderService

