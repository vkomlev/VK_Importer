"""Унифицированная доменная модель контента (Phase 3)."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .video import VideoData


@dataclass
class MediaRef:
    """Ссылка на медиа-файл (видео, изображение и т.д.)."""
    type: str  # "video", "image", "audio"
    path: Optional[Path] = None
    url: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.path is not None and not isinstance(self.path, Path):
            self.path = Path(self.path)


@dataclass
class ContentItem:
    """Единая сущность публикации для любых источников и направлений.

    Позволяет описывать контент из TG, RSS, VK и публиковать в VK, YouTube, Дзен и т.д.
    """
    source: str  # Идентификатор источника (например "tg_export", "ege", "tg_parser")
    external_id: str  # Уникальный в рамках источника ID (путь к файлу, message_id и т.д.)
    text: str = ""  # Текст/описание
    title: str = ""
    published_at: Optional[datetime] = None
    media: list[MediaRef] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def primary_media_path(self) -> Optional[Path]:
        """Путь к первому видео (для совместимости с текущим pipeline)."""
        for m in self.media:
            if m.type == "video" and m.path and m.path.exists():
                return m.path
        return None

    @classmethod
    def from_video_record(
        cls,
        file_path: str,
        title: str,
        description: str,
        channel: Optional[str] = None,
        source_folder: str = "",
        date: Optional[datetime] = None,
        record_id: Optional[int] = None,
    ) -> "ContentItem":
        """Собрать ContentItem из полей VideoRecord (для публикации из БД)."""
        path = Path(file_path)
        return cls(
            source=source_folder or "unknown",
            external_id=str(record_id) if record_id is not None else path.name,
            title=title,
            text=description or "",
            published_at=date,
            media=[MediaRef(type="video", path=path)] if path.exists() else [],
            metadata={"channel": channel, "source_folder": source_folder},
        )

    @classmethod
    def from_video_data(cls, video: VideoData, source_folder: str = "", external_id: str = "") -> "ContentItem":
        """Собрать ContentItem из VideoData (результат парсеров)."""
        return cls(
            source=source_folder or "export",
            external_id=external_id or video.file_path.name,
            title=video.title,
            text=video.description or "",
            published_at=video.date,
            media=[MediaRef(type="video", path=video.file_path)],
            metadata={"channel": video.channel},
        )

    def to_video_data(self) -> Optional[VideoData]:
        """Преобразовать в VideoData для VKPublisher (если есть видеофайл)."""
        path = self.primary_media_path()
        if path is None:
            return None
        return VideoData(
            file_path=path,
            title=self.title,
            description=self.text,
            date=self.published_at,
            channel=self.metadata.get("channel"),
        )


@dataclass
class PublicationResult:
    """Результат попытки публикации в destination (аудит 5.1)."""
    destination: str  # "vk", "youtube", "rutube", ...
    ok: bool
    remote_url: Optional[str] = None
    error_code: Optional[str] = None
    retry_count: int = 0
