"""Конфигурация и реестры (курсы, каналы, источники)."""

from .registry import COURSE_TYPES, CHANNEL_TO_TITLE_GENERATOR
from .source_registry import get_export_paths

__all__ = ["COURSE_TYPES", "CHANNEL_TO_TITLE_GENERATOR", "get_export_paths"]
