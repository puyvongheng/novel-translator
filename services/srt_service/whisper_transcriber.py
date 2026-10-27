"""
Whisper Transcriber Service
High-accuracy speech-to-text with VAD filtering, word-level timestamps,
real-time progress reporting, and automatic CPU retry on CUDA failure.
"""

import os
import time
from services.srt_service.whisper_runtime import WhisperModelLoader, is_cuda_runtime_available
from services.srt_service.audio_extractor import AudioExtractor


class WhisperTranscriber:
    """
    Continuous movie dialogue transcription using Faster-Whisper.
    """

    def __init__(self, model_size: str = "base", device: str = "auto"):
        self.model_size = model_size
        self.device = device

    def transcribe(
        self,
        media_path: str,
        source_lang: str = "auto",
        progress_callback=None,
        is_cancelled=None
    ) -> list[dict]:
        """
        Transcribes continuous movie speech into timestamped dialogue items.
        media_path can be an audio file (.mp3, .wav, .m4a) or a video file (.mp4, .mkv).
        Returns a list of raw subtitle segment dicts.
        """
        temp_wav = None
        # If input is a video file or compressed audio, extract normalized 16kHz mono WAV
        if not media_path.lower().endswith(".wav"):
            if progress_callback:
                progress_callback("Extracting normalized 16kHz audio for speech recognition...", 0.05)
            temp_wav = AudioExtractor.extract_asr_wav(media_path)
            input_audio = temp_wav
        else:
            input_audio = media_path

        try:
            return self._run_transcribe_with_fallback(
                audio_path=input_audio,
                source_lang=source_lang,
                progress_callback=progress_callback,
                is_cancelled=is_cancelled
            )
        finally:
            if temp_wav and os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except Exception:
                    pass

    def _run_transcribe_with_fallback(
        self,
        audio_path: str,
        source_lang: str,
        progress_callback,
        is_cancelled=None
    ) -> list[dict]:
        """Runs transcription with automatic CPU fallback if CUDA fails at any point."""
        try:
            return self._do_transcribe(
                audio_path=audio_path,
                source_lang=source_lang,
                device_preference=self.device,
                progress_callback=progress_callback,
                is_cancelled=is_cancelled
            )
        except RuntimeError as r_err:
            err_msg = str(r_err)
            if "cublas" in err_msg.lower() or "cuda" in err_msg.lower():
                if progress_callback:
                    progress_callback("⚠️ CUDA library not found. Falling back to multi-core CPU (int8)...", 0.20)
                print(f"[WhisperTranscriber] CUDA runtime error ({err_msg}). Auto-retrying on CPU...")
                return self._do_transcribe(
                    audio_path=audio_path,
                    source_lang=source_lang,
                    device_preference="cpu",
                    progress_callback=progress_callback,
                    is_cancelled=is_cancelled
                )
            raise r_err

    def _do_transcribe(
        self,
        audio_path: str,
        source_lang: str,
        device_preference: str,
        progress_callback,
        is_cancelled=None
    ) -> list[dict]:
        if progress_callback:
            progress_callback(f"Loading Whisper model ({self.model_size})...", 0.15)

        model = WhisperModelLoader.get_model(
            model_size=self.model_size,
            device=device_preference
        )

        if progress_callback:
            progress_callback("Recognizing movie dialogue and speech timestamps...", 0.30)

        lang_param = source_lang if source_lang not in ["auto", "Auto Detect", "", None] else None

        segments, info = model.transcribe(
            audio_path,
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

        total_duration = getattr(info, "duration", 0.0) or 0.0
        raw_segs = []
        last_cb_time = 0.0
        start_transcribe_time = time.time()

        for seg in segments:
            if is_cancelled and is_cancelled():
                if progress_callback:
                    progress_callback("🛑 ការស្ដាប់សន្ទនាត្រូវបានបញ្ឈប់ដោយអ្នកប្រើប្រាស់!", 1.0)
                break
            raw_segs.append(seg)
            now = time.time()
            if progress_callback and (now - last_cb_time >= 0.8):
                last_cb_time = now
                if total_duration > 0:
                    cur_t = min(seg.end, total_duration)
                    # Real audio percentage (1% - 99%)
                    pct_val = max(1, min(99, int((cur_t / total_duration) * 100)))
                    pct_norm = min(0.98, 0.15 + (cur_t / total_duration) * 0.83)

                    # Dynamic ETA calculation based on real processing speed
                    elapsed_wall = max(0.4, now - start_transcribe_time)
                    if cur_t >= 3.0:
                        speed_ratio = cur_t / elapsed_wall  # audio seconds processed per real-time second
                        rem_audio_sec = max(0.0, total_duration - cur_t)
                        eta_seconds = rem_audio_sec / max(0.01, speed_ratio)
                        if eta_seconds >= 60:
                            eta_m, eta_s = divmod(int(eta_seconds), 60)
                            eta_str = f" | នៅសល់ប្រហែល: ~{eta_m} នាទី {eta_s:02d} វិ (ETA: {eta_m:02d}:{eta_s:02d})"
                        else:
                            eta_str = f" | នៅសល់ប្រហែល: ~{max(1, int(eta_seconds))} វិនាទី (ETA: ~{max(1, int(eta_seconds))}s)"
                    else:
                        eta_str = " | កំពុងគណនាពេល..."

                    m_c, s_c = divmod(int(cur_t), 60)
                    m_t, s_t = divmod(int(total_duration), 60)
                    progress_callback(
                        f"⚡ [{pct_val}%] {m_c:02d}:{s_c:02d} / {m_t:02d}:{s_t:02d} ({len(raw_segs)} បន្ទាត់){eta_str}",
                        pct_norm
                    )
                else:
                    progress_callback(f"⚡ កំពុងស្ដាប់សន្ទនា... រកឃើញ {len(raw_segs)} បន្ទាត់", 0.5)

        if progress_callback and total_duration > 0:
            m_t, s_t = divmod(int(total_duration), 60)
            progress_callback(
                f"✅ [100%] ស្ដាប់ចប់សព្វគ្រប់: {m_t:02d}:{s_t:02d} (សរុប {len(raw_segs)} បន្ទាត់)",
                1.0
            )

        dialogues = []
        for idx, seg in enumerate(raw_segs):
            text = seg.text.strip()
            if not text:
                continue

            # Precise word-level boundary alignment
            if hasattr(seg, "words") and seg.words:
                s_sec = max(0.0, seg.words[0].start - 0.05)
                e_sec = seg.words[-1].end + 0.10
            else:
                s_sec = seg.start
                e_sec = seg.end

            if e_sec <= s_sec:
                e_sec = s_sec + 0.35

            dialogues.append({
                "id": len(dialogues) + 1,
                "start": round(s_sec, 2),
                "end": round(e_sec, 2),
                "orig_text": text,
                "original": text,
                "text": text,
                "khmer_text": "",
                "translated": "",
                "audio_file": None,
                "rate": "+0%",
                "status": "raw"
            })

        if progress_callback:
            progress_callback(f"Recognized {len(dialogues)} dialogue lines successfully!", 1.0)

        return dialogues
