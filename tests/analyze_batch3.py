"""Анализ следующих 10 проблемных строк (21-30)."""

import sys
from pathlib import Path
import csv
import io

# Настройка кодировки для Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.title_generators.ege_generators import EGEAutoTitleGenerator
from src.title_generators.python_generators import PythonAutoTitleGenerator
from src.models.video import VideoData

# Читаем проблемные строки (из папки tests)
problematic_file = Path(__file__).parent / "problematic_titles.csv"
with open(problematic_file, "r", encoding="utf-8-sig") as f:
    reader = csv.reader(f, delimiter=";")
    rows = list(reader)

# Берем строки 21-30
test_cases = rows[21:31]

ege_generator = EGEAutoTitleGenerator()
python_generator = PythonAutoTitleGenerator()

print("Анализ следующих 10 проблемных строк (21-30):")
print("=" * 80)

for i, (row_num, channel, first_line, filename, old_title) in enumerate(test_cases, 21):
    # Создаем временный файл для тестирования
    test_file = Path("test") / filename
    test_file.parent.mkdir(exist_ok=True)
    test_file.touch()
    
    try:
        # Выбираем генератор
        generator = ege_generator if channel == "ЕГЭ" else python_generator
        
        # Создаем VideoData для тестирования
        video = VideoData(
            file_path=test_file,
            title="",
            description=first_line,
            date=None
        )
        video.channel = channel
        
        # Генерируем новый заголовок
        new_title = generator.generate(video)
        
        print(f"\n{i}. Строка {row_num}")
        print(f"   Канал: {channel}")
        print(f"   Первая строка: {first_line[:80] if first_line else '(пусто)'}...")
        print(f"   Файл: {filename}")
        print(f"   Старый заголовок: {old_title}")
        print(f"   Новый заголовок: {new_title}")
        
        # Проверяем, исправлено ли
        filename_stem = Path(filename).stem
        is_fixed = "Разбираем" in new_title or "Курс" in new_title
        if filename_stem in new_title and "Разбираем" not in new_title:
            is_fixed = False
        
        print(f"   Исправлено: {'✓' if is_fixed else '✗'}")
        if not is_fixed:
            print(f"   ПРОБЛЕМА: В заголовке все еще есть имя файла или нет 'Разбираем'")
    finally:
        # Удаляем временный файл
        if test_file.exists():
            test_file.unlink()
