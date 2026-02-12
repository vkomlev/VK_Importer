"""Анализ проблемных заголовков для Python (где есть имя файла)."""

import sys
import csv
from pathlib import Path
import io

# Настройка кодировки для Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Читаем файл (из корня проекта)
mapping_file = Path(__file__).parent.parent / "title_mapping.csv"
with open(mapping_file, "r", encoding="utf-8-sig") as f:
    reader = csv.reader(f, delimiter=";")
    rows = list(reader)

# Находим проблемные строки для Python (где заголовок содержит имя файла)
problematic = []
for i, row in enumerate(rows[1:], start=2):  # Пропускаем заголовок
    if len(row) < 4:
        continue
    channel, first_line, filename, title = row
    if channel != "Python":
        continue
    
    filename_stem = Path(filename).stem
    
    # Проверяем, содержит ли заголовок имя файла
    if filename_stem in title and "Разбираем" not in title:
        problematic.append((i, channel, first_line, filename, title))

print(f"Найдено проблемных строк для Python: {len(problematic)}\n")
print("=" * 80)
print("АНАЛИЗ ПЕРВЫХ 10 ПРОБЛЕМНЫХ СТРОК PYTHON")
print("=" * 80)

for i, (row_num, channel, first_line, filename, title) in enumerate(problematic[:10], 1):
    print(f"\n{i}. Строка {row_num}")
    print(f"   Канал: {channel}")
    print(f"   Первая строка: {first_line[:100] if first_line else '(пусто)'}...")
    print(f"   Файл: {filename}")
    print(f"   Текущий заголовок: {title}")
    print(f"   Проблема: Генератор не распознал паттерн")

# Сохраняем все проблемные строки для дальнейшего анализа
if problematic:
    problematic_file = Path(__file__).parent / "problematic_titles_python.csv"
    with open(problematic_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Номер строки", "Канал", "Первая строка", "Имя файла", "Текущий заголовок"])
        for row_num, channel, first_line, filename, title in problematic:
            writer.writerow([row_num, channel, first_line, filename, title])
    
    print(f"\n\nВсе проблемные строки Python сохранены в: {problematic_file}")
    print(f"Всего проблемных: {len(problematic)}")
else:
    print("\n\n✓ Проблемных строк не найдено!")
