# AI Khmer Movie Studio - Architecture & Engineering Guide

## 1. Overview
AI Khmer Movie Studio is an end-to-end desktop software for translating, subtitle timing, voice cloning/dubbing, and burning movie dialogues (Chinese/English/Foreign to Khmer) with synchronized multi-track audio.

## 2. Directory & Module Responsibilities

```text
tool tleslet souns movie/
├── models/                     # [DATA LAYER] Structured entities, state machines & schemas
│   ├── __init__.py             # Exports EditorModel, SubtitleItem, GlobalBrandingProfile, etc.
│   ├── editor_model.py         # Multi-clip timeline, tracks, filters, undo/redo
│   ├── subtitle_model.py       # Typed SubtitleItem dataclass
│   └── branding_model.py       # KeyframePoint, MotionPathAnimation, SponsorAdItem, GlobalBrandingProfile
│
├── services/                   # [BUSINESS LOGIC & ENGINE LAYER]
│   ├── __init__.py             # Unified exports for all domain services
│   ├── translation/            # Text translation engines (Google GTX, Gemini, ChatGPT)
│   │   ├── __init__.py         # TranslationService, engines & pipelines
│   │   ├── google_translator.py# Google Multi-Client Free GTX Engine
│   │   ├── gemini_translator.py# Google Gemini AI Dialogue Translation
│   │   ├── chatgpt_translator.py# OpenAI ChatGPT Dubbing Translation
│   │   ├── mymemory_translator.py# MyMemory Free Translation Service
│   │   ├── translator.py       # TranslationService Orchestrator & Multi-Threading
│   │   └── translator_engine.py# Audio extraction, Whisper transcription & GTX translation
│   ├── srt_service/            # [SRT & ASR PIPELINE] Modular Speech-to-SRT & Audio Tools
│   │   ├── __init__.py         # Package exports (Whisper, WhisperX, FunASR, AudioExtractor, SrtFormatter)
│   │   ├── audio_extractor.py  # FFmpeg audio extraction (mono 16kHz for ASR, stereo MP3 for cinema)
│   │   ├── whisper_runtime.py  # Safe CUDA cuBLAS DLL check & multi-thread CPU int8 auto-fallback
│   │   ├── whisper_transcriber.py # Faster-Whisper VAD dialogue transcription & safe retry
│   │   ├── whisperx_transcriber.py# WhisperX Forced Alignment (Word timestamps) & Diarization (Actor A/B)
│   │   ├── funasr_transcriber.py  # Alibaba DAMO FunASR Chinese Paraformer + VAD transcription
│   │   ├── srt_formatter.py    # Subtitle dictionary normalization, overlap fixer & SRT file generation
│   │   └── srt_pipeline.py     # End-to-end 1-call orchestrator: Video -> ASR -> Fixed Timestamps -> SRT
│   ├── speech/                 # Speech recognition (Whisper) & TTS voice generation
│   │   ├── __init__.py         # SpeechRecognitionEngine, models & voice generators
│   │   ├── speech_engine.py    # SpeechRecognitionEngine Facade (delegates to srt_service)
│   │   ├── edge_tts_model.py   # Edge-TTS Neural Khmer Model (Piseth, Sreymom)
│   │   ├── gemini_tts_model.py # Google Gemini 2.0 AI Audio Speech Model
│   │   ├── google_cloud_tts_model.py # Google Cloud TTS Model (km-KH-Standard-A/B)
│   │   └── khmer_tts.py        # Multi-model TTS Orchestrator & Movie Dub Mix
│   ├── dubbing/                # AI Voice dubbing, timing stretching & audio ducking
│   │   ├── __init__.py         # Package exports (DubbingEngine & utility functions)
│   │   ├── dubbing_engine.py   # DubbingEngine Orchestrator (Coordinates pipeline)
│   │   ├── cloning.py          # Voice cloning profile extraction, analysis & storage
│   │   ├── audio_effects.py    # Studio audio filters, equalizers, preset effects & BGM
│   │   ├── timing_ducking.py   # Speech rate auto-calculation, duration fit & auto-ducking
│   │   └── track_assembler.py  # Parallel clip generation, synchronized mixer & 1-sec SRT dialogue mute
│   └── video/                  # Hardsub burning, audio mix & chunked export pipelines
│       ├── __init__.py         # SubtitleBurner, ChunkedPipeline, VideoChunk
│       ├── video_burner.py     # SubtitleBurner (NVENC, QSV, CPU ASS hardsub burning)
│       └── chunk_pipeline.py   # ChunkedPipeline, VideoChunk (background incremental rendering)
│
├── utils/                      # [SHARED UTILITIES]
│   ├── __init__.py             # Unified exports
│   ├── time_utils.py           # SRT timestamp formatting & conversions
│   ├── srt_utils.py            # Robust SRT/VTT file & content parsing & generation
│   ├── media_utils.py          # Ultra-fast OpenCV (<5ms) & ffprobe metadata probe
│   └── audio_player.py         # Resilient multi-backend audio player (Pygame/FFplay/OS)
│
├── ui_v_PyQt6/                 # [PRESENTATION LAYER - HIGH PERFORMANCE 60FPS]
│   ├── qt_compat.py            # Automatic dual-import bridge (PySide6 / PyQt6)
│   ├── styles.py               # Dark Studio QSS stylesheet with hardware acceleration
│   ├── components/             # [PANEL COMPONENTS BY DOMAIN]
│   │   ├── __init__.py         # Unified exports for all panel components
│   │   ├── header/             # HeaderView (Top navigation bar & quick actions)
│   │   ├── player/             # PlayerView (Video Monitor & Transport playback)
│   │   ├── timeline/           # TimelineEditor & 60fps TimelineCanvas (Multi-track editing)
│   │   ├── subtitles/          # SubtitlesView (Virtualized 60fps table & editor)
│   │   ├── dubbing_export/     # DubbingExportView (Audio mixing & render settings)
│   │   ├── quick_speech/       # QuickSpeechView (Custom text AI voice studio)
│   │   ├── downloader/         # VideoDownloaderView (Turbo downloader & diagnostics)
│   │   ├── srt_splitter/       # SrtSplitterView (SRT Subtitle Splitter & AI Dialogue Chunker)
│   │   ├── video_tools/        # VideoToolsView (Shorts Splitter, Merger & MP3/MP4 Tools)
│   │   └── branding/           # BrandingView (Global Branding, Sponsor Ads & Motion Path Studio)
│   └── __init__.py             # Unified package exports
│
├── ui/                         # [LEGACY PRESENTATION LAYER - CUSTOMTKINTER]
│   └── (Kept intact for backward compatibility)
│
├── config.py                   # Central presets, voice profiles, constants & fonts
├── app_qt.py                   # Main Application Entry Point (PySide6/PyQt6 High Performance)
├── run_app_qt.bat              # Windows Launcher for Qt Edition
├── app.py                      # Application Entry Point (CustomTkinter Edition)
└── run_app.bat                 # Windows Launcher for CustomTkinter Edition
```

## 3. Development Guidelines for AI Agents
- **Preserve Clean Boundaries:**
  - Keep UI components in `ui_v_PyQt6/` and `ui/` decoupled from business logic.
  - Implement business logic, API calls, and file processing inside `services/`.
  - Store state and data structures inside `models/`.
  - Put shared helper functions in `utils/`.
- **Backward Compatibility:**
  - Keep `ui/` and `app.py` intact so legacy users can always launch `run_app.bat`.

## 4. Running & Verification
- **Run Qt Edition (Recommended):** `python app_qt.py` or double-click `run_app_qt.bat`.
- **Run Legacy CTk Edition:** `python app.py` or double-click `run_app.bat`.
- **Compile & Syntax Check:** `python -m py_compile app_qt.py app.py`.
