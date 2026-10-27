"""
SRT Formatter & File Generator Service
Normalizes subtitle items, fixes overlapping timestamps, and writes clean .srt files.
"""

import os
from utils.time_utils import format_timestamp
from utils.srt_utils import fix_overlapping_subtitles, generate_srt_content


class SrtFormatter:
    """
    Utilities for normalizing, fixing and serializing subtitle datasets.
    """

    @staticmethod
    def normalize_items(items: list[dict]) -> list[dict]:
        """Ensures all standard keys required by Movie Studio UI and engines exist."""
        normalized = []
        for idx, sub in enumerate(items):
            orig = sub.get("orig_text") or sub.get("original") or sub.get("text") or ""
            khmer = sub.get("khmer_text") or sub.get("translated") or ""
            start = float(sub.get("start", 0.0))
            end = float(sub.get("end", start + 1.0))
            if end <= start:
                end = start + 0.35

            normalized.append({
                "id": idx + 1,
                "start": round(start, 2),
                "end": round(end, 2),
                "orig_text": orig.strip(),
                "original": orig.strip(),
                "text": orig.strip(),
                "khmer_text": khmer.strip(),
                "translated": khmer.strip(),
                "rate": sub.get("rate", "+0%"),
                "status": sub.get("status", "raw"),
                "audio_file": sub.get("audio_file", None)
            })
        return normalized

    @classmethod
    def clean_and_fix_overlaps(cls, items: list[dict]) -> tuple[list[dict], int]:
        """Normalizes items and eliminates overlapping timestamps."""
        norm = cls.normalize_items(items)
        fixed_items, fixed_count = fix_overlapping_subtitles(norm)
        return fixed_items, fixed_count

    @classmethod
    def save_to_file(cls, items: list[dict], output_srt_path: str, prefer_khmer: bool = False) -> str:
        """
        Generates and saves standard .srt file content to disk.
        Returns the absolute path to the saved file.
        """
        fixed_items, _ = cls.clean_and_fix_overlaps(items)
        content = generate_srt_content(fixed_items, prefer_khmer=prefer_khmer)

        os.makedirs(os.path.dirname(os.path.abspath(output_srt_path)), exist_ok=True)
        with open(output_srt_path, "w", encoding="utf-8") as f:
            f.write(content)

        return os.path.abspath(output_srt_path)
