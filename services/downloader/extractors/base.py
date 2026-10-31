"""
Base Extractor Class for Custom Media & Drama Platforms
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Callable


class BaseDramaExtractor(ABC):
    """Abstract base class for drama & video platform extractors."""

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        self.log_callback = log_callback

    def log(self, message: str):
        if self.log_callback:
            self.log_callback(message)

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """Determines whether this extractor supports the given URL."""
        pass

    @abstractmethod
    def extract_series(self, url: str, cookie_file: str = "") -> Optional[Dict[str, Any]]:
        """Extracts playlist/series metadata, episodes, titles, covers, and streams."""
        pass

