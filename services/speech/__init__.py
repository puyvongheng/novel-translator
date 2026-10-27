"""
Speech Services Package
Provides:
- Faster-Whisper Continuous Transcription (SpeechRecognitionEngine)
- Microsoft Edge-TTS Neural Voice Model (EdgeTTSModel)
- Google Gemini 2.0 AI Audio Speech Model (GeminiTTSModel)
- Google Cloud TTS Voice Model (GoogleCloudTTSModel)
- Unified Khmer Voice Synthesis Manager (generate_speech_file, generate_voice_file)
"""

from services.speech.speech_engine import SpeechRecognitionEngine
from services.speech.edge_tts_model import EdgeTTSModel, generate_edge_tts
from services.speech.gemini_tts_model import GeminiTTSModel, generate_gemini_tts
from services.speech.google_cloud_tts_model import GoogleCloudTTSModel, generate_google_cloud_tts
from services.speech.khmer_tts import (
    generate_speech_file,
    generate_voice_file,
    generate_voice_file_sync,
    generate_khmer_dubbing,
    merge_video_with_dubbing,
    KHMER_VOICES
)

__all__ = [
    "SpeechRecognitionEngine",
    "EdgeTTSModel",
    "generate_edge_tts",
    "GeminiTTSModel",
    "generate_gemini_tts",
    "GoogleCloudTTSModel",
    "generate_google_cloud_tts",
    "generate_speech_file",
    "generate_voice_file",
    "generate_voice_file_sync",
    "generate_khmer_dubbing",
    "merge_video_with_dubbing",
    "KHMER_VOICES"
]
