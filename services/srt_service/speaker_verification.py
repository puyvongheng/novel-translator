"""
Speaker Verification & Comparison Service using CAM++
Alibaba DAMO / FunASR CAM++ Conformer Architecture (16kHz 192-dim embeddings).

Features:
1. Compare two audio clips to determine if they belong to the same person or different people.
2. Extract speaker voice embedding fingerprint (192-dim vector) for character profiling.
3. Match unknown audio against known speaker profiles with cosine similarity.
"""

import os
import tempfile
from typing import Optional, Dict, Any, Tuple
import numpy as np
from services.srt_service.audio_extractor import AudioExtractor


class SpeakerVerificationService:
    """
    CAM++ Speaker Verification & Comparison Service.
    Determines whether two audio clips are spoken by the same speaker.
    """

    _model = None

    @classmethod
    def get_model(cls, device: Optional[str] = None):
        """Lazy loads CAM++ model singleton."""
        if cls._model is None:
            import torch
            from funasr import AutoModel

            if device is None:
                device = "cuda" if torch.cuda.is_available() else "cpu"

            cls._model = AutoModel(
                model="cam++",
                device=device,
                disable_update=True
            )
        return cls._model

    @classmethod
    def extract_embedding(cls, audio_path: str, device: Optional[str] = None) -> np.ndarray:
        """
        Extracts 192-dimensional speaker embedding vector from audio.
        Automatically normalizes input to 16kHz mono WAV if necessary.
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        temp_wav = None
        input_audio = audio_path
        if not audio_path.lower().endswith(".wav"):
            temp_wav = AudioExtractor.extract_asr_wav(audio_path)
            input_audio = temp_wav

        try:
            model = cls.get_model(device=device)
            res = model.generate(input=input_audio)
            if not res or not isinstance(res, list) or len(res) == 0:
                raise RuntimeError(f"CAM++ failed to extract embedding from {audio_path}")

            emb = res[0].get("spk_embedding")
            if emb is None:
                raise RuntimeError("No 'spk_embedding' returned by CAM++ model")

            return np.array(emb, dtype=np.float32).flatten()
        finally:
            if temp_wav and os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except Exception:
                    pass

    @classmethod
    def compute_similarity(cls, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """
        Calculates cosine similarity between two speaker embeddings.
        Returns float between -1.0 and 1.0 (typically 0.0 to 1.0).
        """
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)
        if norm1 < 1e-8 or norm2 < 1e-8:
            return 0.0
        return float(np.dot(emb1, emb2) / (norm1 * norm2))

    @classmethod
    def compare_speakers(
        cls,
        audio_path1: str,
        audio_path2: str,
        threshold: float = 0.60,
        device: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Compares two audio recordings using CAM++:
        - Determines if both audio clips belong to the SAME person or DIFFERENT people.
        - Default threshold is 0.60 (tuned for CAM++ cosine similarity).

        Returns:
            dict containing:
                - is_same_speaker: bool (True = មនុស្សតែមួយ, False = មនុស្សខុសគ្នា)
                - similarity: float (e.g. 0.72)
                - similarity_pct: str (e.g. "72.4%")
                - verdict_kh: str ("មនុស្សតែមួយ (Match)" or "មនុស្សខុសគ្នា (Different)")
                - confidence_kh: str ("ខ្ពស់ខ្លាំង", "ខ្ពស់", "មធ្យម", "ខុសគ្នាដាច់")
                - threshold: float
        """
        emb1 = cls.extract_embedding(audio_path1, device=device)
        emb2 = cls.extract_embedding(audio_path2, device=device)

        sim = cls.compute_similarity(emb1, emb2)
        is_same = bool(sim >= threshold)

        # Categorize confidence
        if sim >= 0.75:
            conf_kh = "ខ្ពស់ខ្លាំង (Very High Confidence)"
        elif sim >= 0.60:
            conf_kh = "ខ្ពស់ (High Confidence)"
        elif sim >= 0.45:
            conf_kh = "មធ្យម (Moderate / Uncertain)"
        else:
            conf_kh = "ខុសគ្នាដាច់ (Distinct Voice)"

        verdict_kh = "មនុស្សតែមួយ (Same Person)" if is_same else "មនុស្សខុសគ្នា (Different Persons)"

        return {
            "is_same_speaker": is_same,
            "similarity": round(sim, 4),
            "similarity_pct": f"{max(0.0, sim * 100):.1f}%",
            "verdict": verdict_kh,
            "confidence": conf_kh,
            "threshold": threshold,
            "audio1": audio_path1,
            "audio2": audio_path2
        }

    @classmethod
    def identify_speaker(
        cls,
        audio_path: str,
        reference_profiles: Dict[str, np.ndarray],
        threshold: float = 0.60,
        device: Optional[str] = None
    ) -> Tuple[str, float]:
        """
        Matches an unknown audio against a library of enrolled speaker embeddings.
        Returns (best_match_name, similarity_score).
        If no profile exceeds the threshold, returns ("Unknown", best_score).
        """
        if not reference_profiles:
            return "Unknown", 0.0

        query_emb = cls.extract_embedding(audio_path, device=device)
        best_name = "Unknown"
        best_score = -1.0

        for name, ref_emb in reference_profiles.items():
            score = cls.compute_similarity(query_emb, ref_emb)
            if score > best_score:
                best_score = score
                if score >= threshold:
                    best_name = name

        return best_name, round(best_score, 4)

    @classmethod
    def detect_gender(cls, audio_chunk: np.ndarray, sr: int = 16000) -> Tuple[str, float, str]:
        """
        Ultra-fast (<2ms) acoustic pitch (F0) & character gender detector using FFT autocorrelation.
        - Adult Male voices: F0 < 165 Hz (typically 90 - 150 Hz)
        - Adult Female / Youth voices: F0 >= 165 Hz (typically 180 - 280 Hz)
        Returns: (gender: "Male"|"Female", pitch_hz: float, label_kh: "តួប្រុស (Male)"|"តួស្រី (Female)")
        """
        from scipy.signal import correlate

        if audio_chunk is None or len(audio_chunk) < int(sr * 0.15):
            return "Male", 130.0, "តួប្រុស (Male)"

        try:
            # Flatten & ensure 1D float32
            sig = audio_chunk.flatten().astype(np.float32)
            # Take middle segment (up to 0.6s) to avoid silence at word edges
            mid = len(sig) // 2
            half_w = min(len(sig) // 2, int(sr * 0.30))
            seg = sig[mid - half_w : mid + half_w]
            seg = seg - np.mean(seg)

            # Energy check: if near silent, default to Male
            energy = np.mean(seg ** 2)
            if energy < 1e-5:
                return "Male", 130.0, "តួប្រុស (Male)"

            # Autocorrelation via FFT
            corr = correlate(seg, seg, mode="full")
            corr = corr[len(corr) // 2 :] # positive lags

            # Human vocal pitch range: 70 Hz to 350 Hz
            min_lag = int(sr / 350) # ~45
            max_lag = int(sr / 70)  # ~228

            if len(corr) < max_lag:
                return "Male", 130.0, "តួប្រុស (Male)"

            peak_lag = min_lag + int(np.argmax(corr[min_lag:max_lag]))
            f0 = float(sr) / float(peak_lag)

            if f0 < 165.0:
                return "Male", round(f0, 1), "តួប្រុស (Male)"
            else:
                return "Female", round(f0, 1), "តួស្រី (Female)"
        except Exception:
            return "Male", 130.0, "តួប្រុស (Male)"


class SpeakerClusterManager:
    """
    Manages online speaker clustering with CAM++ embeddings and acoustic pitch-based gender classification.
    Automatically assigns:
    - Gender: "Male" or "Female"
    - Character Name: "តួប្រុស 1 (Male 1)", "តួស្រី 1 (Female 1)", etc.
    - Default TTS Voice: "km-KH-PisethNeural" (Male) or "km-KH-SreymomNeural" (Female)
    """

    def __init__(self, threshold: float = 0.58):
        self.threshold = threshold
        self.clusters: list[dict] = []
        self.male_count = 0
        self.female_count = 0

    def process_segment(
        self,
        audio_chunk: np.ndarray,
        sr: int = 16000,
        embedding: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """
        Processes a single dialogue segment:
        1. Classifies Gender & Pitch
        2. Matches against existing Speaker Clusters using CAM++ cosine similarity
        3. Returns speaker details with assigned Khmer voice profile
        """
        gender, f0, g_khmer = SpeakerVerificationService.detect_gender(audio_chunk, sr=sr)

        # Match against known clusters if embedding is provided
        if embedding is not None:
            norm = np.linalg.norm(embedding)
            if norm > 1e-6:
                emb = embedding / norm
                best_match = None
                best_sim = -1.0

                for c in self.clusters:
                    # Same gender constraint helps avoid misclustering male/female with similar timbre
                    centroid = np.mean(c["embeddings"], axis=0)
                    centroid_norm = np.linalg.norm(centroid)
                    if centroid_norm > 1e-6:
                        centroid = centroid / centroid_norm
                        sim = float(np.dot(emb, centroid))
                        # Give slight bonus if detected gender matches cluster gender
                        if c["gender"] == gender:
                            sim += 0.05
                        if sim > best_sim:
                            best_sim = sim
                            best_match = c

                if best_match and best_sim >= self.threshold:
                    best_match["embeddings"].append(emb)
                    best_match["pitches"].append(f0)
                    return {
                        "speaker_id": best_match["id"],
                        "speaker": best_match["label"],
                        "gender": best_match["gender"],
                        "voice": best_match["voice"],
                        "pitch": round(f0, 1),
                        "similarity": round(best_sim, 3)
                    }

        # Create new cluster for this character
        if gender == "Male":
            self.male_count += 1
            spk_label = f"តួប្រុស {self.male_count} (Male {self.male_count})"
            voice = "km-KH-PisethNeural"
        else:
            self.female_count += 1
            spk_label = f"តួស្រី {self.female_count} (Female {self.female_count})"
            voice = "km-KH-SreymomNeural"

        cluster_id = f"spk_{len(self.clusters) + 1}"
        new_c = {
            "id": cluster_id,
            "gender": gender,
            "label": spk_label,
            "voice": voice,
            "embeddings": [embedding / np.linalg.norm(embedding)] if (embedding is not None and np.linalg.norm(embedding) > 1e-6) else [],
            "pitches": [f0]
        }
        self.clusters.append(new_c)

        return {
            "speaker_id": cluster_id,
            "speaker": spk_label,
            "gender": gender,
            "voice": voice,
            "pitch": round(f0, 1),
            "similarity": 1.0
        }
