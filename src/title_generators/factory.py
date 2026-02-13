"""Фабрика генераторов заголовков."""

from typing import Optional

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


class TitleGeneratorFactory:
    """Фабрика для создания генераторов заголовков."""
    
    _generators = {
        # Базовые генераторы
        "simple": SimpleTitleGenerator,
        "date": DateTitleGenerator,
        "description": DescriptionTitleGenerator,
        "composite": CompositeTitleGenerator,
        
        # Генераторы для ЕГЭ
        "ege_topic": EGETopicTitleGenerator,
        "ege_task": EGETaskTitleGenerator,
        "ege_auto": EGEAutoTitleGenerator,
        
        # Генераторы для Python
        "python_topic": PythonTopicTitleGenerator,
        "python_task": PythonTaskTitleGenerator,
        "python_auto": PythonAutoTitleGenerator,
        # Генераторы для ОГЭ
        "oge_topic": OGETopicTitleGenerator,
        "oge_task": OGETaskTitleGenerator,
        "oge_auto": OGEAutoTitleGenerator,
    }
    
    @classmethod
    def create(cls, generator_name: str, **kwargs) -> Optional[BaseTitleGenerator]:
        """Создать генератор заголовков.
        
        Args:
            generator_name: Имя генератора.
            **kwargs: Дополнительные параметры для генератора.
            
        Returns:
            Экземпляр генератора или None, если генератор не найден.
        """
        generator_class = cls._generators.get(generator_name)
        if not generator_class:
            return None
        
        try:
            return generator_class(**kwargs)
        except TypeError:
            # Если генератор не принимает kwargs, создаем без них
            return generator_class()
    
    @classmethod
    def list_available(cls) -> list[str]:
        """Получить список доступных генераторов.
        
        Returns:
            Список имен генераторов.
        """
        return list(cls._generators.keys())
    
    @classmethod
    def register(cls, name: str, generator_class: type[BaseTitleGenerator]):
        """Зарегистрировать новый генератор.
        
        Args:
            name: Имя генератора.
            generator_class: Класс генератора.
        """
        cls._generators[name] = generator_class
