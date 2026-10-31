"""
Data Models and Types for Downloader Service
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class DownloadProgress:
    """Live progress data sent via callbacks during downloads."""
    status: str = "downloading"   # 'downloading', 'finished', 'error', 'canceled'
    percent: float = 0.0          # 0.0 to 100.0
    speed_mb: float = 0.0         # Download speed in MB/s
    downloaded_bytes: int = 0
    total_bytes: int = 0
    part_idx: int = 1
    total_parts: int = 1
    title: str = ""
    eta_seconds: Optional[int] = None
    sublabel: str = ""
    error_message: str = ""


@dataclass
class EpisodeEntry:
    """Representation of an individual video/episode in a series or playlist."""
    id: str
    ep_num: int
    title: str
    url: str = ""
    webpage_url: str = ""
    duration: float = 0.0
    thumbnail: str = ""
    is_locked: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityOption:
    """Quality selection format choice."""
    label: str
    format_id: str
    resolution: str = ""
    filesize_mb: float = 0.0
    fps: Optional[int] = None
    vcodec: str = ""
    acodec: str = ""
    ext: str = "mp4"


@dataclass
class VideoMetadata:
    """Comprehensive video or playlist metadata."""
    id: str
    title: str
    url: str
    uploader: str = ""
    thumbnail: str = ""
    duration: float = 0.0
    description: str = ""
    tags: List[str] = field(default_factory=list)
    is_playlist: bool = False
    entries: List[Dict[str, Any]] = field(default_factory=list)
    formats: List[Dict[str, Any]] = field(default_factory=list)
    subtitles: Dict[str, Any] = field(default_factory=dict)
    automatic_captions: Dict[str, Any] = field(default_factory=dict)
    raw_info: Dict[str, Any] = field(default_factory=dict)

