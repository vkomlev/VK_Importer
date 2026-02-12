"""Хранилище данных о видео."""

from .database import VideoStorage, VideoRecord
from .duplicate_detector import DuplicateDetector

__all__ = ["VideoStorage", "VideoRecord", "DuplicateDetector"]
