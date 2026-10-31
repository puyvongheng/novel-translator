"""
Unified Downloader Service Package
Clean, decoupled architecture for video & drama downloading, metadata analysis,
CENC decryption, and multi-format extraction.
"""

from services.downloader.models import (
    DownloadProgress,
    QualityOption,
    EpisodeEntry,
    VideoMetadata
)
from services.downloader.helpers import (
    get_ffmpeg_binary_path,
    strip_ansi,
    normalize_video_url,
    sanitize_folder_name,
    get_custom_referer,
    format_duration_str,
    download_cover_image
)
from services.downloader.cenc_decryptor import unwrap_spade
from services.downloader.bypass import BypassEngine
from services.downloader.extractors import (
    BaseDramaExtractor,
    HongguoExtractor,
    HainanYuyueExtractor,
    StardustExtractor,
    KissKHExtractor,
    BilibiliBangumiExtractor,
    DouyinExtractor,
    SabayflixExtractor,
    KHDiamondExtractor
)
from services.downloader.downloader_service import DownloaderService

__all__ = [
    "DownloaderService",
    "DownloadProgress",
    "QualityOption",
    "EpisodeEntry",
    "VideoMetadata",
    "get_ffmpeg_binary_path",
    "strip_ansi",
    "normalize_video_url",
    "sanitize_folder_name",
    "get_custom_referer",
    "format_duration_str",
    "download_cover_image",
    "unwrap_spade",
    "BypassEngine",
    "BaseDramaExtractor",
    "HongguoExtractor",
    "HainanYuyueExtractor",
    "StardustExtractor",
    "KissKHExtractor",
    "BilibiliBangumiExtractor",
    "DouyinExtractor",
    "SabayflixExtractor",
    "KHDiamondExtractor"
]

