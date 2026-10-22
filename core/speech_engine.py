import os
import subprocess
import tempfile
import time
from core.translator import TranslationService

class SpeechRecognitionEngine:
    """
    OOP Speech Recognition Engine powered by Faster-Whisper.
    Extracts audio from video, detects speech timestamps, and translates.
    """
    def __init__(self, model_size: str = "base", device: str = "auto"):
        self.model_size = model_size
        self.device = device
        self._model = None

    def _get_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            try:
                self._model = WhisperModel(self.model_size, device=self.device if self.device != "auto" else "cpu", compute_type="int8")
            except Exception:
                self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        return self._model

    def set_model_size(self, new_size: str):
        if new_size != self.model_size:
            self.model_size = new_size
            self._model = None  # Re-init next time

    def extract_audio(self, video_path: str, output_wav: str) -> bool:
        """Extracts mono 16kHz audio with speech bandpass & dynamic normalization for optimal Whisper transcription"""
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            "-af", "highpass=f=80,lowpass=f=7500,dynaudnorm=f=150:g=15",
            output_wav
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return res.returncode == 0

    def transcribe_continuous(
        self,
        video_path: str,
        source_lang: str = "auto",
        progress_callback=None
    ) -> list:
        """
        Transcribes continuous movie speech into timestamped subtitles without auto-translation
        """
        if progress_callback:
            progress_callback("Extracting audio from movie...", 0.05)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
            wav_path = tmp_audio.name

        try:
            if not self.extract_audio(video_path, wav_path):
                raise RuntimeError("Failed to extract audio from video using FFmpeg.")

            if progress_callback:
                progress_callback(f"Loading speech model ({self.model_size})...", 0.15)

            model = self._get_model()

            if progress_callback:
                progress_callback("Recognizing speech in movie dialogue...", 0.35)

            lang_param = source_lang if source_lang not in ["auto", "Auto Detect"] else None
            segments, info = model.transcribe(
                wav_path,
                language=lang_param,
                beam_size=1,
                temperature=0.0,
                word_timestamps=True,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=250,
                    speech_pad_ms=200,
                    threshold=0.45
                )
            )

            raw_segs = list(segments)
            segments_list = [s for s in raw_segs if s.text.strip()]
            total_segs = len(segments_list)
            if total_segs == 0:
                if progress_callback:
                    progress_callback("No speech detected.", 1.0)
                return []

            subtitles = []
            for idx, seg in enumerate(segments_list):
                if hasattr(seg, "words") and seg.words:
                    s_sec = max(0.0, seg.words[0].start - 0.05)
                    e_sec = seg.words[-1].end + 0.10
                else:
                    s_sec = seg.start
                    e_sec = seg.end
                if e_sec <= s_sec:
                    e_sec = s_sec + 0.35

                orig_text = seg.text.strip()
                subtitles.append({
                    "id": idx + 1,
                    "start": round(s_sec, 2),
                    "end": round(e_sec, 2),
                    "original": orig_text,
                    "translated": "",
                    "audio_file": None,
                    "rate": "+0%"
                })

            if progress_callback:
                progress_callback(f"Successfully captured {len(subtitles)} dialogue lines!", 1.0)

            return subtitles

        finally:
            if os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except Exception:
                    pass

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
        if progress_callback:
            progress_callback("Extracting audio from movie...", 0.05)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
            wav_path = tmp_audio.name

        try:
            if not self.extract_audio(video_path, wav_path):
                raise RuntimeError("Failed to extract audio from video using FFmpeg.")

            if progress_callback:
                progress_callback(f"Loading speech model ({self.model_size})...", 0.15)

            model = self._get_model()

            if progress_callback:
                progress_callback("Recognizing speech in movie dialogue...", 0.3)

            lang_param = source_lang if source_lang not in ["auto", "Auto Detect"] else None
            segments, info = model.transcribe(
                wav_path,
                language=lang_param,
                beam_size=1,
                temperature=0.0,
                word_timestamps=True,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=250,
                    speech_pad_ms=200,
                    threshold=0.45
                )
            )

            raw_segs = list(segments)
            segments_list = [s for s in raw_segs if s.text.strip()]
            total_segs = len(segments_list)
            if total_segs == 0:
                if progress_callback:
                    progress_callback("No speech detected.", 1.0)
                return []

            if progress_callback:
                progress_callback(f"Detected {total_segs} dialogue lines. Translating...", 0.5)

            subtitles = []
            for idx, seg in enumerate(segments_list):
                orig_text = seg.text.strip()
                if not orig_text:
                    continue
                # Frame-accurate second-by-second speech timing alignment
                if hasattr(seg, "words") and seg.words:
                    s_sec = max(0.0, seg.words[0].start - 0.05)
                    e_sec = seg.words[-1].end + 0.10
                else:
                    s_sec = seg.start
                    e_sec = seg.end
                if e_sec <= s_sec:
                    e_sec = s_sec + 0.35

                subtitles.append({
                    "id": len(subtitles) + 1,
                    "start": round(s_sec, 2),
                    "end": round(e_sec, 2),
                    "original": orig_text,
                    "translated": ""
                })

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
                    sub["translated"] = translator_service.translate_text(sub["original"], source_lang=source_lang, target_lang=target_lang)

            if progress_callback:
                progress_callback("Translation finished successfully!", 1.0)

            return subtitles

        finally:
            if os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except Exception:
                    pass
