"""Анализ проблемных заголовков (где есть имя файла)."""

import csv
from pathlib import Path

# Читаем файл: tests/title_mapping.csv
mapping_file = Path(__file__).parent / "title_mapping.csv"
with open(mapping_file, "r", encoding="utf-8-sig") as f:
    reader = csv.reader(f, delimiter=";")
    rows = list(reader)

# Находим проблемные строки (где заголовок содержит имя файла)
problematic = []
for i, row in enumerate(rows[1:], start=2):  # Пропускаем заголовок
    channel, first_line, filename, title = row
    filename_stem = Path(filename).stem
    
    # Проверяем, содержит ли заголовок имя файла
    if filename_stem in title and "Разбираем" not in title:
        problematic.append((i, channel, first_line, filename, title))

print(f"Найдено проблемных строк: {len(problematic)}\n")
print("=" * 80)
print("АНАЛИЗ ПЕРВЫХ 10 ПРОБЛЕМНЫХ СТРОК")
print("=" * 80)

for i, (row_num, channel, first_line, filename, title) in enumerate(problematic[:10], 1):
    print(f"\n{i}. Строка {row_num}")
    print(f"   Канал: {channel}")
    print(f"   Первая строка: {first_line[:100]}...")
    print(f"   Файл: {filename}")
    print(f"   Текущий заголовок: {title}")
    print(f"   Проблема: Генератор не распознал паттерн")

# Сохраняем все проблемные строки для дальнейшего анализа
problematic_file = Path(__file__).parent / "problematic_titles.csv"
with open(problematic_file, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f, delimiter=";")
    writer.writerow(["Номер строки", "Канал", "Первая строка", "Имя файла", "Текущий заголовок"])
    for row_num, channel, first_line, filename, title in problematic:
        writer.writerow([row_num, channel, first_line, filename, title])

print(f"\n\nВсе проблемные строки сохранены в: {problematic_file}")
print(f"Всего проблемных: {len(problematic)}")
