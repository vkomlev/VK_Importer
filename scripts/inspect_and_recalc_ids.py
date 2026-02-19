# -*- coding: utf-8 -*-
"""Просмотр в БД title/description для указанных ID и пересчёт заголовков."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.storage.database import VideoStorage, VideoRecord
from src.title_generators.ege_generators import EGEAutoTitleGenerator
from src.title_generators.python_generators import PythonAutoTitleGenerator
from src.title_generators.oge_generators import OGEAutoTitleGenerator
from src.title_generators.algorithms_generators import AlgorithmsAutoTitleGenerator
from src.models.video import VideoData


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


IDS = list(range(971, 992)) + list(range(994, 1003))


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

    lines = []
    for vid in IDS:
        r = storage.get_video(vid)
        if not r:
            lines.append(f"ID {vid}: не найден\n\n")
            continue
        lines.append(f"--- ID {vid} channel={r.channel!r} ---\n")
        lines.append("title: " + (r.title or "")[:120] + "\n")
        lines.append("desc (200): " + (r.description or "")[:200] + "\n\n")

    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)
    inspect_path = log_dir / "inspect_971_1002.txt"
    inspect_path.write_text("".join(lines), encoding="utf-8")
    print("Inspect written:", inspect_path)

    # Пересчёт заголовков
    updated = 0
    for vid in IDS:
        rec = storage.get_video(vid)
        if not rec:
            continue
        ch = normalize_channel(rec.channel or "")
        gen = generators.get(ch)
        if not gen:
            print(f"  ID {vid}: канал {ch!r} — генератор не найден")
            continue
        try:
            v = record_to_video_data(rec)
        except ValueError:
            continue
        new_title = gen.generate(v)
        old_title = rec.title or ""
        if new_title != old_title:
            rec.title = new_title
            storage.add_video(rec)
            updated += 1
            print(f"  ID {vid}: {old_title[:50]}... -> {new_title[:60]}...")

    print(f"\nОбновлено заголовков: {updated}")


if __name__ == "__main__":
    main()
