# -*- coding: utf-8 -*-
"""Посмотреть в БД title и description для указанных ID."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.storage.database import VideoStorage

ids = [608, 609, 737, 764]
storage = VideoStorage(Path("videos.db"))
out = []
for vid in ids:
    r = storage.get_video(vid)
    if not r:
        out.append(f"ID {vid}: не найден\n")
        continue
    out.append(f"--- ID {vid} channel={r.channel} ---\n")
    out.append("title: " + repr((r.title or "")[:150]) + "\n")
    out.append("desc: " + repr((r.description or "")[:500]) + "\n\n")
path = Path(__file__).resolve().parent.parent / "logs" / "inspect_ids.txt"
path.parent.mkdir(exist_ok=True)
path.write_text("".join(out), encoding="utf-8")
print("Written", path)
