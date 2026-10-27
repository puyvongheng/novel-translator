"""
Speech Recognition Engine (Facade & Legacy Compatibility)
Powered by Faster-Whisper and Alibaba FunASR with automatic CPU fallback.
Delegates core processing to services.srt_service.
"""

import os
from services.translation.translator import TranslationService
from services.srt_service import (
    AudioExtractor,
    WhisperModelLoader,
    WhisperTranscriber,
    WhisperXTranscriber,
    FunASRTranscriber,
    SrtFormatter,
    is_cuda_runtime_available
)


class SpeechRecognitionEngine:
    """
    OOP Speech Recognition Engine powered by Faster-Whisper & FunASR.
    Extracts audio from video, detects speech timestamps, and translates.
    Safely falls back to CPU if CUDA libraries (e.g. cublas64_12.dll) are missing.
    """

    def __init__(self, model_size: str = "base", device: str = "auto"):
        self.model_size = model_size
        self.device = device
        self._transcriber = WhisperTranscriber(model_size=model_size, device=device)

    def _get_model(self):
        """Legacy access to cached WhisperModel instance."""
        return WhisperModelLoader.get_model(model_size=self.model_size, device=self.device)

    def set_model_size(self, new_size: str):
        if new_size != self.model_size:
            self.model_size = new_size
            self._transcriber = WhisperTranscriber(model_size=new_size, device=self.device)

    def extract_audio(self, video_path: str, output_wav: str) -> bool:
        """Extracts mono 16kHz audio with speech bandpass & dynamic normalization for optimal Whisper transcription"""
        try:
            AudioExtractor.extract_asr_wav(video_path, output_wav=output_wav)
            return True
        except Exception:
            return False

    def transcribe_continuous(
        self,
        video_path: str,
        source_lang: str = "auto",
        progress_callback=None,
        is_cancelled=None
    ) -> list:
        """
        Transcribes continuous movie speech into timestamped subtitles without auto-translation.
        Automatically falls back to CPU (int8) if CUDA libraries (cublas64_12.dll) are missing.
        """
        transcriber = WhisperTranscriber(model_size=self.model_size, device=self.device)
        return transcriber.transcribe(
            media_path=video_path,
            source_lang=source_lang,
            progress_callback=progress_callback,
            is_cancelled=is_cancelled
        )

    def transcribe_with_whisperx(
        self,
        video_path: str,
        source_lang: str = "auto",
        progress_callback=None,
        is_cancelled=None,
        enable_diarization: bool = True,
        hf_token: str = None
    ) -> list:
        """
        Transcribes dialogue with WhisperX:
        Forced Phoneme Alignment (Word-level timestamps) + PyAnnote Speaker Diarization (Actor A / Actor B).
        """
        transcriber = WhisperXTranscriber(
            model_size=self.model_size,
            device=self.device,
            hf_token=hf_token
        )
        return transcriber.transcribe(
            media_path=video_path,
            source_lang=source_lang,
            progress_callback=progress_callback,
            is_cancelled=is_cancelled,
            enable_diarization=enable_diarization
        )

    def transcribe_and_translate(
        self,
        video_path: str,
        translator_service: TranslationService,
        source_lang: str = "zh",
        target_lang: str = "km",
        progress_callback=None
    ) -> list:
        """
        Executes pipeline: Audio extract -> Whisper transcribe -> Translation -> Subtitle list
        """
        subtitles = self.transcribe_continuous(
            video_path=video_path,
            source_lang=source_lang,
            progress_callback=progress_callback
        )

        if not subtitles:
            return []

        if progress_callback:
            progress_callback(f"Detected {len(subtitles)} dialogue lines. Translating...", 0.6)

        if hasattr(translator_service, "translate_subtitles_parallel"):
            translator_service.translate_subtitles_parallel(
                subtitles=subtitles,
                source_lang=source_lang,
                target_lang=target_lang,
                batch_size=15,
                max_workers=16,
                progress_callback=progress_callback
            )
        else:
            for sub in subtitles:
                sub["translated"] = translator_service.translate_text(
                    sub.get("orig_text") or sub.get("original", ""),
                    source_lang=source_lang,
                    target_lang=target_lang
                )
                sub["khmer_text"] = sub["translated"]

        if progress_callback:
            progress_callback("Translation finished successfully!", 1.0)

        return subtitles

    def transcribe_with_funasr(
        self,
        video_path: str,
        progress_callback=None,
        enable_diarization: bool = True
    ) -> list:
        """
        Transcribes speech using Alibaba SenseVoice-Small & CAM++ Speaker Diarization.
        Extracts multi-lingual dialogue, emotions (SER), audio events (AED), and speaker identities.
        """
        return FunASRTranscriber.transcribe(
            video_path,
            progress_callback=progress_callback,
            enable_diarization=enable_diarization
        )

    def compare_speakers(
        self,
        audio1: str,
        audio2: str,
        threshold: float = 0.60
    ) -> dict:
        """
        Compares two audio clips using CAM++ to determine if they belong to the same person or different people.
        """
        from services.srt_service.speaker_verification import SpeakerVerificationService
        return SpeakerVerificationService.compare_speakers(audio1, audio2, threshold=threshold)
