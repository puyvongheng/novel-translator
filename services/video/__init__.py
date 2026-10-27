"""
Video Processing & Rendering Services Package
Handles subtitle burning, audio multiplexing, and chunked background export pipelines.
"""

from services.video.video_burner import SubtitleBurner
from services.video.chunk_pipeline import ChunkedPipeline, VideoChunk
from services.video.segment_editor import SegmentEditorService
from services.video.face_tracking_service import (
    FaceMeshDetector, AutoFaceBlurProcessor, FaceARPropsEngine, FaceKeypoints
)

__all__ = [
    "SubtitleBurner",
    "ChunkedPipeline",
    "VideoChunk",
    "SegmentEditorService",
    "FaceMeshDetector",
    "AutoFaceBlurProcessor",
    "FaceARPropsEngine",
    "FaceKeypoints"
]
