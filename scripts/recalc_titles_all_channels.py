# -*- coding: utf-8 -*-
"""Пересчёт заголовков по всем каналам (ЕГЭ, Python, ОГЭ), сбор затронутых ID и статистика.

Запуск: python scripts/recalc_titles_all_channels.py

Результат: logs/titles_recalc_all.csv (id, channel, old_title, new_title),
           краткая статистика в консоль.
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.storage.database import VideoStorage, VideoRecord
from src.title_generators.ege_generators import EGEAutoTitleGenerator
from src.title_generators.python_generators import PythonAutoTitleGenerator
from src.title_generators.oge_generators import OGEAutoTitleGenerator
from src.models.video import VideoData


def record_to_video_data(r: VideoRecord) -> VideoData:
    return VideoData(
        file_path=Path(r.file_path),
        title=r.title or "",
        description=r.description or "",
        date=r.date,
        channel=r.channel,
    )


def main():
    project_root = Path(__file__).resolve().parent.parent
    db_path = project_root / "videos.db"
    storage = VideoStorage(db_path)

    generators = {
        "ЕГЭ": EGEAutoTitleGenerator(),
        "Python": PythonAutoTitleGenerator(),
        "ОГЭ": OGEAutoTitleGenerator(),
    }

    def normalize_channel(ch: str) -> str:
        if not ch:
            return ""
        ch = ch.strip()
        if ch == "Python" or "python" in ch.lower():
            return "Python"
        if ch == "ЕГЭ" or "егэ" in ch.lower() or ch == "ege":
            return "ЕГЭ"
        if ch == "ОГЭ" or "огэ" in ch.lower() or "оге" in ch.lower():
            return "ОГЭ"
        return ch

    all_records = storage.get_videos_range(0, 100000)
    changed = []
    skipped = 0
    by_channel = {}

    for r in all_records:
        ch = normalize_channel(r.channel or "")
        if ch not in generators:
            continue
        try:
            v = record_to_video_data(r)
        except ValueError:
            skipped += 1
            continue
        gen = generators[ch]
        new_title = gen.generate(v)
        old_title = r.title or ""
        if old_title != new_title:
            changed.append({
                "id": r.id,
                "channel": ch,
                "old_title": old_title,
                "new_title": new_title,
            })
            by_channel[ch] = by_channel.get(ch, 0) + 1

    # Статистика
    total_processed = sum(
        1 for r in all_records
        if normalize_channel(r.channel or "") in generators
    )
    total_changed = len(changed)
    affected_ids = sorted({c["id"] for c in changed})

    print("Пересчёт заголовков (тема/задание, короткие темы — первые 2 предложения)")
    print("Каналы: ЕГЭ, Python, ОГЭ")
    print("-" * 60)
    print(f"Обработано записей (с учётом канала): {total_processed}")
    print(f"Пропущено (файл не найден): {skipped}")
    print(f"Изменено заголовков: {total_changed}")
    print("По каналам:", by_channel)
    print(f"Затронутые ID (всего {len(affected_ids)}):", affected_ids[:50], end="")
    if len(affected_ids) > 50:
        print(" ...")
    else:
        print()

    out_dir = project_root / "logs"
    out_dir.mkdir(exist_ok=True)
    out_csv = out_dir / "titles_recalc_all.csv"
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "channel", "old_title", "new_title"])
        for row in changed:
            w.writerow([row["id"], row["channel"], row["old_title"], row["new_title"]])
    print(f"\nСохранено: {out_csv}")

    ids_file = out_dir / "titles_recalc_affected_ids.txt"
    with open(ids_file, "w", encoding="utf-8") as f:
        f.write(",".join(map(str, affected_ids)))
    print(f"Список ID: {ids_file}")

    summary_file = out_dir / "titles_recalc_summary.txt"
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write("Пересчёт заголовков: тема/задание, короткие темы — первые 2 предложения, источники (КЕГЭ и др.)\n")
        f.write(f"Обработано записей: {total_processed}\n")
        f.write(f"Изменено заголовков: {total_changed}\n")
        f.write(f"По каналам: ЕГЭ {by_channel.get('ЕГЭ', 0)}, Python {by_channel.get('Python', 0)}, ОГЭ {by_channel.get('ОГЭ', 0)}\n")
        f.write(f"Затронутые ID: {len(affected_ids)}\n")
    print(f"Сводка: {summary_file}")


if __name__ == "__main__":
    main()
