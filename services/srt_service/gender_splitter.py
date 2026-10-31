"""
Gender-Based SRT Splitter Service
Classifies each subtitle segment as Male or Female, then generates separate SRT files.

Three modes:
  A) split_by_tags()   — Parse existing [Male]/[Female] tags in SRT text (no audio needed)
  B) split_by_gender() — Audio-based classification using one of two engines:
     1. "builtin" — F0 pitch autocorrelation (zero install, uses scipy — already in project)
     2. "ina"     — inaSpeechSegmenter CNN (more accurate, requires: pip install inaSpeechSegmenter)

Output: _male.srt, _female.srt, _tagged.srt (or _clean.srt for tag mode)
"""

import os
import re
import sys
import tempfile
import argparse
from typing import List, Dict, Optional, Callable, Literal

# Project imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from utils.srt_utils import parse_srt_file, parse_raw_srt_blocks
from utils.time_utils import format_timestamp


class GenderSrtSplitter:
    """
    Splits an SRT file into Male/Female tracks using audio-based gender classification.

    Engines:
        "builtin" — Uses F0 pitch detection (SpeakerVerificationService.detect_gender).
                    No extra install needed. Fast (~2ms per segment).
        "ina"     — Uses inaSpeechSegmenter CNN. More accurate for noisy/mixed audio.
                    Requires: pip install inaSpeechSegmenter pydub
    """

    SUPPORTED_ENGINES = ("builtin", "ina")

    def __init__(self, engine: Literal["builtin", "ina"] = "builtin"):
        if engine not in self.SUPPORTED_ENGINES:
            raise ValueError(f"Unsupported engine '{engine}'. Use: {self.SUPPORTED_ENGINES}")
        self.engine = engine
        self._ina_segmenter = None

    @staticmethod
    def is_ina_available() -> bool:
        """Checks if inaSpeechSegmenter is installed."""
        try:
            from inaSpeechSegmenter import Segmenter
            return True
        except ImportError:
            return False

    @staticmethod
    def is_builtin_available() -> bool:
        """Checks if scipy (required for builtin F0 gender) is available."""
        try:
            from scipy.signal import correlate
            import numpy as np
            return True
        except ImportError:
            return False

    def _get_ina_segmenter(self):
        """Lazy-loads the inaSpeechSegmenter CNN model (cached after first call)."""
        if self._ina_segmenter is None:
            from inaSpeechSegmenter import Segmenter
            self._ina_segmenter = Segmenter()
        return self._ina_segmenter

    # ──────────────────────────────────────────────────────────
    # TAG PATTERN for detecting [Male]/[Female] in SRT text
    # Matches: [Male], [male], [MALE], [Female], [female], [FEMALE]
    # ──────────────────────────────────────────────────────────
    _TAG_PATTERN = re.compile(
        r'^\s*\[(male|female|Male|Female|MALE|FEMALE)\]\s*',
        re.IGNORECASE
    )

    def split_by_tags(
        self,
        srt_path: str,
        output_dir: Optional[str] = None,
        strip_tags: bool = True,
        progress_callback: Optional[Callable] = None
    ) -> Dict:
        """
        Splits an SRT file by existing [Male]/[Female] text tags — NO audio needed.

        Handles common SRT formatting issues:
          - Missing blank lines between blocks (e.g. block 2 and 3 touching)
          - Case-insensitive tags: [Male], [male], [MALE], [Female], etc.

        Args:
            srt_path:           Path to the tagged SRT file
            output_dir:         Output directory (defaults to SRT file's directory)
            strip_tags:         If True, remove [Male]/[Female] tags from output text
            progress_callback:  Optional callback(message: str, progress: float)

        Returns:
            Dict with keys:
                male_srt_path, female_srt_path, clean_srt_path,
                male_count, female_count, unknown_count, total_count,
                gender_map (list of dicts)
        """
        if not os.path.exists(srt_path):
            raise FileNotFoundError(f"SRT file not found: {srt_path}")

        if progress_callback:
            progress_callback("📄 Parsing tagged SRT file...", 0.10)

        subtitles = self._parse_srt_robust(srt_path)
        if not subtitles:
            raise ValueError("No subtitle cues found in the SRT file.")

        total = len(subtitles)
        if progress_callback:
            progress_callback(f"📄 Parsed {total} subtitle lines.", 0.30)

        # Prepare output
        if not output_dir:
            output_dir = os.path.dirname(os.path.abspath(srt_path))
        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(srt_path))[0]

        male_subs = []
        female_subs = []
        clean_subs = []
        detailed_map = []

        for sub in subtitles:
            text = sub.get("text", "")
            tag_match = self._TAG_PATTERN.match(text)

            if tag_match:
                gender = tag_match.group(1).lower()
                clean_text = text[tag_match.end():].strip() if strip_tags else text
            else:
                gender = "unknown"
                clean_text = text

            entry = {
                "start": sub["start"],
                "end": sub["end"],
                "text": clean_text,
                "gender": gender
            }

            if gender == "male":
                male_subs.append(entry)
            elif gender == "female":
                female_subs.append(entry)

            clean_subs.append(entry)

            detailed_map.append({
                "id": sub.get("id", 0),
                "start": sub["start"],
                "end": sub["end"],
                "original_text": text,
                "clean_text": clean_text,
                "gender": gender
            })

        if progress_callback:
            progress_callback("📝 Generating split SRT files...", 0.70)

        # Write output files
        male_path = os.path.join(output_dir, f"{base_name}_male.srt")
        female_path = os.path.join(output_dir, f"{base_name}_female.srt")
        clean_path = os.path.join(output_dir, f"{base_name}_clean.srt")

        self._write_srt(male_subs, male_path)
        self._write_srt(female_subs, female_path)
        self._write_srt(clean_subs, clean_path)

        if progress_callback:
            progress_callback(
                f"✅ Done! Male: {len(male_subs)}, Female: {len(female_subs)}, "
                f"Unknown: {total - len(male_subs) - len(female_subs)}",
                1.0
            )

        return {
            "male_srt_path": male_path,
            "female_srt_path": female_path,
            "clean_srt_path": clean_path,
            "male_count": len(male_subs),
            "female_count": len(female_subs),
            "unknown_count": total - len(male_subs) - len(female_subs),
            "total_count": total,
            "engine": "tags",
            "gender_map": detailed_map
        }

    def split_by_gender(
        self,
        srt_path: str,
        audio_path: str,
        output_dir: Optional[str] = None,
        progress_callback: Optional[Callable] = None
    ) -> Dict:
        """
        Main entry point: analyze audio gender per SRT segment and generate split SRT files.

        Args:
            srt_path:           Path to the input .srt file (English)
            audio_path:         Path to the input audio file (.mp3, .wav, etc.)
            output_dir:         Output directory (defaults to SRT file's directory)
            progress_callback:  Optional callback(message: str, progress: float 0.0-1.0)

        Returns:
            Dict with keys:
                male_srt_path, female_srt_path, tagged_srt_path,
                male_count, female_count, unknown_count, total_count,
                gender_map (list of dicts with id, start, end, text, gender, pitch)
        """
        if not os.path.exists(srt_path):
            raise FileNotFoundError(f"SRT file not found: {srt_path}")
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Validate engine availability
        if self.engine == "ina" and not self.is_ina_available():
            raise ImportError(
                "inaSpeechSegmenter is not installed. "
                "Please run: pip install inaSpeechSegmenter pydub\n"
                "Or use engine='builtin' for F0 pitch detection (no extra install)."
            )
        if self.engine == "builtin" and not self.is_builtin_available():
            raise ImportError("scipy and numpy are required for builtin engine.")

        # --- Stage 1: Parse SRT ---
        if progress_callback:
            progress_callback("📄 Stage 1/4: Parsing SRT file...", 0.05)

        subtitles = self._parse_srt(srt_path)
        if not subtitles:
            raise ValueError("No subtitle cues found in the SRT file.")

        total = len(subtitles)
        if progress_callback:
            progress_callback(f"📄 Parsed {total} subtitle lines.", 0.10)

        # --- Stage 2: Load audio ---
        if progress_callback:
            progress_callback(f"🎵 Stage 2/4: Loading audio ({self.engine} engine)...", 0.15)

        # Dispatch to appropriate engine
        if self.engine == "builtin":
            gender_results = self._classify_all_builtin(audio_path, subtitles, total, progress_callback)
        else:
            gender_results = self._classify_all_ina(audio_path, subtitles, total, progress_callback)

        # --- Stage 4: Generate output SRT files ---
        if progress_callback:
            progress_callback("📝 Stage 4/4: Generating output SRT files...", 0.85)

        # Prepare output directory
        if not output_dir:
            output_dir = os.path.dirname(os.path.abspath(srt_path))
        os.makedirs(output_dir, exist_ok=True)

        base_name = os.path.splitext(os.path.basename(srt_path))[0]

        # Build categorized lists
        male_subs = []
        female_subs = []
        tagged_subs = []
        detailed_map = []

        for sub, result in zip(subtitles, gender_results):
            gender = result["gender"]
            pitch = result.get("pitch", 0.0)
            text = sub.get("text", "")
            entry = {
                "start": sub["start"],
                "end": sub["end"],
                "text": text,
                "gender": gender
            }

            if gender == "male":
                male_subs.append(entry)
            elif gender == "female":
                female_subs.append(entry)

            # Tagged version includes all lines
            tag = gender.upper() if gender in ("male", "female") else "UNKNOWN"
            tagged_entry = dict(entry)
            tagged_entry["text"] = f"[{tag}] {text}"
            tagged_subs.append(tagged_entry)

            detailed_map.append({
                "id": sub.get("id", 0),
                "start": sub["start"],
                "end": sub["end"],
                "text": text,
                "gender": gender,
                "pitch": pitch
            })

        # Write SRT files
        male_path = os.path.join(output_dir, f"{base_name}_male.srt")
        female_path = os.path.join(output_dir, f"{base_name}_female.srt")
        tagged_path = os.path.join(output_dir, f"{base_name}_tagged.srt")

        self._write_srt(male_subs, male_path)
        self._write_srt(female_subs, female_path)
        self._write_srt(tagged_subs, tagged_path)

        if progress_callback:
            progress_callback(
                f"✅ Done! Male: {len(male_subs)}, Female: {len(female_subs)}, "
                f"Unknown: {total - len(male_subs) - len(female_subs)}",
                1.0
            )

        return {
            "male_srt_path": male_path,
            "female_srt_path": female_path,
            "tagged_srt_path": tagged_path,
            "male_count": len(male_subs),
            "female_count": len(female_subs),
            "unknown_count": total - len(male_subs) - len(female_subs),
            "total_count": total,
            "engine": self.engine,
            "gender_map": detailed_map
        }

    # ──────────────────────────────────────────────────────────
    # Engine: Builtin F0 Pitch Detection (zero install)
    # ──────────────────────────────────────────────────────────
    def _classify_all_builtin(
        self,
        audio_path: str,
        subtitles: List[Dict],
        total: int,
        progress_callback: Optional[Callable]
    ) -> List[Dict]:
        """Classifies gender using built-in F0 autocorrelation (SpeakerVerificationService)."""
        import numpy as np
        import subprocess
        import io

        from services.srt_service.speaker_verification import SpeakerVerificationService

        if progress_callback:
            progress_callback("🧠 Stage 3/4: Loading audio for F0 pitch analysis...", 0.20)

        # Load full audio as numpy array (16kHz mono) using ffmpeg
        sr = 16000
        audio_data = self._load_audio_numpy(audio_path, sr)
        total_samples = len(audio_data)

        results = []
        for idx, sub in enumerate(subtitles):
            start_sample = int(sub["start"] * sr)
            end_sample = int(sub["end"] * sr)

            # Clamp to audio bounds
            start_sample = max(0, min(start_sample, total_samples - 1))
            end_sample = max(start_sample + 1, min(end_sample, total_samples))

            chunk = audio_data[start_sample:end_sample]

            # Use project's detect_gender (F0 autocorrelation via scipy)
            gender, pitch, label_kh = SpeakerVerificationService.detect_gender(chunk, sr=sr)
            results.append({
                "gender": gender.lower(),  # normalize to "male"/"female"
                "pitch": pitch
            })

            if progress_callback and (idx + 1) % max(1, total // 10) == 0:
                pct = 0.25 + (idx / total) * 0.55
                progress_callback(
                    f"🧠 F0 classified {idx + 1}/{total} segments...",
                    min(pct, 0.80)
                )

        return results

    # ──────────────────────────────────────────────────────────
    # Engine: inaSpeechSegmenter CNN (more accurate)
    # ──────────────────────────────────────────────────────────
    def _classify_all_ina(
        self,
        audio_path: str,
        subtitles: List[Dict],
        total: int,
        progress_callback: Optional[Callable]
    ) -> List[Dict]:
        """Classifies gender using inaSpeechSegmenter CNN."""
        from pydub import AudioSegment

        audio = AudioSegment.from_file(audio_path)
        segmenter = self._get_ina_segmenter()

        if progress_callback:
            progress_callback("🧠 Stage 3/4: CNN gender classification...", 0.25)

        results = []
        with tempfile.TemporaryDirectory(prefix="gender_srt_") as tmp_dir:
            for idx, sub in enumerate(subtitles):
                start_ms = int(sub["start"] * 1000)
                end_ms = int(sub["end"] * 1000)

                # Clamp to audio duration
                end_ms = min(end_ms, len(audio))
                if start_ms >= end_ms:
                    results.append({"gender": "unknown", "pitch": 0.0})
                    continue

                # Extract audio clip
                clip = audio[start_ms:end_ms]
                clip_path = os.path.join(tmp_dir, f"seg_{idx:05d}.wav")
                clip.export(clip_path, format="wav", parameters=["-ac", "1", "-ar", "16000"])

                # Classify gender via CNN
                gender = self._classify_gender_ina(segmenter, clip_path)
                results.append({"gender": gender, "pitch": 0.0})

                if progress_callback and (idx + 1) % max(1, total // 10) == 0:
                    pct = 0.25 + (idx / total) * 0.55
                    progress_callback(
                        f"🧠 CNN classified {idx + 1}/{total} segments...",
                        min(pct, 0.80)
                    )

        return results

    # ──────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def _load_audio_numpy(audio_path: str, target_sr: int = 16000):
        """Loads audio file as numpy float32 array at target sample rate using ffmpeg."""
        import numpy as np
        import subprocess

        cmd = [
            "ffmpeg", "-i", audio_path,
            "-f", "s16le", "-acodec", "pcm_s16le",
            "-ac", "1", "-ar", str(target_sr),
            "-v", "error", "-"
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {proc.stderr.decode('utf-8', errors='replace')}")

        audio = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32)
        audio = audio / 32768.0  # Normalize to [-1.0, 1.0]
        return audio

    def _parse_srt(self, srt_path: str) -> List[Dict]:
        """Parses SRT file with fallback to raw block parser."""
        subtitles = parse_srt_file(srt_path)
        if subtitles:
            return subtitles

        for enc in ["utf-8-sig", "utf-8", "utf-16", "gbk", "cp1252"]:
            try:
                with open(srt_path, "r", encoding=enc) as f:
                    content = f.read()
                cues = parse_raw_srt_blocks(content)
                if cues:
                    return cues
            except Exception:
                continue
        return []

    def _parse_srt_robust(self, srt_path: str) -> List[Dict]:
        """
        Robust SRT parser that handles common formatting issues:
          - Missing blank lines between blocks
          - Blocks where cue number touches previous text
          - Mixed line endings
        Falls back to standard parsers if robust parse yields nothing.
        """
        content = ""
        for enc in ["utf-8-sig", "utf-8", "utf-16", "gbk", "cp1252"]:
            try:
                with open(srt_path, "r", encoding=enc) as f:
                    content = f.read()
                if content:
                    break
            except Exception:
                continue

        if not content:
            return []

        # Normalize line endings
        content = content.replace("\r\n", "\n").replace("\r", "\n")

        # Strategy: Find all timing lines ("-->") and reconstruct blocks around them
        lines = content.split("\n")
        timing_pattern = re.compile(
            r'(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})'
        )

        # Locate every timing line index
        timing_indices = []
        for i, line in enumerate(lines):
            if timing_pattern.search(line.strip()):
                timing_indices.append(i)

        if not timing_indices:
            # Fallback to standard parsers
            return self._parse_srt(srt_path)

        subtitles = []
        for t_pos, t_idx in enumerate(timing_indices):
            timing_line = lines[t_idx].strip()
            m = timing_pattern.search(timing_line)
            if not m:
                continue

            from utils.time_utils import parse_timestamp_to_seconds
            start_str = m.group(1).replace(".", ",")
            end_str = m.group(2).replace(".", ",")
            start_sec = parse_timestamp_to_seconds(start_str)
            end_sec = parse_timestamp_to_seconds(end_str)

            # Collect text lines after timing until next block boundary
            # Boundary = blank line, next cue number line (digit only), or next timing line
            text_lines = []
            j = t_idx + 1
            # Determine where the next block starts
            next_timing_idx = timing_indices[t_pos + 1] if t_pos + 1 < len(timing_indices) else len(lines)

            while j < next_timing_idx:
                line = lines[j].strip()
                # Stop if this looks like a standalone cue number for the next block
                # (a line that is purely digits, and the next line is a timing line)
                if line.isdigit() and j + 1 < len(lines) and timing_pattern.search(lines[j + 1].strip()):
                    break
                if line == "":
                    j += 1
                    continue
                text_lines.append(line)
                j += 1

            full_text = " ".join(text_lines).strip()
            if not full_text:
                continue

            # Try to get cue ID from line before timing
            cue_id = len(subtitles) + 1
            if t_idx > 0:
                prev_line = lines[t_idx - 1].strip()
                if prev_line.isdigit():
                    cue_id = int(prev_line)

            subtitles.append({
                "id": cue_id,
                "start": start_sec,
                "end": end_sec,
                "text": full_text
            })

        return subtitles if subtitles else self._parse_srt(srt_path)

    @staticmethod
    def _classify_gender_ina(segmenter, clip_path: str) -> str:
        """Runs inaSpeechSegmenter on a single clip. Returns 'male', 'female', or 'unknown'."""
        try:
            results = segmenter(clip_path)
            male_dur = 0.0
            female_dur = 0.0
            for label, start, end in results:
                dur = end - start
                if label == "male":
                    male_dur += dur
                elif label == "female":
                    female_dur += dur

            if male_dur > 0 or female_dur > 0:
                return "male" if male_dur >= female_dur else "female"
            return "unknown"
        except Exception:
            return "unknown"

    @staticmethod
    def _write_srt(entries: List[Dict], output_path: str):
        """Writes a list of subtitle entries to an SRT file."""
        lines = []
        for idx, entry in enumerate(entries, 1):
            start_ts = format_timestamp(entry["start"])
            end_ts = format_timestamp(entry["end"])
            text = entry.get("text", "")
            lines.append(f"{idx}\n{start_ts} --> {end_ts}\n{text}\n")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))


