"""Парсеры экспортов Telegram Desktop."""

from .base import BaseParser
from .html_parser import HTMLParser
from .json_parser import JSONParser
from .custom_export_parser import CustomExportParser

__all__ = ["BaseParser", "HTMLParser", "JSONParser", "CustomExportParser"]
