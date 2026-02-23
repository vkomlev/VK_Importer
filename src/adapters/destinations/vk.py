"""Адаптер публикации в VK Video (обёртка над VKPublisher)."""

import logging
from typing import TYPE_CHECKING

from ..base import DestinationAdapter
from ...models.content import ContentItem, PublicationResult
from ...publisher.vk_publisher import VKApi1051Error

if TYPE_CHECKING:
    from ...publisher.vk_publisher import VKPublisher

logger = logging.getLogger(__name__)


class VKDestinationAdapter(DestinationAdapter):
    """Публикация в VK Video через существующий VKPublisher."""

    def __init__(self, publisher: "VKPublisher"):
        self._publisher = publisher

    @property
    def destination_id(self) -> str:
        return "vk"

    def publish(self, item: ContentItem, **options: object) -> PublicationResult:
        video_data = item.to_video_data()
        if video_data is None:
            return PublicationResult(
                destination=self.destination_id,
                ok=False,
                error_code="NO_VIDEO",
            )
        try:
            url = self._publisher.publish(video_data)
        except VKApi1051Error:
            return PublicationResult(
                destination=self.destination_id,
                ok=False,
                error_code="VK_API_1051",
            )
        if url:
            return PublicationResult(destination=self.destination_id, ok=True, remote_url=url)
        return PublicationResult(
            destination=self.destination_id,
            ok=False,
            error_code="PUBLISH_FAILED",
        )
