"""Базовый класс для генераторов заголовков."""

from abc import ABC, abstractmethod

from ..models.video import VideoData


class BaseTitleGenerator(ABC):
    """Базовый класс для генераторов заголовков видео.
    
    Позволяет создавать различные стратегии формирования заголовков
    на основе данных видео.
    """
    
    @abstractmethod
    def generate(self, video: VideoData) -> str:
        """Сгенерировать заголовок для видео.
        
        Args:
            video: Данные видео.
            
        Returns:
            Сгенерированный заголовок.
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Получить имя генератора.
        
        Returns:
            Имя генератора для использования в конфигурации.
        """
        pass
