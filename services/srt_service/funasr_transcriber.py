"""
FunASR / SenseVoice-Small & CAM++ Transcriber Service
Specialized for ultra-fast multi-lingual dialogue recognition, Speech Emotion Recognition (SER),
Audio Event Detection (AED), and CAM++ Speaker Diarization.
"""

import os
import re
from typing import Optional, List, Dict, Any
import numpy as np
import soundfile as sf
from services.srt_service.audio_extractor import AudioExtractor
from services.srt_service.speaker_verification import SpeakerVerificationService, SpeakerClusterManager


# Emotion mapping (SenseVoice SER tags -> English & Khmer)
EMOTION_MAP = {
    "<|HAPPY|>": ("happy", "😊 សប្បាយ (Happy)"),
    "<|SAD|>": ("sad", "😢 កើតទុក្ខ (Sad)"),
    "<|ANGRY|>": ("angry", "😡 ខឹង (Angry)"),
    "<|NEUTRAL|>": ("neutral", "😐 ធម្មតា (Neutral)"),
    "<|FEARFUL|>": ("fearful", "😨 ភ័យខ្លាច (Fearful)"),
    "<|DISGUSTED|>": ("disgusted", "🤢 ខ្ពើម (Disgusted)"),
    "<|SURPRISED|>": ("surprised", "😮 ភ្ញាក់ផ្អើល (Surprised)"),
}

# Audio Event mapping (SenseVoice AED tags -> English & Khmer)
EVENT_MAP = {
    "<|BGM|>": ("bgm", "🎵 [ភ្លេង / BGM]"),
    "<|APPLAUSE|>": ("applause", "👏 [ទះដៃ / Applause]"),
    "<|LAUGHTER|>": ("laughter", "😆 [សើច / Laughter]"),
    "<|CRY|>": ("cry", "😭 [យំ / Crying]"),
    "<|SNEEZE|>": ("sneeze", "🤧 [កណ្តាស់]"),
    "<|BREATH|>": ("breath", "💨 [ដង្ហើមធំ]"),
    "<|COUGH|>": ("cough", "😷 [ក្អក]"),
}


def parse_sensevoice_tags(raw_text: str) -> tuple[str, str, str, str]:
    """
    Parses SenseVoice raw text:
    Extracts (clean_text, rich_text, emotion, event)
    """
    found_emotion = ""
    found_emotion_kh = ""
    for tag, (emo_en, emo_kh) in EMOTION_MAP.items():
        if tag in raw_text:
            found_emotion = emo_en
            found_emotion_kh = emo_kh
            break

    found_event = ""
    found_event_kh = ""
    for tag, (evt_en, evt_kh) in EVENT_MAP.items():
        if tag in raw_text:
            found_event = evt_en
            found_event_kh = evt_kh
            break

    # Strip all special tokens like <|zh|>, <|NEUTRAL|>, <|Speech|>, <|woitn|>, etc.
    clean_text = re.sub(r"<\|[A-Za-z0-9_]+\|>", "", raw_text).strip()

    # Build rich text (annotated with event and emotion for preview/subtitles)
    rich_prefix = []
    if found_event_kh:
        rich_prefix.append(found_event_kh)
    if found_emotion_kh and found_emotion != "neutral":
        rich_prefix.append(found_emotion_kh.split()[0]) # e.g. "😊"

    if rich_prefix and clean_text:
        rich_text = f"{' '.join(rich_prefix)} {clean_text}"
    else:
        rich_text = clean_text

    return clean_text, rich_text, found_emotion, found_event


