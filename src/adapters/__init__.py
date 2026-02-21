"""Адаптеры источников и направлений (Phase 3)."""

from .base import SourceAdapter, DestinationAdapter
from .sources import ExportFilesystemSourceAdapter
from .destinations import VKDestinationAdapter, YouTubeDestinationAdapter

__all__ = [
    "SourceAdapter",
    "DestinationAdapter",
    "ExportFilesystemSourceAdapter",
    "VKDestinationAdapter",
    "YouTubeDestinationAdapter",
]
