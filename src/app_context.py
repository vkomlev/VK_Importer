"""Контекст приложения: единая точка инициализации VK publisher (Phase 2). Убирает дубли env/publisher в CLI."""

import logging
from typing import Callable, Optional

from .utils.env_utils import get_env_var
from .publisher.vk_publisher import VKPublisher, VKPublisherError

logger = logging.getLogger(__name__)


class FatalUploadError(Exception):
    """Фатальная ошибка окружения/API при загрузке; вызывающий код должен записать summary и выйти с EXIT_FATAL."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def get_vk_publisher(
    delay: float,
    max_retries: int = 3,
    group_id_required: bool = True,
    on_token_expired: Optional[Callable[[], Optional[str]]] = None,
) -> VKPublisher:
    """Создать VKPublisher из переменных окружения.

    Args:
        delay: Задержка между запросами (сек).
        max_retries: Макс. повторов при ошибке.
        group_id_required: True для загрузки видео (нужен VK_GROUP_ID), False для delete/edit (только токен).
        on_token_expired: Callback при истечении токена (обновление и возврат нового).

    Returns:
        VKPublisher.

    Raises:
        FatalUploadError: Нет токена, нет/неверный group_id (если group_id_required), VKPublisherError.
    """
    access_token = get_env_var("VK_ACCESS_TOKEN")
    if not access_token:
        raise FatalUploadError("VK_ACCESS_TOKEN не найден в .env файле")

    group_id: Optional[int] = None
    if group_id_required:
        group_id_str = get_env_var("VK_GROUP_ID")
        if not group_id_str:
            raise FatalUploadError("VK_GROUP_ID не найден в .env файле")
        try:
            group_id = int(group_id_str)
        except ValueError:
            raise FatalUploadError(f"Неверный формат VK_GROUP_ID: {group_id_str}")

    if group_id is not None:
        logger.info(
            "VK publisher: group_id=%s (токен — user OAuth с правом video, не сервисный ключ)",
            group_id,
        )
    try:
        return VKPublisher(
            access_token=access_token,
            group_id=group_id,
            delay_between_uploads=delay,
            max_retries=max_retries,
            on_token_expired=on_token_expired,
        )
    except VKPublisherError as e:
        raise FatalUploadError(str(e))
