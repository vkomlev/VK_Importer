"""Тестирование исправлений для первых 10 проблемных строк."""

import sys
from pathlib import Path
import csv
import io

# Настройка кодировки для Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.title_generators.ege_generators import EGEAutoTitleGenerator
from src.models.video import VideoData
from unittest.mock import patch

# Читаем проблемные строки (из папки tests)
problematic_file = Path(__file__).parent / "problematic_titles.csv"
with open(problematic_file, "r", encoding="utf-8-sig") as f:
    reader = csv.reader(f, delimiter=";")
    rows = list(reader)

# Берем первые 10
test_cases = rows[1:11]  # Пропускаем заголовок

generator = EGEAutoTitleGenerator()

print("Тестирование исправлений для первых 10 проблемных строк:")
print("=" * 80)

for i, (row_num, channel, first_line, filename, old_title) in enumerate(test_cases, 1):
    # Создаем временный файл для тестирования
    test_file = Path("test") / filename
    test_file.parent.mkdir(exist_ok=True)
    test_file.touch()
    
    try:
        # Создаем VideoData для тестирования
        video = VideoData(
            file_path=test_file,
            title="",
            description=first_line,
            date=None
        )
        
        # Генерируем новый заголовок
        new_title = generator.generate(video)
    finally:
        # Удаляем временный файл
        if test_file.exists():
            test_file.unlink()
    
    print(f"\n{i}. Строка {row_num}")
    print(f"   Первая строка: {first_line[:80]}...")
    print(f"   Старый заголовок: {old_title}")
    print(f"   Новый заголовок: {new_title}")
    print(f"   Исправлено: {'✓' if 'Разбираем' in new_title else '✗'}")
