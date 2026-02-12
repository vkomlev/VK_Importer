"""Генераторы заголовков для видео."""

from .base import BaseTitleGenerator
from .generators import (
    SimpleTitleGenerator,
    DateTitleGenerator,
    DescriptionTitleGenerator,
)

__all__ = [
    "BaseTitleGenerator",
    "SimpleTitleGenerator",
    "DateTitleGenerator",
    "DescriptionTitleGenerator",
]
