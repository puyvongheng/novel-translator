"""
Translation Services Package
Supports:
- Google Multi-Client Free GTX Engine (GoogleTranslatorEngine)
- Google Gemini AI Dialogue Translation (GeminiTranslatorEngine)
- OpenAI ChatGPT Dubbing Translation (ChatGPTTranslatorEngine)
- MyMemory Translation Engine (MyMemoryTranslatorEngine)
- Groq LPU Fast Inference (GroqTranslatorEngine)
- OpenRouter Multi-Model Router (OpenRouterTranslatorEngine)
- NVIDIA NIM GPU Cloud Inference (NvidiaTranslatorEngine)
- Unified Translation Service Orchestrator (TranslationService)
- Continuous Whisper Audio Extraction & Subtitle Pipeline (transcribe_and_translate)
"""

from services.translation.translator import TranslationService, is_khmer_text
from services.translation.google_translator import GoogleTranslatorEngine, translate_google_gtx
from services.translation.gemini_translator import GeminiTranslatorEngine, translate_gemini
from services.translation.chatgpt_translator import ChatGPTTranslatorEngine, translate_chatgpt
from services.translation.mymemory_translator import MyMemoryTranslatorEngine, translate_mymemory
from services.translation.groq_translator import GroqTranslatorEngine, translate_groq
from services.translation.openrouter_translator import OpenRouterTranslatorEngine, translate_openrouter
from services.translation.nvidia_translator import NvidiaTranslatorEngine, translate_nvidia
from services.translation.translator_engine import (
    transcribe_and_translate,
    extract_audio,
    export_to_srt,
    burn_subtitles_to_video,
    get_video_info
)

__all__ = [
    "TranslationService",
    "is_khmer_text",
    "GoogleTranslatorEngine",
    "translate_google_gtx",
    "GeminiTranslatorEngine",
    "translate_gemini",
    "ChatGPTTranslatorEngine",
    "translate_chatgpt",
    "MyMemoryTranslatorEngine",
    "translate_mymemory",
    "GroqTranslatorEngine",
    "translate_groq",
    "OpenRouterTranslatorEngine",
    "translate_openrouter",
    "NvidiaTranslatorEngine",
    "translate_nvidia",
    "transcribe_and_translate",
    "extract_audio",
    "export_to_srt",
    "burn_subtitles_to_video",
    "get_video_info"
]
