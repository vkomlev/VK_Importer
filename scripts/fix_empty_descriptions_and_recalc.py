# -*- coding: utf-8 -*-
"""Копирование описания с предыдущей записи в папке (многоприкрепления) и пересчёт заголовков.

ID: 436, 556, 594, 993 и 971–991, 994–1002 — пустое описание, «Запись встречи».

Запуск: python scripts/fix_empty_descriptions_and_recalc.py

Шаги:
1. Для каждого ID с пустым описанием копировать описание с предыдущей записи в том же source_folder.
2. Пересчитать заголовки для этих записей и обновить БД.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.storage.database import VideoStorage, VideoRecord
from src.title_generators.ege_generators import EGEAutoTitleGenerator
from src.title_generators.python_generators import PythonAutoTitleGenerator
from src.title_generators.oge_generators import OGEAutoTitleGenerator
from src.title_generators.algorithms_generators import AlgorithmsAutoTitleGenerator
from src.models.video import VideoData


# Развернуть диапазоны в плоский список ID
IDS_RAW = [436, 556, 594, 993] + list(range(971, 992)) + list(range(994, 1003))
TARGET_IDS = sorted(set(IDS_RAW))


def record_to_video_data(r: VideoRecord) -> VideoData:
    return VideoData(
        file_path=Path(r.file_path),
        title=r.title or "",
        description=r.description or "",
        date=r.date,
        channel=r.channel,
    )


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
    if "алгоритм" in ch.lower():
        return "Алгоритмы"
    return ch


def main():
    project_root = Path(__file__).resolve().parent.parent
    db_path = project_root / "videos.db"
    storage = VideoStorage(db_path)

    generators = {
        "ЕГЭ": EGEAutoTitleGenerator(),
        "Python": PythonAutoTitleGenerator(),
        "ОГЭ": OGEAutoTitleGenerator(),
        "Алгоритмы": AlgorithmsAutoTitleGenerator(),
    }

    # 1) Копирование описания с предыдущей записи в папке
    copied = 0
    skipped_no_record = 0
    skipped_has_desc = 0
    skipped_no_prev = 0
    for vid in TARGET_IDS:
        rec = storage.get_video(vid)
        if not rec:
            skipped_no_record += 1
            continue
        if rec.description and rec.description.strip():
            skipped_has_desc += 1
            continue
        prev = storage.get_previous_in_folder(vid)
        if not prev or not (prev.description and prev.description.strip()):
            skipped_no_prev += 1
            continue
        storage.update_description(vid, prev.description)
        copied += 1
        print(f"  ID {vid}: скопировано описание с ID {prev.id} ({len(prev.description)} символов)")

    print("\nКопирование описания:")
    print(f"  Скопировано: {copied}")
    print(f"  Пропущено (нет записи): {skipped_no_record}")
    print(f"  Пропущено (уже есть описание): {skipped_has_desc}")
    print(f"  Пропущено (нет предыдущей с описанием): {skipped_no_prev}")

    # 2) Пересчёт заголовков и обновление БД
    updated_titles = 0
    for vid in TARGET_IDS:
        rec = storage.get_video(vid)
        if not rec:
            continue
        ch = normalize_channel(rec.channel or "")
        gen = generators.get(ch)
        if not gen:
            continue
        try:
            v = record_to_video_data(rec)
        except ValueError:
            continue
        new_title = gen.generate(v)
        if new_title != (rec.title or ""):
            rec.title = new_title
            storage.add_video(rec)
            updated_titles += 1
            print(f"  ID {vid}: заголовок обновлён -> {new_title[:60]}...")

    print("\nПересчёт заголовков:")
    print(f"  Обновлено записей: {updated_titles}")


if __name__ == "__main__":
    main()
