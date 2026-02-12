"""Публикатор видео в VK Video."""

import time
from pathlib import Path
from typing import Optional
import logging
from datetime import datetime

import vk_api
from vk_api.upload import VkUpload
from vk_api.exceptions import VkApiError, ApiError

from ..models.video import VideoData

logger = logging.getLogger(__name__)


class VKPublisherError(Exception):
    """Исключение для ошибок публикации."""
    pass


class VKPublisher:
    """Публикатор видео в VK Video через VK API."""
    
    def __init__(
        self,
        access_token: str,
        group_id: Optional[int] = None,
        delay_between_uploads: float = 5.0,
        max_retries: int = 3,
        retry_delay: float = 10.0,
    ):
        """Инициализировать публикатор.
        
        Args:
            access_token: Токен доступа VK API.
            group_id: ID группы для публикации (обязательно для загрузки в сообщество).
            delay_between_uploads: Задержка между загрузками в секундах (по умолчанию 5 сек).
            max_retries: Максимальное количество повторных попыток при ошибке.
            retry_delay: Задержка перед повторной попыткой в секундах.
        """
        self.access_token = access_token
        self.group_id = group_id
        
        if not group_id:
            logger.warning("group_id не указан. Видео будет загружаться к пользователю, а не в сообщество.")
        self.delay_between_uploads = delay_between_uploads
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Инициализация VK API
        try:
            self.vk_session = vk_api.VkApi(token=access_token)
            self.vk = self.vk_session.get_api()
            self.upload = VkUpload(self.vk_session)
            logger.info("VK API инициализирован успешно")
        except Exception as e:
            logger.error(f"Ошибка инициализации VK API: {e}")
            raise VKPublisherError(f"Не удалось инициализировать VK API: {e}")
    
    def _handle_api_error(self, error: Exception, attempt: int) -> bool:
        """Обработать ошибку API и определить, стоит ли повторять попытку.
        
        Args:
            error: Исключение от VK API.
            attempt: Номер текущей попытки.
            
        Returns:
            True если стоит повторить попытку, False иначе.
        """
        if isinstance(error, ApiError):
            error_code = error.code
            
            # Ошибки, при которых стоит повторить попытку
            retryable_errors = {
                6,   # Слишком много запросов в секунду
                9,   # Flood control: слишком много однотипных действий
                10,  # Внутренняя ошибка сервера
                14,  # Требуется ввод капчи
            }
            
            if error_code in retryable_errors:
                if attempt < self.max_retries:
                    logger.warning(
                        f"Ошибка API {error_code}: {error}. "
                        f"Повторная попытка {attempt + 1}/{self.max_retries} через {self.retry_delay} сек"
                    )
                    return True
                else:
                    logger.error(f"Достигнуто максимальное количество попыток. Ошибка: {error}")
                    return False
            else:
                # Критические ошибки, которые не стоит повторять
                logger.error(f"Критическая ошибка API {error_code}: {error}")
                return False
        
        # Для других типов ошибок (сетевые, таймауты) стоит повторить
        if attempt < self.max_retries:
            logger.warning(
                f"Ошибка при загрузке: {error}. "
                f"Повторная попытка {attempt + 1}/{self.max_retries} через {self.retry_delay} сек"
            )
            return True
        else:
            logger.error(f"Достигнуто максимальное количество попыток. Ошибка: {error}")
            return False
    
    def publish(
        self,
        video: VideoData,
    ) -> Optional[str]:
        """Опубликовать видео в VK Video.
        
        Args:
            video: Данные видео для публикации.
            
        Returns:
            URL опубликованного видео или None при ошибке.
        """
        for attempt in range(self.max_retries):
            try:
                logger.info(
                    f"Загрузка видео: {video.file_path.name} "
                    f"(попытка {attempt + 1}/{self.max_retries})"
                )
                
                # Подготовка параметров загрузки
                # Контракт: заголовок -> name, полное описание -> description
                # Видео загружается в сообщество (группу), а не к пользователю
                upload_params = {
                    "video_file": str(video.file_path),
                    "name": video.title,  # Заголовок в название видео
                    "description": video.description if video.description else "",  # Полный текст сообщения
                }
                
                # Загружаем видео в сообщество (группу)
                if self.group_id:
                    # VkUpload.video() принимает group_id как параметр
                    # Передаем положительный ID группы, VK API сам преобразует его
                    upload_params["group_id"] = self.group_id
                    logger.debug(f"Загрузка видео в сообщество (group_id={self.group_id})")
                else:
                    logger.warning("group_id не указан! Видео будет загружено к пользователю, а не в сообщество.")
                
                # Загрузка видео
                logger.debug(f"Параметры загрузки: name='{video.title[:50]}...', description_length={len(video.description) if video.description else 0}")
                video_response = self.upload.video(**upload_params)
                
                video_id = video_response.get("video_id")
                owner_id = video_response.get("owner_id")
                
                if not video_id or not owner_id:
                    logger.error(f"Не удалось получить ID видео из ответа: {video_response}")
                    return None
                
                video_url = f"https://vk.com/video{owner_id}_{video_id}"
                
                # Проверяем, что видео загружено в группу (owner_id должен быть отрицательным)
                if owner_id < 0:
                    logger.info(f"✓ Видео успешно загружено в сообщество: {video_url}")
                else:
                    logger.warning(f"⚠ Видео загружено к пользователю (owner_id={owner_id}), а не в сообщество!")
                
                post_url = None
                
                # Публикуем видео на стене сообщества (если указан group_id)
                if self.group_id:
                    try:
                        # Формат вложения: video{owner_id}_{video_id}
                        attachment = f"video{owner_id}_{video_id}"
                        
                        # Публикуем на стене группы
                        # owner_id должен быть отрицательным для групп
                        # Пробуем разные варианты параметров
                        group_owner_id = -abs(self.group_id)
                        
                        # Вариант 1: С from_group=1 (публикация от имени группы)
                        try:
                            wall_params = {
                                "owner_id": group_owner_id,
                                "message": video.description if video.description else "",
                                "attachments": attachment,
                                "from_group": 1,  # Публикация от имени группы
                            }
                            logger.debug(f"Попытка публикации на стене с from_group=1, owner_id={group_owner_id}")
                            wall_response = self.vk.wall.post(**wall_params)
                            
                            post_id = wall_response.get("post_id")
                            if post_id:
                                post_url = f"https://vk.com/wall{group_owner_id}_{post_id}"
                                logger.info(f"✓ Видео опубликовано на стене сообщества: {post_url}")
                            else:
                                logger.warning(f"Видео загружено, но не удалось опубликовать на стене. Ответ: {wall_response}")
                        except ApiError as e1:
                            if e1.code == 15:
                                # Пробуем без from_group
                                logger.debug(f"Ошибка 15 с from_group=1, пробуем без from_group")
                                try:
                                    wall_params = {
                                        "owner_id": group_owner_id,
                                        "message": video.description if video.description else "",
                                        "attachments": attachment,
                                    }
                                    wall_response = self.vk.wall.post(**wall_params)
                                    
                                    post_id = wall_response.get("post_id")
                                    if post_id:
                                        post_url = f"https://vk.com/wall{group_owner_id}_{post_id}"
                                        logger.info(f"✓ Видео опубликовано на стене сообщества: {post_url}")
                                    else:
                                        logger.warning(f"Видео загружено, но не удалось опубликовать на стене. Ответ: {wall_response}")
                                except ApiError as e2:
                                    if e2.code == 15:
                                        logger.warning(
                                            f"Ошибка доступа при публикации на стене (код {e2.code}): {e2}. "
                                            f"Метод wall.post доступен только для Standalone приложений. "
                                            f"Если ваше приложение Website/iFrame, используйте JavaScript SDK или создайте Standalone приложение."
                                        )
                                    else:
                                        logger.warning(f"Видео загружено, но ошибка при публикации на стене: {e2}")
                            else:
                                raise  # Пробрасываем другие ошибки
                    except Exception as e:
                        logger.warning(f"Видео загружено, но ошибка при публикации на стене: {e}")
                        # Не возвращаем None, так как видео уже загружено
                
                # Сохраняем post_url в атрибуте для доступа извне
                video._post_url = post_url
                
                return video_url
                    
            except (VkApiError, ApiError) as e:
                should_retry = self._handle_api_error(e, attempt)
                if not should_retry:
                    return None
                
                # Ждем перед повторной попыткой
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    
            except Exception as e:
                logger.error(f"Неожиданная ошибка при публикации видео {video.file_path}: {e}", exc_info=True)
                
                # Для неожиданных ошибок тоже делаем повторные попытки
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    return None
        
        logger.error(f"Не удалось опубликовать видео {video.file_path} после {self.max_retries} попыток")
        return None
    
    def publish_batch(
        self,
        videos: list[VideoData],
        delay_between_uploads: Optional[float] = None,
    ) -> dict[str, Optional[str]]:
        """Опубликовать несколько видео.
        
        Args:
            videos: Список видео для публикации.
            delay_between_uploads: Задержка между загрузками в секундах 
                                   (если None, используется значение из __init__).
            
        Returns:
            Словарь {file_path: video_url} с результатами публикации.
        """
        if delay_between_uploads is None:
            delay_between_uploads = self.delay_between_uploads
        
        results = {}
        total = len(videos)
        
        logger.info(f"Начало публикации пакета из {total} видео")
        
        for idx, video in enumerate(videos, 1):
            logger.info(f"[{idx}/{total}] Публикация: {video.file_path.name}")
            
            video_url = self.publish(video)
            results[str(video.file_path)] = video_url
            
            # Задержка между загрузками (кроме последнего видео)
            if idx < total:
                logger.debug(f"Ожидание {delay_between_uploads} сек перед следующей загрузкой...")
                time.sleep(delay_between_uploads)
        
        successful = sum(1 for url in results.values() if url is not None)
        failed = total - successful
        
        logger.info(
            f"Публикация пакета завершена: "
            f"успешно {successful}, ошибок {failed} из {total}"
        )
        
        return results
