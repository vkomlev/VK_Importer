"""Интерфейсы адаптеров источников и направлений (Phase 3)."""

from abc import ABC, abstractmethod
from typing import List

from ..models.content import ContentItem, PublicationResult


class SourceAdapter(ABC):
    """Адаптер источника контента (TG export, RSS, VK source и т.д.)."""

    @property
    @abstractmethod
    def source_id(self) -> str:
        """Идентификатор источника для логов и маршрутизации."""
        pass

    @abstractmethod
    def fetch(self, **options: object) -> List[ContentItem]:
        """Получить список элементов контента из источника.

        Returns:
            Список ContentItem. Пустой список при отсутствии данных.
        """
        pass


class DestinationAdapter(ABC):
    """Адаптер направления публикации (VK, YouTube, Дзен, WordPress и т.д.)."""

    @property
    @abstractmethod
    def destination_id(self) -> str:
        """Идентификатор направления (vk, youtube, rutube, ...)."""
        pass

    @abstractmethod
    def publish(self, item: ContentItem, **options: object) -> PublicationResult:
        """Опубликовать элемент контента в направление.

        Returns:
            PublicationResult с remote_url при успехе или error_code при ошибке.
        """
        pass