class FunASRTranscriber:
    """
    Transcribes dialogues using Alibaba SenseVoice-Small & CAM++ Diarization:
    1. Ultra-fast multi-lingual ASR (Chinese, English, Cantonese, Japanese, Korean)
    2. Speech Emotion Recognition (SER: Laugh, Cry, Angry, Happy, Sad, Fear, Surprise)
    3. Audio Event Detection (AED: BGM music, Applause, Laughter, Cough)
    4. CAM++ Speaker Diarization & Acoustic Gender Classification (តួប្រុស, តួស្រី)
    5. Automatic character voice matching (Piseth / Sreymom)
    """

    @staticmethod
    def transcribe(
        media_path: str,
        progress_callback=None,
        enable_diarization: bool = True,
        model_name: str = "SenseVoiceSmall"
    ) -> List[Dict[str, Any]]:
        """
        Transcribes audio with SenseVoice-Small + CAM++ Speaker Diarization + Gender + Emotion & Event detection.
        """
        temp_wav = None
        if not media_path.lower().endswith(".wav"):
            if progress_callback:
                progress_callback("Extracting normalized audio for SenseVoice & CAM++...", 0.05)
            temp_wav = AudioExtractor.extract_asr_wav(media_path)
            input_audio = temp_wav
        else:
            input_audio = media_path

        try:
            from funasr import AutoModel
            import torch

            device_str = "cuda" if torch.cuda.is_available() else "cpu"

            # 1. Try loading SenseVoice-Small with FSMN-VAD & CAM++ Diarization
            subtitles = []
            is_sensevoice = False

            if model_name in ("SenseVoiceSmall", "auto", "sensevoice"):
                try:
                    if progress_callback:
                        progress_callback("Loading SenseVoice-Small & FSMN-VAD...", 0.12)

                    vad_model = AutoModel(
                        model="fsmn-vad",
                        vad_kwargs={"max_single_segment_time": 30000},
                        device=device_str,
                        disable_update=True
                    )
                    sv_model = AutoModel(
                        model="iic/SenseVoiceSmall",
                        device=device_str,
                        disable_update=True
                    )
                    is_sensevoice = True

                    if progress_callback:
                        progress_callback("Detecting speech dialogue segments with FSMN-VAD...", 0.20)

                    vad_res = vad_model.generate(input=input_audio)
                    segments = vad_res[0]["value"] if (vad_res and isinstance(vad_res, list) and "value" in vad_res[0]) else []

                    cam_model = None
                    if enable_diarization:
                        try:
                            if progress_callback:
                                progress_callback("Loading CAM++ Speaker Diarization & Gender Model...", 0.25)
                            cam_model = SpeakerVerificationService.get_model(device=device_str)
                        except Exception:
                            cam_model = None

                    cluster_mgr = SpeakerClusterManager(threshold=0.58)

                    if progress_callback:
                        progress_callback(f"Transcribing {len(segments)} dialogue lines & detecting characters...", 0.30)

                    with sf.SoundFile(input_audio) as sfile:
                        file_sr = sfile.samplerate
                        total_frames = len(sfile)

                        for i, (s_ms, e_ms) in enumerate(segments):
                            start_frame = max(0, min(total_frames, int((s_ms / 1000.0) * file_sr)))
                            end_frame = max(0, min(total_frames, int((e_ms / 1000.0) * file_sr)))
                            num_frames = end_frame - start_frame
                            if num_frames < int(file_sr * 0.15):
                                continue

                            sfile.seek(start_frame)
                            chunk = sfile.read(num_frames, dtype="float32")
                            if len(chunk.shape) > 1:
                                chunk = np.mean(chunk, axis=1)

                            if file_sr != 16000 and len(chunk) > 0:
                                import librosa
                                chunk = librosa.resample(chunk, orig_sr=file_sr, target_sr=16000)
                                sr = 16000
                            else:
                                sr = file_sr

                            res = sv_model.generate(input=chunk, language="auto", use_itn=True, disable_pbar=True)
                            raw_txt = (res[0]["text"] if res else "").strip()
                            if not raw_txt:
                                continue

                            clean_txt, rich_txt, emotion, event = parse_sensevoice_tags(raw_txt)
                            if not clean_txt and not rich_txt:
                                continue

                            st = round(float(s_ms) / 1000.0, 3)
                            en = round(float(e_ms) / 1000.0, 3)
                            if en <= st:
                                en = round(st + 0.4, 3)

                            # Speaker Diarization with CAM++ & Gender Classification
                            emb = None
                            if cam_model is not None and len(chunk) >= int(sr * 0.35):
                                try:
                                    spk_res = cam_model.generate(input=chunk, disable_pbar=True)
                                    if spk_res and isinstance(spk_res, list) and "spk_embedding" in spk_res[0]:
                                        raw_emb = np.array(spk_res[0]["spk_embedding"], dtype=np.float32).flatten()
                                        if np.linalg.norm(raw_emb) > 1e-6:
                                            emb = raw_emb
                                except Exception:
                                    emb = None

                            spk_info = cluster_mgr.process_segment(chunk, sr=sr, embedding=emb)
                            spk_label = spk_info["speaker"]
                            spk_gender = spk_info["gender"]
                            spk_voice = spk_info["voice"]
                            spk_pitch = spk_info.get("pitch", 130.0)

                            subtitles.append({
                                "id": len(subtitles) + 1,
                                "start": st,
                                "end": en,
                                "orig_text": clean_txt or rich_txt,
                                "original": clean_txt or rich_txt,
                                "text": clean_txt or rich_txt,
                                "rich_text": rich_txt or clean_txt,
                                "khmer_text": "",
                                "translated": "",
                                "speaker": spk_label,
                                "actor": spk_label,
                                "speaker_id": spk_info["speaker_id"],
                                "gender": spk_gender,
                                "voice": spk_voice,
                                "pitch": spk_pitch,
                                "emotion": emotion,
                                "event": event,
                                "rate": "+0%",
                                "status": "raw"
                            })

                            if progress_callback and (i % 2 == 0 or i == len(segments) - 1):
                                pct = 0.30 + 0.68 * ((i + 1) / max(1, len(segments)))
                                progress_callback(
                                    f"SenseVoice [{i+1}/{len(segments)}] {spk_label}: {clean_txt[:25]}",
                                    pct
                                )

                except Exception as ex_sv:
                    if progress_callback:
                        progress_callback(f"SenseVoice note ({ex_sv}). Fallback to Paraformer...", 0.20)

            # 2. Fallback to Paraformer-zh + VAD if SenseVoice was not available
            if not subtitles and not is_sensevoice:
                if progress_callback:
                    progress_callback("Loading Alibaba Paraformer + VAD...", 0.25)

                para_kwargs = {
                    "model": "paraformer-zh",
                    "vad_model": "fsmn-vad",
                    "punc_model": "ct-punc",
                    "device": device_str,
                    "disable_update": True
                }

                model = AutoModel(**para_kwargs)
                res = model.generate(input=input_audio, batch_size_s=60, sentence_timestamp=True)
                if res and isinstance(res, list) and len(res) > 0:
                    sentence_list = res[0].get("sentence_info") or []
                    for s in sentence_list:
                        raw_txt = (s.get("text") or s.get("sentence") or "").strip()
                        if not raw_txt:
                            continue
                        clean_txt, rich_txt, emotion, event = parse_sensevoice_tags(raw_txt)
                        st = float(s.get("start", 0)) / 1000.0
                        en = float(s.get("end", 0)) / 1000.0
                        if en <= st:
                            en = st + 0.4
                        subtitles.append({
                            "id": len(subtitles) + 1,
                            "start": round(st, 3),
                            "end": round(en, 3),
                            "orig_text": clean_txt or rich_txt,
                            "original": clean_txt or rich_txt,
                            "text": clean_txt or rich_txt,
                            "rich_text": rich_txt or clean_txt,
                            "khmer_text": "",
                            "translated": "",
                            "speaker": "Speaker 1",
                            "speaker_id": "Speaker 1",
                            "emotion": emotion,
                            "event": event,
                            "rate": "+0%",
                            "status": "raw"
                        })


                # Fallback: parse full text if sentence_info was not populated
                if not subtitles and item.get("text"):
                    full_text = item.get("text", "").strip()
                    clean_txt, rich_txt, emotion, event = parse_sensevoice_tags(full_text)
                    timestamps = item.get("timestamp", [])
                    delimiters = set("。！？；…\n")
                    minor_delims = set("，, ")

                    if timestamps and len(timestamps) > 0:
                        cur_chars = []
                        cur_start = None
                        cur_end = None
                        ts_idx = 0

                        for ch in clean_txt:
                            cur_chars.append(ch)
                            if ts_idx < len(timestamps) and ch not in delimiters and ch not in minor_delims:
                                t_pair = timestamps[ts_idx]
                                if cur_start is None:
                                    cur_start = t_pair[0]
                                cur_end = t_pair[1]
                                ts_idx += 1

                            is_major = ch in delimiters
                            is_long = (ch in minor_delims and len(cur_chars) >= 12)
                            if (is_major or is_long) and cur_start is not None and cur_end is not None:
                                sent_str = "".join(cur_chars).strip()
                                if sent_str:
                                    st = float(cur_start) / 1000.0
                                    en = float(cur_end) / 1000.0
                                    if en <= st:
                                        en = st + 0.4
                                    subtitles.append({
                                        "id": len(subtitles) + 1,
                                        "start": round(st, 3),
                                        "end": round(en, 3),
                                        "orig_text": sent_str,
                                        "original": sent_str,
                                        "text": sent_str,
                                        "rich_text": sent_str,
                                        "khmer_text": "",
                                        "translated": "",
                                        "speaker": "",
                                        "speaker_id": "",
                                        "emotion": emotion,
                                        "event": event,
                                        "rate": "+0%",
                                        "status": "raw"
                                    })
                                cur_chars = []
                                cur_start = None
                                cur_end = None

                        if cur_chars and cur_start is not None and cur_end is not None:
                            sent_str = "".join(cur_chars).strip()
                            if sent_str:
                                st = float(cur_start) / 1000.0
                                en = float(cur_end) / 1000.0
                                if en <= st:
                                    en = st + 0.4
                                subtitles.append({
                                    "id": len(subtitles) + 1,
                                    "start": round(st, 3),
                                    "end": round(en, 3),
                                    "orig_text": sent_str,
                                    "original": sent_str,
                                    "text": sent_str,
                                    "rich_text": sent_str,
                                    "khmer_text": "",
                                    "translated": "",
                                    "speaker": "",
                                    "speaker_id": "",
                                    "emotion": emotion,
                                    "event": event,
                                    "rate": "+0%",
                                    "status": "raw"
                                })

            if progress_callback:
                spk_count = len(set(s.get("speaker_id") for s in subtitles if s.get("speaker_id")))
                spk_str = f" | {spk_count} Speakers detected by CAM++" if spk_count > 0 else ""
                progress_callback(f"FunASR & CAM++ completed! Detected {len(subtitles)} dialogue lines{spk_str}.", 1.0)

            return subtitles

        finally:
            if temp_wav and os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except Exception:
                    pass
