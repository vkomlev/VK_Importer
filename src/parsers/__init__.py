"""Парсеры экспортов Telegram Desktop."""

from .base import BaseParser
from .html_parser import HTMLParser
from .json_parser import JSONParser

__all__ = ["BaseParser", "HTMLParser", "JSONParser"]
