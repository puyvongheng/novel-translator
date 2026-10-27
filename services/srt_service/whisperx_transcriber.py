"""
WhisperX Transcriber Service
Advanced ASR engine built on Faster-Whisper featuring:
1. Fast multi-language speech-to-text
2. Forced Phoneme Alignment for exact word-level timestamps (wav2vec2)
3. Speaker Diarization (PyAnnote) to identify Actor A, Actor B, etc.
4. Automatic character voice and gender mapping for multi-role movie dubbing.
5. Seamless graceful fallback to Faster-Whisper if whisperx is not yet installed.
"""

import os
import re
from typing import Optional, List, Dict, Any
from services.srt_service.audio_extractor import AudioExtractor


class WhisperXTranscriber:
    """
    Next-generation speech recognition with Speaker Diarization and Word-Level Timestamps.
    """

    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "auto",
        hf_token: Optional[str] = None
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.hf_token = hf_token or os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")

    @staticmethod
    def is_whisperx_available() -> bool:
        """Checks if whisperx package is installed in the current environment."""
        try:
            import whisperx
            return True
        except ImportError:
            return False

    def transcribe(
        self,
        media_path: str,
        source_lang: str = "auto",
        progress_callback=None,
        is_cancelled=None,
        enable_diarization: bool = True,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Transcribes speech using WhisperX pipeline:
        Audio Extract -> Faster-Whisper ASR -> wav2vec2 Word Alignment -> PyAnnote Speaker Diarization.
        Falls back to standard Faster-Whisper if whisperx is missing.
        """
        if not self.is_whisperx_available():
            if progress_callback:
                progress_callback(
                    "⚠️ [WhisperX] កញ្ចប់ whisperx មិនទាន់បានដំឡើងទេ។ កំពុងប្រើប្រាស់ Faster-Whisper ជាស្វ័យប្រវត្តិ... "
                    "(ដើម្បីប្រើ Diarization សូម run: pip install whisperx pyannote.audio)",
                    0.10
                )
            from services.srt_service.whisper_transcriber import WhisperTranscriber
            fallback_transcriber = WhisperTranscriber(model_size=self.model_size, device=self.device)
            return fallback_transcriber.transcribe(
                media_path=media_path,
                source_lang=source_lang,
                progress_callback=progress_callback,
                is_cancelled=is_cancelled
            )

        temp_wav = None
        if not media_path.lower().endswith(".wav"):
            if progress_callback:
                progress_callback("Extracting normalized audio for WhisperX...", 0.05)
            temp_wav = AudioExtractor.extract_asr_wav(media_path)
            input_audio = temp_wav
        else:
            input_audio = media_path

        try:
            import torch
            import whisperx

            if is_cancelled and is_cancelled():
                return []

            # 1. Device and compute type resolution
            has_cuda = torch.cuda.is_available()
            resolved_device = "cuda" if (self.device == "cuda" or (self.device == "auto" and has_cuda)) else "cpu"
            resolved_compute = "float16" if resolved_device == "cuda" else "int8"
            if self.compute_type != "auto":
                resolved_compute = self.compute_type

            if progress_callback:
                progress_callback(f"🎯 [WhisperX] កំពុងផ្ទុក Model {self.model_size} ({resolved_device.upper()} / {resolved_compute})...", 0.15)

            # 2. Stage 1: Transcription (Faster-Whisper Backend)
            batch_size = 16 if resolved_device == "cuda" else 4
            lang_param = None if source_lang == "auto" else source_lang
            model = whisperx.load_model(
                self.model_size,
                device=resolved_device,
                compute_type=resolved_compute,
                language=lang_param
            )

            if is_cancelled and is_cancelled():
                return []

            audio = whisperx.load_audio(input_audio)
            if progress_callback:
                progress_callback("🎯 [WhisperX] កំពុងវិភាគ និងសម្គាល់សំឡេងនិយាយ...", 0.35)

            result = model.transcribe(audio, batch_size=batch_size, language=lang_param)
            detected_lang = result.get("language", "en")

            if is_cancelled and is_cancelled():
                return []

            # 3. Stage 2: Forced Alignment (Word-level timestamps via wav2vec2)
            try:
                if progress_callback:
                    progress_callback(f"🎯 [WhisperX] កំពុងតម្រឹមម៉ោងកម្រិតពាក្យ (Word-level Alignment: {detected_lang})...", 0.60)

                align_model, metadata = whisperx.load_align_model(
                    language_code=detected_lang,
                    device=resolved_device
                )
                aligned_result = whisperx.align(
                    result["segments"],
                    align_model,
                    metadata,
                    audio,
                    resolved_device,
                    return_char_alignments=False
                )
                segments = aligned_result.get("segments", result.get("segments", []))
            except Exception as align_err:
                if progress_callback:
                    progress_callback(f"⚠️ [WhisperX Alignment] រំលង Word Alignment ({align_err}), បន្តប្រើ Segment Timestamps...", 0.65)
                segments = result.get("segments", [])

            if is_cancelled and is_cancelled():
                return []

            # 4. Stage 3: Speaker Diarization (Who speaks what: Actor A vs Actor B)
            speaker_detected = False
            if enable_diarization:
                try:
                    token = self.hf_token
                    if progress_callback:
                        progress_callback("🎯 [WhisperX] កំពុងបំបែកសំឡេងតួអង្គ (Speaker Diarization)...", 0.75)

                    diarize_pipeline = whisperx.DiarizationPipeline(
                        use_auth_token=token,
                        device=resolved_device
                    )
                    diarize_kwargs = {}
                    if min_speakers:
                        diarize_kwargs["min_speakers"] = min_speakers
                    if max_speakers:
                        diarize_kwargs["max_speakers"] = max_speakers

                    diarize_segments = diarize_pipeline(audio, **diarize_kwargs)
                    aligned_with_spk = whisperx.assign_word_speakers(diarize_segments, {"segments": segments})
                    segments = aligned_with_spk.get("segments", segments)
                    speaker_detected = True
                except Exception as diarize_err:
                    if progress_callback:
                        progress_callback(
                            f"ℹ️ [WhisperX Diarization] PyAnnote Diarization មិនដំណើរការ ({diarize_err}). "
                            "បន្តដំណើរការ Subtitles ដោយគ្មានការបែងចែកតួអង្គស្វ័យប្រវត្តិ។",
                            0.80
                        )

            # 5. Stage 4: Normalize to Movie Studio Subtitle Structure & Voice Assignment
            subtitles = []
            known_speakers = []

            for idx, seg in enumerate(segments):
                text = (seg.get("text") or "").strip()
                if not text:
                    continue

                start = float(seg.get("start", 0.0))
                end = float(seg.get("end", start + 1.0))
                if end <= start:
                    end = start + 0.4

                spk_id = seg.get("speaker")
                if spk_id:
                    if spk_id not in known_speakers:
                        known_speakers.append(spk_id)
                    spk_idx = known_speakers.index(spk_id)
                    actor_label = f"តួអង្គ {chr(65 + spk_idx)}"  # Actor A, Actor B, etc.
                    # Alternate voice profiles: Even -> Male (Piseth), Odd -> Female (Sreymom)
                    is_female = (spk_idx % 2 == 1)
                    voice_gender = "female" if is_female else "male"
                    assigned_voice = "km-KH-SreymomNeural" if is_female else "km-KH-PisethNeural"
                else:
                    spk_id = "SPEAKER_00"
                    actor_label = "តួអង្គទូទៅ"
                    voice_gender = "male"
                    assigned_voice = "km-KH-PisethNeural"

                words = seg.get("words", [])

                subtitles.append({
                    "id": len(subtitles) + 1,
                    "start": round(start, 3),
                    "end": round(end, 3),
                    "orig_text": text,
                    "original": text,
                    "text": text,
                    "khmer_text": "",
                    "translated": "",
                    "speaker": spk_id,
                    "actor": actor_label,
                    "gender": voice_gender,
                    "voice_name": assigned_voice,
                    "words": words,
                    "rate": "+0%",
                    "status": "raw"
                })

            if progress_callback:
                spk_msg = f" រកឃើញតួអង្គ {len(known_speakers)} នាក់" if known_speakers else ""
                progress_callback(f"✅ WhisperX រួចរាល់! ចាប់បាន {len(subtitles)} បន្ទាត់{spk_msg}។", 1.0)

            return subtitles

        except Exception as e:
            if progress_callback:
                progress_callback(f"❌ [WhisperX Error] {e}", 1.0)
            raise e
        finally:
            if temp_wav and os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except Exception:
                    pass