# ──────────────────────────────────────────────────────────
# CLI Entry Point
# ──────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Split SRT by Male/Female speaker gender using audio analysis"
    )
    parser.add_argument("srt", help="Path to input SRT file")
    parser.add_argument("audio", help="Path to input audio file (MP3/WAV)")
    parser.add_argument("--output", "-o", help="Output directory (default: same as SRT)")
    parser.add_argument(
        "--engine", "-e",
        choices=["builtin", "ina"],
        default="builtin",
        help="Gender engine: 'builtin' (F0 pitch, zero install) or 'ina' (CNN, pip install inaSpeechSegmenter)"
    )
    args = parser.parse_args()

    def cli_progress(msg, pct):
        bar_len = 30
        filled = int(bar_len * pct)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"\r  [{bar}] {pct*100:5.1f}%  {msg}", end="", flush=True)
        if pct >= 1.0:
            print()

    splitter = GenderSrtSplitter(engine=args.engine)

    if args.engine == "ina" and not splitter.is_ina_available():
        print("❌ inaSpeechSegmenter is not installed.")
        print("   Run: pip install inaSpeechSegmenter pydub")
        print("   Or use --engine builtin (no extra install needed)")
        sys.exit(1)

    print(f"\n🎬 Gender SRT Splitter (engine: {args.engine})")
    print(f"   SRT:   {args.srt}")
    print(f"   Audio: {args.audio}\n")

    results = splitter.split_by_gender(
        srt_path=args.srt,
        audio_path=args.audio,
        output_dir=args.output,
        progress_callback=cli_progress
    )

    print(f"\n📊 Results:")
    print(f"   Total lines:    {results['total_count']}")
    print(f"   👨 Male lines:   {results['male_count']}")
    print(f"   👩 Female lines: {results['female_count']}")
    print(f"   ❓ Unknown:      {results['unknown_count']}")
    print(f"\n📁 Output files:")
    print(f"   {results['male_srt_path']}")
    print(f"   {results['female_srt_path']}")
    print(f"   {results['tagged_srt_path']}")


if __name__ == "__main__":
    main()
