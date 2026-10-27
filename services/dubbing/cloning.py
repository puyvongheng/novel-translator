"""
Voice Cloning & Acoustic Profile Module
Provides profile extraction, timbre analysis, and cloned voice persistence.
"""

import os
import sys
import json
import time
import subprocess

if getattr(sys, 'frozen', False):
    CLONED_VOICES_FILE = os.path.join(os.path.dirname(sys.executable), "cloned_voices.json")
else:
    root_candidate = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "cloned_voices.json")
    services_candidate = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cloned_voices.json")
    if os.path.exists(root_candidate):
        CLONED_VOICES_FILE = root_candidate
    elif os.path.exists(services_candidate):
        CLONED_VOICES_FILE = services_candidate
    else:
        CLONED_VOICES_FILE = root_candidate


def get_cloned_voices() -> dict:
    """Reads saved custom cloned voice profiles from disk."""
    if os.path.exists(CLONED_VOICES_FILE):
        try:
            with open(CLONED_VOICES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_cloned_voice(
    name: str,
    base_voice: str,
    pitch_scale: float,
    formant: str,
    bass_gain: float,
    treble_gain: float,
    ref_path: str = None
) -> bool:
    """Saves or updates a cloned voice configuration profile."""
    voices = get_cloned_voices()
    voices[name] = {
        "name": name,
        "base_voice": base_voice,
        "pitch_scale": round(pitch_scale, 3),
        "formant": formant,
        "bass_gain": round(bass_gain, 1),
        "treble_gain": round(treble_gain, 1),
        "ref_path": ref_path or "",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        with open(CLONED_VOICES_FILE, "w", encoding="utf-8") as f:
            json.dump(voices, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Save cloned voice error: {e}")
        return False


def delete_cloned_voice(name: str) -> bool:
    """Deletes a cloned voice profile by name."""
    voices = get_cloned_voices()
    if name in voices:
        del voices[name]
        try:
            with open(CLONED_VOICES_FILE, "w", encoding="utf-8") as f:
                json.dump(voices, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
    return False


def analyze_voice_sample(sample_path: str) -> dict:
    """Analyzes reference audio sample file for cloning parameters."""
    info = {
        "duration": 0.0,
        "mean_volume_db": -20.0,
        "recommended_base": "km-KH-PisethNeural",
        "recommended_pitch_scale": 1.0,
        "recommended_bass": 0,
        "recommended_treble": 0,
        "status": "OK"
    }
    if not os.path.exists(sample_path):
        info["status"] = "File not found"
        return info

    try:
        d_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", sample_path]
        d_res = subprocess.run(d_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if d_res.stdout.strip():
            info["duration"] = round(float(d_res.stdout.strip()), 2)

        v_cmd = ["ffmpeg", "-i", sample_path, "-af", "volumedetect", "-f", "null", "-"]
        v_res = subprocess.run(v_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for line in v_res.stderr.splitlines():
            if "mean_volume:" in line:
                parts = line.split("mean_volume:")[1].strip().split(" ")
                info["mean_volume_db"] = round(float(parts[0]), 1)

        if info["mean_volume_db"] > -22.0:
            info["recommended_bass"] = 4
            info["recommended_pitch_scale"] = 0.95
        else:
            info["recommended_bass"] = 2
            info["recommended_pitch_scale"] = 1.05
    except Exception as ex:
        info["status"] = f"Analysis error: {ex}"

    return info


def extract_reference_acoustic_profile(sample_path: str) -> dict:
    """
    Extracts real acoustic characteristics from uploaded sample using librosa/numpy:
    - Median F0 pitch
    - Spectral tilt & formant resonance distribution
    - Bass/Mid/Treble energy ratios
    """
    profile = {
        "pitch_scale": 1.0,
        "bass_db": 0.0,
        "mid_db": 0.0,
        "treble_db": 0.0,
        "formant": "shifted"
    }
    if not sample_path or not os.path.exists(sample_path):
        return profile

    try:
        import numpy as np
        import librosa

        y, sr = librosa.load(sample_path, sr=22050, duration=12)
        if len(y) > 0:
            # 1. Pitch extraction (F0)
            f0, _, _ = librosa.pyin(y, fmin=65, fmax=450, sr=sr)
            valid_f0 = f0[~np.isnan(f0)]
            if len(valid_f0) > 0:
                med_f0 = float(np.median(valid_f0))
                # Standard baseline for PisethNeural is ~135Hz
                base_f0 = 135.0
                ratio = float(np.clip(med_f0 / base_f0, 0.70, 1.45))
                profile["pitch_scale"] = round(ratio, 3)

            # 2. Spectral energy bands for timbre matching
            spec = np.abs(librosa.stft(y))
            freqs = librosa.fft_frequencies(sr=sr)

            low_mask = (freqs >= 60) & (freqs < 300)
            mid_mask = (freqs >= 300) & (freqs < 3200)
            high_mask = (freqs >= 3200) & (freqs < 8000)

            low_eng = float(np.mean(spec[low_mask])) if np.any(low_mask) else 1e-4
            mid_eng = float(np.mean(spec[mid_mask])) if np.any(mid_mask) else 1e-4
            high_eng = float(np.mean(spec[high_mask])) if np.any(high_mask) else 1e-4

            total = low_eng + mid_eng + high_eng + 1e-6
            profile["bass_db"] = round(float(np.clip((low_eng / total - 0.28) * 22.0, -5.0, 9.0)), 1)
            profile["mid_db"] = round(float(np.clip((mid_eng / total - 0.42) * 16.0, -4.0, 6.0)), 1)
            profile["treble_db"] = round(float(np.clip((high_eng / total - 0.30) * 22.0, -5.0, 8.0)), 1)
    except Exception as e:
        print(f"Acoustic profile extraction error: {e}")

    return profile
