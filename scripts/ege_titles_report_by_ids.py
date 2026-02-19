# -*- coding: utf-8 -*-
"""Выгрузка заголовков по списку ID для проверки и обновления в VK.

Использование:
  python scripts/ege_titles_report_by_ids.py

Список ID задаётся в переменной IDS ниже (поддержка диапазонов 222-225, 971-1002).
Скрипт загружает записи из БД, пересчитывает заголовок через EGEAutoTitleGenerator,
сравнивает со старым и выводит отчёт + CSV для последующего обновления в VK.
"""

import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.storage.database import VideoStorage, VideoRecord
from src.title_generators.ege_generators import EGEAutoTitleGenerator
from src.models.video import VideoData

# Список ID из запроса пользователя (диапазоны раскрыты)
IDS_RAW = [
    15, 47, 58, 70, 151, 192, 199, 207,
    "222-225", 234, 236, 258, 260, 263, 274, 275, 292, 296, 297, 298, 301, 311,
    323, 325, 326, 327, 330, 336, 341, 350, 351, "369-371", 382, 391, 398, 411,
    426, 429, 433, 436, 441, 460, "478-480", 503, 511, 512, 529, 547, 549, 554,
    556, 557, 560, 594, 608, 609, 737, 764, 816, "971-1002", 1010, "1057-1061", 1079,
]


def expand_ids(ids_raw) -> list:
    out = []
    for x in ids_raw:
        if isinstance(x, int):
            out.append(x)
        elif isinstance(x, str) and "-" in x:
            a, b = x.split("-", 1)
            out.extend(range(int(a.strip()), int(b.strip()) + 1))
        else:
            out.append(int(x))
    return out


def record_to_video_data(r: VideoRecord) -> VideoData:
    p = Path(r.file_path)
    return VideoData(
        file_path=p,
        title=r.title or "",
        description=r.description or "",
        date=r.date,
        channel=r.channel,
    )


def classify_change(old_title: str, new_title: str, desc: str) -> str:
    """Упрощённая классификация типа изменения (метки в ASCII для консоли)."""
    if old_title == new_title:
        return "bez_izmeneniy"
    if "Разбираем задание" in new_title and "Разбираем тему" in old_title:
        return "tema_v_zadanie"
    if "Разбираем тему" in old_title and "Разбираем тему" not in new_title and "Курс ЕГЭ" in new_title:
        return "korotkaya_tema_2_predl"
    if re.search(r"\((Яндекс|Крылов|КЕГЭ|Решу ЕГЭ|Поляков)\)", new_title) and not re.search(r"\((Яндекс|Крылов|КЕГЭ|Решу ЕГЭ|Поляков)\)", old_title):
        return "dobavlen_istochnik"
    return "drugoe"


def main():
    ids = expand_ids(IDS_RAW)
    project_root = Path(__file__).resolve().parent.parent
    db_path = project_root / "videos.db"
    storage = VideoStorage(db_path)
    generator = EGEAutoTitleGenerator()

    records = storage.get_videos_by_ids(ids)
    # Только ЕГЭ
    records = [r for r in records if r.channel and "ЕГЭ" in (r.channel or "")]

    rows = []
    by_type = {}
    skipped = 0
    for r in records:
        try:
            v = record_to_video_data(r)
        except ValueError:
            skipped += 1
            continue
        new_title = generator.generate(v)
        old_title = r.title or ""
        desc_preview = (r.description or "")[:200].replace("\n", " ")
        change_type = classify_change(old_title, new_title, r.description or "")
        by_type[change_type] = by_type.get(change_type, 0) + 1
        rows.append({
            "id": r.id,
            "old_title": old_title,
            "new_title": new_title,
            "change_type": change_type,
            "desc_preview": desc_preview,
        })

    # Отчёт в консоль
    print("Записей по списку ID (ЕГЭ):", len(rows), "(пропущено из-за отсутствия файла:", skipped, ")")
    print("По типам изменений:", by_type)
    print()
    # Детальный отчёт в файл (UTF-8)
    out_txt = project_root / "logs" / "ege_titles_changes_report.txt"
    with open(out_txt, "w", encoding="utf-8") as f:
        for row in rows:
            if row["change_type"] == "bez_izmeneniy":
                continue
            f.write(f"ID {row['id']} [{row['change_type']}]\n")
            f.write(f"  Было:  {row['old_title'][:90]}\n")
            f.write(f"  Стало: {row['new_title'][:90]}\n")
            f.write(f"  Desc:  {row['desc_preview'][:100]}...\n\n")
    if any(r["change_type"] != "bez_izmeneniy" for r in rows):
        print("Детальный отчёт:", out_txt)

    # CSV для обновления в VK (все затронутые: id, old_title, new_title)
    out_csv = project_root / "logs" / "ege_titles_changes.csv"
    out_csv.parent.mkdir(exist_ok=True)
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "old_title", "new_title", "change_type"])
        for row in rows:
            w.writerow([row["id"], row["old_title"], row["new_title"], row["change_type"]])
    print(f"Сохранено: {out_csv}")


if __name__ == "__main__":
    main()
