"""
Subtitle & Dialogue Line Data Models
Provides structured representation for subtitle items, speech cues, and timing.
"""

from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class SubtitleItem:
    """Represents a single subtitle cue line with timing, original text, and translation"""
    id: int
    start: float
    end: float
    original_text: str = ""
    khmer_text: str = ""
    audio_path: Optional[str] = None
    speech_rate: str = "+0%"
    is_dubbed: bool = False
    status: str = "raw"  # raw, translated, dubbed, error

    @property
    def duration(self) -> float:
        return max(0.1, self.end - self.start)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "orig_text": self.original_text,
            "khmer_text": self.khmer_text,
            "audio_path": self.audio_path,
            "rate": self.speech_rate,
            "status": self.status
        }

    @classmethod
    def from_dict(cls, data: dict, default_id: int = 1) -> "SubtitleItem":
        return cls(
            id=data.get("id", default_id),
            start=float(data.get("start", 0.0)),
            end=float(data.get("end", 0.0)),
            original_text=data.get("orig_text") or data.get("original") or data.get("text") or "",
            khmer_text=data.get("khmer_text") or data.get("translated") or "",
            audio_path=data.get("audio_path") or data.get("audio_file"),
            speech_rate=data.get("rate", "+0%"),
            is_dubbed=bool(data.get("audio_path") or data.get("audio_file"))
        )
