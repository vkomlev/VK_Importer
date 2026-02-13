"""Генераторы заголовков для видео."""

from .base import BaseTitleGenerator
from .generators import (
    SimpleTitleGenerator,
    DateTitleGenerator,
    DescriptionTitleGenerator,
    CompositeTitleGenerator,
)
from .ege_generators import (
    EGETopicTitleGenerator,
    EGETaskTitleGenerator,
    EGEAutoTitleGenerator,
)
from .python_generators import (
    PythonTopicTitleGenerator,
    PythonTaskTitleGenerator,
    PythonAutoTitleGenerator,
)
from .oge_generators import (
    OGETopicTitleGenerator,
    OGETaskTitleGenerator,
    OGEAutoTitleGenerator,
)

__all__ = [
    "BaseTitleGenerator",
    "SimpleTitleGenerator",
    "DateTitleGenerator",
    "DescriptionTitleGenerator",
    "CompositeTitleGenerator",
    "EGETopicTitleGenerator",
    "EGETaskTitleGenerator",
    "EGEAutoTitleGenerator",
    "PythonTopicTitleGenerator",
    "PythonTaskTitleGenerator",
    "PythonAutoTitleGenerator",
    "OGETopicTitleGenerator",
    "OGETaskTitleGenerator",
    "OGEAutoTitleGenerator",
]
