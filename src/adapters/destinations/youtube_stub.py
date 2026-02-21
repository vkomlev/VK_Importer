"""Заглушка адаптера публикации в YouTube (Phase 3 skeleton)."""

import logging

from ..base import DestinationAdapter
from ...models.content import ContentItem, PublicationResult

logger = logging.getLogger(__name__)


class YouTubeDestinationAdapter(DestinationAdapter):
    """Заглушка: публикация в YouTube не реализована."""

    @property
    def destination_id(self) -> str:
        return "youtube"

    def publish(self, item: ContentItem, **options: object) -> PublicationResult:
        logger.info("YouTube adapter (stub): публикация не реализована, item=%s", item.external_id)
        return PublicationResult(
            destination=self.destination_id,
            ok=False,
            error_code="NOT_IMPLEMENTED",
        )
