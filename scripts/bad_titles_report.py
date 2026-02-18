# -*- coding: utf-8 -*-
"""Сбор заголовков с некорректно сформированным именем для анализа и правки генератора.

Использование:
  python scripts/bad_titles_report.py [channel] [--limit N] [--offset K]

По умолчанию: channel=Алгоритмы, limit=10, offset=0.
Плохой заголовок: совпадает с именем файла (stem), или префикс "Курс по Python базовый." + stem,
или содержит типичный шаблон сырого имени (запись, Телемост, много подчёркиваний).
"""

import argparse
import re
import sys
from pathlib import Path

# проект в пути
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3
from src.storage.database import VideoStorage


def get_videos_by_channel_or_path(storage: VideoStorage, channel: str = None, path_substring: str = None):
    """Получить записи по каналу или по подстроке в file_path (для обхода проблем кодировки)."""
    conn = sqlite3.connect(str(storage.db_path))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if path_substring:
        c.execute("SELECT * FROM videos WHERE file_path LIKE ? ORDER BY id", (f"%{path_substring}%",))
    else:
        c.execute("SELECT * FROM videos WHERE channel = ? ORDER BY id", (channel,))
    rows = c.fetchall()
    conn.close()
    try:
        return [storage._row_to_record(row) for row in rows]
    except Exception as e:
        import traceback
        traceback.print_exc()
        return []


def is_bad_title(title: str, file_path: str) -> bool:
    """Заголовок считается плохим, если это fallback (имя файла) или сырое имя."""
    if not title or not title.strip():
        return True
    stem = Path(file_path).stem
    # Точное совпадение со stem
    if title.strip() == stem:
        return True
    # Префикс курса Python + stem (fallback генератора)
    prefix = "Курс по Python базовый. "
    if title.startswith(prefix) and title[len(prefix):].strip() == stem:
        return True
    # Сырое имя в заголовке: много подчёркиваний, "запись", "Телемост"
    if re.search(r"_\d{2}_\d{2}_\d{2}_", title) or "запись" in title.lower() or "телемост" in title.lower():
        return True
    # Короткий fallback "Курс по Python базовый. <что-то похожее на stem>"
    if title.startswith(prefix):
        rest = title[len(prefix):].strip()
        if rest and len(rest) > 20 and "_" in rest and re.search(r"\d{2}_\d{2}_\d{2}", rest):
            return True
    return False


def main():
    ap = argparse.ArgumentParser(description="Отчёт по плохим заголовкам")
    ap.add_argument("channel", nargs="?", default="Алгоритмы", help="Канал (тип курса)")
    ap.add_argument("--limit", type=int, default=10, help="Сколько вывести")
    ap.add_argument("--offset", type=int, default=0, help="Смещение")
    ap.add_argument("--count-only", action="store_true", help="Только вывести количество плохих")
    args = ap.parse_args()

    # Путь к БД относительно корня проекта (скрипт может вызываться из любой папки)
    project_root = Path(__file__).resolve().parent.parent
    db_path = project_root / "videos.db"
    if not db_path.exists():
        print("БД не найдена:", db_path)
        return
    storage = VideoStorage(db_path)
    # Для канала «Алгоритмы» берём записи по подстроке пути (надёжно при любой кодировке CLI)
    use_path_substring = (
        args.channel == "Алгоритмы"
        or (args.channel or "").lower() in ("algorithms", "алгоритмы")
        or "algorithm" in (args.channel or "").lower()
    )
    if use_path_substring:
        all_records = get_videos_by_channel_or_path(storage, path_substring="AlgorithmPythonStruct")
    else:
        all_records = get_videos_by_channel_or_path(storage, channel=args.channel)
    # Если по channel ничего не нашли — для известных каналов пробуем по пути
    if not all_records and not use_path_substring:
        all_records = get_videos_by_channel_or_path(storage, path_substring="AlgorithmPythonStruct")
    bad = [(r.id, r.title, r.description or "", r.file_path) for r in all_records if is_bad_title(r.title or "", r.file_path)]

    if args.count_only:
        print(len(bad))
        return
    if not all_records:
        print("Записей по каналу/пути не найдено.")
        return
    if not bad and all_records:
        print("Плохих не найдено (всего записей: %d)." % len(all_records))
        return

    subset = bad[args.offset : args.offset + args.limit]
    print(f"Плохих заголовков всего: {len(bad)} (показано {len(subset)} с offset={args.offset})")
    print("-" * 80)
    for i, (vid, title, desc, fp) in enumerate(subset, 1):
        stem = Path(fp).stem
        first_line = (desc.split("\n")[0] if desc else "")[:120]
        print(f"{i}. id={vid} | stem={stem[:50]}...")
        print(f"   title: {title[:80]}")
        print(f"   desc:  {first_line}")
        print()
    return len(bad)


if __name__ == "__main__":
    main()
