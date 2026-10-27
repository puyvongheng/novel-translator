import os
import time
import subprocess
import tempfile
import threading
from services.translation.translator import TranslationService
from services.speech.speech_engine import SpeechRecognitionEngine
from services.dubbing.dubbing_engine import DubbingEngine

class VideoChunk:
    """
    Represents an incremental processing chunk (e.g. 30-60s) of movie dialogue.
    States: PENDING, PROCESSING, READY, PLAYING, FAILED
    """
    def __init__(self, chunk_id: int, start_sec: float, end_sec: float):
        self.chunk_id = chunk_id
        self.start_sec = round(start_sec, 2)
        self.end_sec = round(end_sec, 2)
        self.duration = round(end_sec - start_sec, 2)
        self.status = "PENDING"
        self.subtitles = []
        self.audio_files = []
        self.error_msg = ""
        self.retries = 0

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "start_sec": self.start_sec,
            "end_sec": self.end_sec,
            "status": self.status,
            "subtitles_count": len(self.subtitles),
            "error_msg": self.error_msg
        }

class ChunkedPipeline:
    """
    Streaming Incremental Pipeline:
    - Slices source video into 30-60s chunks
    - Transcribes, translates, and synthesizes Khmer voice dialogue incrementally
    - Fires on_chunk_ready as soon as each chunk finishes so users can PLAY immediately!
    - Enables progressive playback buffering and chunk failure retry
    """
    def __init__(self, video_path: str, total_duration: float, chunk_size_sec: float = 45.0):
        self.video_path = video_path
        self.total_duration = max(1.0, total_duration)
        self.chunk_size_sec = max(20.0, chunk_size_sec)
        self.chunks = []
        self.is_running = False
        self._stop_requested = False
        self.max_ready_sec = 0.0

        self._build_chunks()

    def _build_chunks(self):
        self.chunks = []
        t = 0.0
        cid = 0
        while t < self.total_duration:
            next_t = min(self.total_duration, t + self.chunk_size_sec)
            chunk = VideoChunk(chunk_id=cid, start_sec=t, end_sec=next_t)
            self.chunks.append(chunk)
            cid += 1
            t = next_t

    def get_max_playable_sec(self) -> float:
        """Returns contiguous playable timestamp from 0 to first unready chunk"""
        playable = 0.0
        for c in self.chunks:
            if c.status == "READY":
                playable = c.end_sec
            else:
                break
        return playable

    def is_time_ready(self, timestamp_sec: float) -> bool:
        """Checks if a given timestamp falls into a READY chunk"""
        for c in self.chunks:
            if c.start_sec <= timestamp_sec < c.end_sec:
                return c.status == "READY"
        return False

    def start_processing(
        self,
        speech_engine: SpeechRecognitionEngine,
        translation_service: TranslationService,
        dubbing_engine: DubbingEngine,
        source_lang: str,
        target_lang: str,
        voice_dir: str,
        on_chunk_status_change=None,
        on_chunk_ready=None,
        on_complete=None
    ):
        if self.is_running:
            return
        self.is_running = True
        self._stop_requested = False

        def _worker():
            try:
                for chunk in self.chunks:
                    if self._stop_requested:
                        break
                    if chunk.status == "READY":
                        continue

                    self._process_single_chunk(
                        chunk=chunk,
                        speech_engine=speech_engine,
                        translation_service=translation_service,
                        dubbing_engine=dubbing_engine,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        voice_dir=voice_dir,
                        on_chunk_status_change=on_chunk_status_change,
                        on_chunk_ready=on_chunk_ready
                    )

                if on_complete:
                    on_complete(self.chunks)
            finally:
                self.is_running = False

        threading.Thread(target=_worker, daemon=True).start()

    def retry_chunk(
        self,
        chunk_id: int,
        speech_engine: SpeechRecognitionEngine,
        translation_service: TranslationService,
        dubbing_engine: DubbingEngine,
        source_lang: str,
        target_lang: str,
        voice_dir: str,
        on_chunk_status_change=None,
        on_chunk_ready=None
    ):
        if not (0 <= chunk_id < len(self.chunks)):
            return
        chunk = self.chunks[chunk_id]
        chunk.retries += 1
        chunk.status = "PENDING"
        if on_chunk_status_change:
            on_chunk_status_change(chunk)

        def _worker():
            self._process_single_chunk(
                chunk=chunk,
                speech_engine=speech_engine,
                translation_service=translation_service,
                dubbing_engine=dubbing_engine,
                source_lang=source_lang,
                target_lang=target_lang,
                voice_dir=voice_dir,
                on_chunk_status_change=on_chunk_status_change,
                on_chunk_ready=on_chunk_ready
            )

        threading.Thread(target=_worker, daemon=True).start()

    def _process_single_chunk(
        self,
        chunk: VideoChunk,
        speech_engine: SpeechRecognitionEngine,
        translation_service: TranslationService,
        dubbing_engine: DubbingEngine,
        source_lang: str,
        target_lang: str,
        voice_dir: str,
        on_chunk_status_change=None,
        on_chunk_ready=None
    ):
        chunk.status = "PROCESSING"
        chunk.error_msg = ""
        if on_chunk_status_change:
            on_chunk_status_change(chunk)

        # Slice audio slice for this chunk
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_f:
            chunk_wav = tmp_f.name

        try:
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(chunk.start_sec),
                "-t", str(chunk.duration),
                "-i", self.video_path,
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                "-af", "highpass=f=80,lowpass=f=7500,dynaudnorm=f=150:g=15",
                chunk_wav
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

            # Transcribe with Whisper (Supercharged speed with beam_size=1 and word-accurate timestamps)
            model = speech_engine._get_model()
            lang_param = source_lang if source_lang not in ["auto", "Auto Detect"] else None
            segments, _ = model.transcribe(
                chunk_wav,
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
            valid_segs = [s for s in raw_segs if s.text.strip()]

            chunk_subs = []
            if valid_segs:
                orig_texts = [s.text.strip() for s in valid_segs]
                # High-speed batch translation (1 single fast HTTP call instead of N sequential calls)
                try:
                    km_texts = translation_service.translate_batch(orig_texts, source_lang=source_lang, target_lang=target_lang)
                    if len(km_texts) != len(orig_texts):
                        km_texts = [translation_service.translate_text(t, source_lang=source_lang, target_lang=target_lang) for t in orig_texts]
                except Exception:
                    km_texts = [translation_service.translate_text(t, source_lang=source_lang, target_lang=target_lang) for t in orig_texts]

                for seg, orig, km in zip(valid_segs, orig_texts, km_texts):
                    # Frame-accurate second-by-second speech timing alignment
                    if hasattr(seg, "words") and seg.words:
                        seg_s = max(0.0, seg.words[0].start - 0.05)
                        seg_e = seg.words[-1].end + 0.10
                    else:
                        seg_s = seg.start
                        seg_e = seg.end
                    if seg_e <= seg_s:
                        seg_e = seg_s + 0.35

                    abs_start = round(chunk.start_sec + seg_s, 2)
                    abs_end = round(chunk.start_sec + seg_e, 2)
                    sub_entry = {
                        "id": 0,  # Assigned globally upon insertion
                        "chunk_id": chunk.chunk_id,
                        "start": abs_start,
                        "end": abs_end,
                        "original": orig,
                        "translated": km,
                        "rate": "+0%"
                    }
                    chunk_subs.append(sub_entry)

            # Generate individual Khmer TTS voice files for this chunk
            if chunk_subs and voice_dir:
                dubbing_engine.generate_segment_files(
                    chunk_subs,
                    voice_dir=voice_dir,
                    default_rate="+0%",
                    force_refresh=False
                )

            chunk.subtitles = chunk_subs
            chunk.audio_files = [s["audio_file"] for s in chunk_subs if s.get("audio_file")]
            chunk.status = "READY"
            self.max_ready_sec = max(self.max_ready_sec, chunk.end_sec)

            if on_chunk_status_change:
                on_chunk_status_change(chunk)

            if on_chunk_ready:
                on_chunk_ready(chunk)

        except Exception as e:
            chunk.status = "FAILED"
            chunk.error_msg = str(e)
            if on_chunk_status_change:
                on_chunk_status_change(chunk)
        finally:
            if os.path.exists(chunk_wav):
                try:
                    os.remove(chunk_wav)
                except Exception:
                    pass

    def stop(self):
        self._stop_requested = True
