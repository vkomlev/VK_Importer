"""Экспорт базы данных видео в Excel файл."""

import sys
import io
from pathlib import Path
from datetime import datetime

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    import pandas as pd
except ImportError:
    print("Установка pandas и openpyxl...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas", "openpyxl"])
    import pandas as pd

from src.storage.database import VideoStorage

def export_to_xlsx(db_path: Path = Path("videos.db"), output_path: Path = None):
    """Экспортировать базу данных в Excel файл.
    
    Args:
        db_path: Путь к файлу базы данных.
        output_path: Путь к выходному Excel файлу (если None, используется videos_export.xlsx).
    """
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(f"videos_export_{timestamp}.xlsx")
    
    storage = VideoStorage(db_path)
    
    # Подключаемся к БД напрямую для чтения всех записей
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Читаем все записи
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM videos ORDER BY id")
    rows = cursor.fetchall()
    
    if not rows:
        print("База данных пуста")
        conn.close()
        return
    
    # Преобразуем в список словарей
    data = []
    for row in rows:
        data.append({
            "ID": row["id"],
            "Путь к файлу": row["file_path"],
            "Хеш файла": row["file_hash"] or "",
            "Заголовок": row["title"],
            "Описание": (row["description"] or "")[:500],  # Ограничиваем длину описания
            "Канал": row["channel"] or "",
            "Папка источника": row["source_folder"],
            "Дата видео": row["date"] or "",
            "Загружено": "Да" if row["uploaded"] else "Нет",
            "Дата загрузки": row["upload_date"] or "",
            "URL видео": row["video_url"] or "",
            "URL поста": row["post_url"] or "",
            "Ошибка": row["error_message"] or "",
            "Создано": row["created_at"] or "",
        })
    
    conn.close()
    
    # Создаем DataFrame
    df = pd.DataFrame(data)
    
    # Экспортируем в Excel
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Видео", index=False)
        
        # Настраиваем ширину колонок
        worksheet = writer.sheets["Видео"]
        column_widths = {
            "A": 8,   # ID
            "B": 50,  # Путь к файлу
            "C": 20,  # Хеш файла
            "D": 60,  # Заголовок
            "E": 50,  # Описание
            "F": 10,  # Канал
            "G": 40,  # Папка источника
            "H": 20,  # Дата видео
            "I": 10,  # Загружено
            "J": 20,  # Дата загрузки
            "K": 50,  # URL видео
            "L": 50,  # URL поста
            "M": 50,  # Ошибка
            "N": 20,  # Создано
        }
        
        for col, width in column_widths.items():
            worksheet.column_dimensions[col].width = width
        
        # Замораживаем первую строку (заголовки)
        worksheet.freeze_panes = "A2"
    
    print(f"Экспортировано {len(data)} записей в {output_path}")
    
    # Показываем статистику
    stats = storage.get_statistics()
    print(f"\nСтатистика:")
    print(f"  Всего видео: {stats['total']}")
    print(f"  Загружено: {stats['uploaded']}")
    print(f"  Не загружено: {stats['not_uploaded']}")
    print(f"  Каналов: {stats['channels']}")
    print(f"  Папок источников: {stats['source_folders']}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Экспорт базы данных видео в Excel")
    parser.add_argument("--db", default="videos.db", help="Путь к файлу базы данных")
    parser.add_argument("--output", "-o", help="Путь к выходному Excel файлу")
    
    args = parser.parse_args()
    
    export_to_xlsx(Path(args.db), Path(args.output) if args.output else None)
