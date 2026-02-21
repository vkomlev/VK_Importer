"""Адаптеры направлений публикации."""

from .vk import VKDestinationAdapter
from .youtube_stub import YouTubeDestinationAdapter

__all__ = ["VKDestinationAdapter", "YouTubeDestinationAdapter"]
