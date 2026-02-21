"""База данных для хранения информации о видео."""

import sqlite3
import hashlib
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

from ..config.registry import COURSE_TYPES

logger = logging.getLogger(__name__)


@dataclass
class VideoRecord:
    """Запись о видео в хранилище."""
    
    id: Optional[int] = None
    file_path: str = ""
    file_hash: Optional[str] = None  # Хеш файла для определения дубликатов
    title: str = ""
    description: str = ""
    channel: Optional[str] = None
    source_folder: str = ""  # Папка экспорта (например, "input/Экпорты ЕГЭ/Апрель 25")
    date: Optional[datetime] = None
    uploaded: bool = False  # Статус загрузки
    upload_date: Optional[datetime] = None
    video_url: Optional[str] = None  # URL загруженного видео в VK
    post_url: Optional[str] = None  # URL поста на стене
    error_message: Optional[str] = None  # Сообщение об ошибке при загрузке
    skip_upload: bool = False  # Пропускать при загрузке (не загружать)
    
    def to_dict(self) -> dict:
        """Преобразовать в словарь."""
        result = asdict(self)
        if self.date:
            result['date'] = self.date.isoformat()
        if self.upload_date:
            result['upload_date'] = self.upload_date.isoformat()
        return result


class VideoStorage:
    """Хранилище видео в SQLite базе данных."""
    
    def __init__(self, db_path: Path = Path("videos.db")):
        """Инициализировать хранилище.
        
        Args:
            db_path: Путь к файлу базы данных.
        """
        self.db_path = Path(db_path)
        self._init_database()
    
    def _init_database(self):
        """Инициализировать структуру базы данных."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL UNIQUE,
                file_hash TEXT,
                title TEXT NOT NULL,
                description TEXT,
                channel TEXT,
                source_folder TEXT NOT NULL,
                date TEXT,
                uploaded INTEGER DEFAULT 0,
                upload_date TEXT,
                video_url TEXT,
                post_url TEXT,
                error_message TEXT,
                skip_upload INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Миграция: добавить skip_upload, если таблица уже существовала
        try:
            cursor.execute("ALTER TABLE videos ADD COLUMN skip_upload INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # колонка уже есть

        # Индексы для быстрого поиска
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_path ON videos(file_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_hash ON videos(file_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_uploaded ON videos(uploaded)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_channel ON videos(channel)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_source_folder ON videos(source_folder)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_skip_upload ON videos(skip_upload)")
        
        # Таблица маппинга: папка -> тип курса (Python, ЕГЭ, ОГЭ)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS folder_course_mapping (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folder_path TEXT NOT NULL UNIQUE,
                course_type TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_folder_mapping_path ON folder_course_mapping(folder_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_folder_mapping_course ON folder_course_mapping(course_type)")
        
        conn.commit()
        conn.close()
        self._ensure_default_folder_mappings()
        logger.info(f"База данных инициализирована: {self.db_path}")
    
    def _ensure_default_folder_mappings(self) -> None:
        """Заполнить маппинг папок значениями по умолчанию, если таблица пуста."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM folder_course_mapping")
        if cursor.fetchone()[0] == 0:
            defaults = [
                ("input/Экпорты ЕГЭ", "ЕГЭ"),
                ("input/Экспорт Python", "Python"),
                ("input/Экспорт ОГЭ", "ОГЭ"),
                ("input/ОГЭ по информатике", "ОГЭ"),
            ]
            for folder_path, course_type in defaults:
                cursor.execute(
                    "INSERT OR IGNORE INTO folder_course_mapping (folder_path, course_type) VALUES (?, ?)",
                    (folder_path, course_type),
                )
            logger.info("Добавлены маппинги папок по умолчанию")
        # Новые папки добавляются только через CLI: python main.py folders set <путь> <курс>
        conn.commit()
        conn.close()
    
    def add_video(self, record: VideoRecord) -> int:
        """Добавить видео в хранилище.
        
        Args:
            record: Запись о видео.
            
        Returns:
            ID добавленной записи.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO videos (
                    file_path, file_hash, title, description, channel,
                    source_folder, date, uploaded, upload_date,
                    video_url, post_url, error_message, skip_upload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.file_path,
                record.file_hash,
                record.title,
                record.description,
                record.channel,
                record.source_folder,
                record.date.isoformat() if record.date else None,
                1 if record.uploaded else 0,
                record.upload_date.isoformat() if record.upload_date else None,
                record.video_url,
                record.post_url,
                record.error_message,
                1 if record.skip_upload else 0,
            ))
            
            record_id = cursor.lastrowid
            conn.commit()
            logger.debug(f"Добавлено видео в БД: {record.file_path} (ID: {record_id})")
            return record_id
            
        except sqlite3.IntegrityError:
            # Видео уже существует, обновляем
            logger.debug(f"Видео уже существует, обновляем: {record.file_path}")
            cursor.execute("""
                UPDATE videos SET
                    file_hash = ?,
                    title = ?,
                    description = ?,
                    channel = ?,
                    source_folder = ?,
                    date = ?
                WHERE file_path = ?
            """, (
                record.file_hash,
                record.title,
                record.description,
                record.channel,
                record.source_folder,
                record.date.isoformat() if record.date else None,
                record.file_path,
            ))
            conn.commit()
            
            # Получаем ID существующей записи
            cursor.execute("SELECT id FROM videos WHERE file_path = ?", (record.file_path,))
            record_id = cursor.fetchone()[0]
            return record_id
            
        finally:
            conn.close()
    
    def get_video(self, video_id: int) -> Optional[VideoRecord]:
        """Получить видео по ID.
        
        Args:
            video_id: ID видео.
            
        Returns:
            Запись о видео или None.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return self._row_to_record(row)

    def get_previous_in_folder(self, video_id: int) -> Optional[VideoRecord]:
        """Предыдущая запись в той же папке источника (по id). Для копирования описания при многоприкреплениях."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT v2.* FROM videos v1
            JOIN videos v2 ON v1.source_folder = v2.source_folder AND v2.id < v1.id
            WHERE v1.id = ?
            ORDER BY v2.id DESC LIMIT 1
        """, (video_id,))
        row = cursor.fetchone()
        conn.close()
        return self._row_to_record(row) if row else None

    def update_description(self, video_id: int, description: str) -> None:
        """Обновить только описание записи по id."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE videos SET description = ? WHERE id = ?", (description, video_id))
        conn.commit()
        conn.close()
        logger.debug(f"Обновлено описание для видео id={video_id}")
    
    def get_next_unuploaded(self, channel: Optional[str] = None, source_folder: Optional[str] = None) -> Optional[VideoRecord]:
        """Получить следующее не загруженное видео.
        
        Args:
            channel: Фильтр по каналу (опционально).
            source_folder: Фильтр по папке источника (опционально).
            
        Returns:
            Запись о следующем видео или None.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM videos WHERE uploaded = 0 AND (skip_upload IS NULL OR skip_upload = 0)"
        params = []
        
        if channel:
            query += " AND channel = ?"
            params.append(channel)
        
        if source_folder:
            query += " AND source_folder = ?"
            params.append(source_folder)
        
        query += " ORDER BY id LIMIT 1"
        
        cursor.execute(query, params)
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return self._row_to_record(row)
    
    def mark_uploaded(self, video_id: int, video_url: str, post_url: Optional[str] = None, error: Optional[str] = None):
        """Отметить видео как загруженное.
        
        Args:
            video_id: ID видео.
            video_url: URL загруженного видео.
            post_url: URL поста на стене (опционально).
            error: Сообщение об ошибке (если была ошибка).
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if error:
            cursor.execute("""
                UPDATE videos SET
                    error_message = ?,
                    upload_date = ?
                WHERE id = ?
            """, (error, datetime.now().isoformat(), video_id))
        else:
            cursor.execute("""
                UPDATE videos SET
                    uploaded = 1,
                    upload_date = ?,
                    video_url = ?,
                    post_url = ?,
                    error_message = NULL
                WHERE id = ?
            """, (datetime.now().isoformat(), video_url, post_url, video_id))
        
        conn.commit()
        conn.close()
        logger.debug(f"Видео {video_id} отмечено как загруженное")

    def clear_upload_state(self, video_id: int) -> bool:
        """Сбросить данные загрузки у записи (uploaded=0, video_url/post_url/error_message=NULL)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE videos SET
                uploaded = 0,
                upload_date = NULL,
                video_url = NULL,
                post_url = NULL,
                error_message = NULL
            WHERE id = ?
        """, (video_id,))
        n = cursor.rowcount
        conn.commit()
        conn.close()
        return n > 0

    def get_skipped_with_video_url(self) -> List[VideoRecord]:
        """Записи с skip_upload=1 и заполненным video_url (для удаления этих роликов из VK)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM videos WHERE skip_upload = 1 AND video_url IS NOT NULL AND video_url != ''"
        )
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_record(row) for row in rows]

    def get_record_by_video_url(self, video_url: str) -> Optional[VideoRecord]:
        """Найти запись по video_url (для сброса данных после удаления в VK)."""
        if not video_url or not video_url.strip():
            return None
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM videos WHERE video_url = ? LIMIT 1", (video_url.strip(),))
        row = cursor.fetchone()
        conn.close()
        return self._row_to_record(row) if row else None

    def clear_upload_state_for_skipped(self) -> int:
        """Сбросить данные загрузки у всех записей с skip_upload=1. Возвращает количество обновлённых.
        Внимание: используйте только если ролики с skip не загружались в VK или уже удалены (delete-skipped-from-vk)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE videos SET
                uploaded = 0,
                upload_date = NULL,
                video_url = NULL,
                post_url = NULL,
                error_message = NULL
            WHERE skip_upload = 1
        """)
        n = cursor.rowcount
        conn.commit()
        conn.close()
        logger.info(f"Сброшены данные загрузки у {n} записей с skip_upload=1")
        return n

    def get_videos_range(self, start_id: int, count: Optional[int] = None, 
                         channel: Optional[str] = None, source_folder: Optional[str] = None) -> List[VideoRecord]:
        """Получить диапазон видео.
        
        Args:
            start_id: Начальный ID.
            count: Количество видео (None = все до конца).
            channel: Фильтр по каналу (опционально).
            source_folder: Фильтр по папке источника (опционально).
            
        Returns:
            Список записей о видео.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM videos WHERE id >= ? AND (skip_upload IS NULL OR skip_upload = 0)"
        params = [start_id]
        
        if channel:
            query += " AND channel = ?"
            params.append(channel)
        
        if source_folder:
            query += " AND source_folder = ?"
            params.append(source_folder)
        
        query += " ORDER BY id"
        
        if count:
            query += f" LIMIT {count}"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_record(row) for row in rows]
    
    def get_videos_by_ids(self, video_ids: List[int]) -> List[VideoRecord]:
        """Получить записи по списку ID (сохраняя порядок ID).
        
        Args:
            video_ids: Список id видео.
            
        Returns:
            Список записей (отсутствующие ID пропускаются).
        """
        if not video_ids:
            return []
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(video_ids))
        cursor.execute(f"SELECT * FROM videos WHERE id IN ({placeholders})", video_ids)
        rows = cursor.fetchall()
        conn.close()
        by_id = {row["id"]: self._row_to_record(row) for row in rows}
        return [by_id[i] for i in video_ids if i in by_id]
    
    def get_all_unuploaded(self, channel: Optional[str] = None, source_folder: Optional[str] = None) -> List[VideoRecord]:
        """Получить все не загруженные видео.
        
        Args:
            channel: Фильтр по каналу (опционально).
            source_folder: Фильтр по папке источника (опционально).
            
        Returns:
            Список записей о видео.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM videos WHERE uploaded = 0 AND (skip_upload IS NULL OR skip_upload = 0)"
        params = []
        
        if channel:
            query += " AND channel = ?"
            params.append(channel)
        
        if source_folder:
            query += " AND source_folder = ?"
            params.append(source_folder)
        
        query += " ORDER BY id"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_record(row) for row in rows]
    
    def set_skip_upload(self, ids: Optional[List[int]] = None, filenames: Optional[List[str]] = None, skip: bool = True) -> int:
        """Пометить видео для пропуска загрузки (или снять пометку).
        
        Args:
            ids: Список ID записей.
            filenames: Список имён файлов или путей; совпадение по окончанию file_path.
            skip: True — пометить пропуск, False — снять пометку.
            
        Returns:
            Количество обновлённых записей.
        """
        if not ids and not filenames:
            return 0
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        updated = 0
        val = 1 if skip else 0
        if ids:
            placeholders = ",".join("?" * len(ids))
            cursor.execute(
                f"UPDATE videos SET skip_upload = ? WHERE id IN ({placeholders})",
                [val] + list(ids),
            )
            updated += cursor.rowcount
        if filenames:
            for name in filenames:
                name_esc = name.replace("\\", "/").strip()
                if not name_esc:
                    continue
                # Совпадение: file_path заканчивается на /name или \name или равен name
                cursor.execute(
                    "UPDATE videos SET skip_upload = ? WHERE file_path = ? OR file_path LIKE ? OR file_path LIKE ?",
                    (val, name_esc, f"%/{name_esc}", f"%\\{name_esc}"),
                )
                updated += cursor.rowcount
        conn.commit()
        conn.close()
        logger.debug(f"Пометка skip_upload={skip}: обновлено записей {updated}")
        return updated
    
    def find_by_hash(self, file_hash: str) -> Optional[VideoRecord]:
        """Найти видео по хешу файла (для определения дубликатов).
        
        Args:
            file_hash: Хеш файла.
            
        Returns:
            Запись о видео или None.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM videos WHERE file_hash = ? LIMIT 1", (file_hash,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return self._row_to_record(row)
    
    def get_statistics(self) -> dict:
        """Получить статистику по видео.
        
        Returns:
            Словарь со статистикой.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM videos")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM videos WHERE uploaded = 1")
        uploaded = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM videos WHERE uploaded = 0")
        not_uploaded = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM videos WHERE (skip_upload IS NULL OR skip_upload = 0) AND uploaded = 0")
        not_uploaded_candidates = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM videos WHERE skip_upload = 1")
        skipped = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT channel) FROM videos WHERE channel IS NOT NULL")
        channels = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT source_folder) FROM videos")
        folders = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total": total,
            "uploaded": uploaded,
            "not_uploaded": not_uploaded,
            "not_uploaded_candidates": not_uploaded_candidates,
            "skipped": skipped,
            "channels": channels,
            "source_folders": folders,
        }
    
    # --- Маппинг папка -> тип курса (COURSE_TYPES из config.registry) ---
    
    VALID_COURSE_TYPES = COURSE_TYPES

    def set_folder_course(self, folder_path: str, course_type: str) -> None:
        """Установить тип курса для папки.
        
        Args:
            folder_path: Путь к папке (нормализованный, например input/Экспорты ЕГЭ).
            course_type: Тип курса: Python, ЕГЭ, ОГЭ.
        """
        if course_type not in self.VALID_COURSE_TYPES:
            raise ValueError(f"Тип курса должен быть один из: {self.VALID_COURSE_TYPES}")
        folder_path = str(Path(folder_path)).replace("\\", "/")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO folder_course_mapping (folder_path, course_type)
            VALUES (?, ?)
            ON CONFLICT(folder_path) DO UPDATE SET course_type = excluded.course_type
            """,
            (folder_path, course_type),
        )
        conn.commit()
        conn.close()
        logger.debug(f"Маппинг: {folder_path} -> {course_type}")
    
    def get_course_for_folder(self, folder_path: str) -> Optional[str]:
        """Получить тип курса для папки.
        
        Ищет запись, где folder_path является префиксом переданного пути
        (или совпадает). Если несколько подходят — возвращается наиболее
        длинное совпадение.
        
        Args:
            folder_path: Путь к папке экспорта.
            
        Returns:
            Тип курса (Python, ЕГЭ, ОГЭ) или None.
        """
        folder_path = str(Path(folder_path)).replace("\\", "/")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT folder_path, course_type FROM folder_course_mapping ORDER BY LENGTH(folder_path) DESC"
        )
        rows = cursor.fetchall()
        conn.close()
        norm = folder_path
        for stored_path, course_type in rows:
            s = stored_path.replace("\\", "/")
            if norm == s:
                return course_type
            if len(norm) > len(s) and norm.startswith(s):
                # Папка/подпапка (path/...) или каталог выгрузки TG Parser (path__YYYY-MM-DD_HH-mm)
                if norm[len(s)] in "/_":
                    return course_type
        return None
    
    def list_folder_mappings(self) -> List[tuple]:
        """Список всех маппингов папка -> тип курса.
        
        Returns:
            Список пар (folder_path, course_type).
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT folder_path, course_type FROM folder_course_mapping ORDER BY folder_path"
        )
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    def delete_folder_mapping(self, folder_path: str) -> bool:
        """Удалить маппинг для папки.
        
        Returns:
            True если запись была удалена.
        """
        folder_path = str(Path(folder_path)).replace("\\", "/")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM folder_course_mapping WHERE folder_path = ?", (folder_path,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted
    
    def _row_to_record(self, row: sqlite3.Row) -> VideoRecord:
        """Преобразовать строку БД в VideoRecord."""
        return VideoRecord(
            id=row["id"],
            file_path=row["file_path"],
            file_hash=row["file_hash"],
            title=row["title"],
            description=row["description"] or "",
            channel=row["channel"],
            source_folder=row["source_folder"],
            date=datetime.fromisoformat(row["date"]) if row["date"] else None,
            uploaded=bool(row["uploaded"]),
            upload_date=datetime.fromisoformat(row["upload_date"]) if row["upload_date"] else None,
            video_url=row["video_url"],
            post_url=row["post_url"],
            error_message=row["error_message"],
            skip_upload=bool(row["skip_upload"]) if "skip_upload" in row.keys() else False,
        )
