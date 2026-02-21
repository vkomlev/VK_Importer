"""Source-адаптер: контент из экспортов на диске (TG export, tg_parser и т.д.)."""

import logging
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

from ..base import SourceAdapter

if TYPE_CHECKING:
    from ...storage.database import VideoStorage
from ...models.content import ContentItem
from ...config.source_registry import get_export_paths
from ...parsers.html_parser import HTMLParser
from ...parsers.json_parser import JSONParser
from ...parsers.custom_export_parser import CustomExportParser
from ...title_generators.factory import TitleGeneratorFactory
from ...config.registry import CHANNEL_TO_TITLE_GENERATOR

logger = logging.getLogger(__name__)


class ExportFilesystemSourceAdapter(SourceAdapter):
    """Читает экспорты с диска (те же пути, что scan) и возвращает ContentItem."""

    def __init__(self, storage: Optional["VideoStorage"] = None):
        """storage опционален: если передан, используется get_course_for_folder для channel."""
        self._storage = storage

    @property
    def source_id(self) -> str:
        return "export_fs"

    def fetch(
        self,
        source_filter: Optional[str] = None,
        input_dir: Optional[Path] = None,
        **options: object,
    ) -> List[ContentItem]:
        paths = get_export_paths(source_filter=source_filter, input_dir=input_dir)
        channel_generators = {
            ch: TitleGeneratorFactory.create(gen_name)
            for ch, gen_name in CHANNEL_TO_TITLE_GENERATOR.items()
        }
        items: List[ContentItem] = []

        for export_path in paths:
            export_path = Path(export_path)
            if not export_path.exists():
                logger.warning("Путь не существует: %s", export_path)
                continue

            parser = None
            if HTMLParser(export_path).detect_format():
                parser = HTMLParser(export_path)
            elif CustomExportParser(export_path).detect_format():
                parser = CustomExportParser(export_path)
            elif JSONParser(export_path).detect_format():
                parser = JSONParser(export_path)
            else:
                logger.debug("Формат не определён: %s", export_path)
                continue

            try:
                videos = parser.parse()
            except Exception as e:
                logger.error("Ошибка парсинга %s: %s", export_path, e)
                continue

            channel = None
            if self._storage:
                channel = self._storage.get_course_for_folder(str(export_path))

            for video in videos:
                video.channel = channel or video.channel
                gen = channel_generators.get(video.channel) or TitleGeneratorFactory.create("simple")
                if gen:
                    video.title = gen.generate(video)
                else:
                    video.title = video.file_path.stem
                item = ContentItem.from_video_data(video, source_folder=str(export_path))
                items.append(item)

            logger.debug("Обработано %s видео из %s", len(videos), export_path)

        return items
