"""Анализ проблемных заголовков ОГЭ (где в заголовке есть имя файла)."""

import sys
import io
import csv
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

mapping_file = Path(__file__).parent / "title_mapping.csv"
with open(mapping_file, "r", encoding="utf-8-sig") as f:
    reader = csv.reader(f, delimiter=";")
    rows = list(reader)

problematic = []
for i, row in enumerate(rows[1:], start=2):
    if len(row) < 4:
        continue
    channel, first_line, filename, title = row[0], row[1], row[2], row[3]
    if channel != "ОГЭ":
        continue
    filename_stem = Path(filename).stem
    if filename_stem in title and "Разбираем" not in title:
        problematic.append((i, channel, first_line, filename, title))

print(f"ОГЭ: найдено проблемных строк: {len(problematic)}\n")
print("=" * 80)
print("ПЕРВЫЕ 10 ПРОБЛЕМНЫХ СТРОК ОГЭ")
print("=" * 80)

for i, (row_num, channel, first_line, filename, title) in enumerate(problematic[:10], 1):
    print(f"\n{i}. Строка {row_num}")
    print(f"   Первая строка: {(first_line[:100] + '...') if len(first_line) > 100 else first_line}")
    print(f"   Файл: {filename}")
    print(f"   Текущий заголовок: {title}")

out_file = Path(__file__).parent / "problematic_titles_oge.csv"
with open(out_file, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["Номер строки", "Канал", "Первая строка", "Имя файла", "Текущий заголовок"])
    for r in problematic:
        w.writerow(r)

print(f"\nВсе проблемные ОГЭ сохранены в: {out_file}")
print(f"Всего: {len(problematic)}")
