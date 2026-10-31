"""
Custom Drama & Media Extractors Package
"""

from services.downloader.extractors.base import BaseDramaExtractor
from services.downloader.extractors.hongguo import HongguoExtractor
from services.downloader.extractors.hainanyuyue import HainanYuyueExtractor
from services.downloader.extractors.stardust import StardustExtractor
from services.downloader.extractors.kisskh import KissKHExtractor
from services.downloader.extractors.bilibili import BilibiliBangumiExtractor
from services.downloader.extractors.douyin import DouyinExtractor
from services.downloader.extractors.sabayflix import SabayflixExtractor
from services.downloader.extractors.khdiamond import KHDiamondExtractor
from services.downloader.extractors.dramabox import DramaBoxExtractor
from services.downloader.extractors.universal_social import UniversalSocialExtractor

__all__ = [
    "BaseDramaExtractor",
    "HongguoExtractor",
    "HainanYuyueExtractor",
    "StardustExtractor",
    "KissKHExtractor",
    "BilibiliBangumiExtractor",
    "DouyinExtractor",
    "SabayflixExtractor",
    "KHDiamondExtractor",
    "DramaBoxExtractor",
    "UniversalSocialExtractor"
]
