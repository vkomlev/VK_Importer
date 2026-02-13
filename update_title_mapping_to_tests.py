"""Обновление tests/title_mapping.csv (все каналы: ЕГЭ, Python, ОГЭ)."""

import sys
import io
from pathlib import Path
import csv

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.parsers.html_parser import HTMLParser
from src.parsers.json_parser import JSONParser
from src.title_generators.factory import TitleGeneratorFactory

input_dir = Path("input")
ege_dir = input_dir / "Экпорты ЕГЭ"
python_dir = input_dir / "Экспорт Python"
# Папка ОГЭ: возможные имена
oge_dir = input_dir / "Экспорт ОГЭ"
if not oge_dir.exists():
    oge_dir = input_dir / "ОГЭ по информатике"

all_videos = []


def parse_channel(channel_dir: Path, channel_name: str) -> None:
    if not channel_dir.exists():
        return
    # Корень канала
    for parser_cls in (HTMLParser, JSONParser):
        p = parser_cls(channel_dir)
        if p.detect_format():
            videos = p.parse()
            for v in videos:
                v.channel = channel_name
            all_videos.extend(videos)
            break
    # Подпапки
    for sub in channel_dir.iterdir():
        if not sub.is_dir():
            continue
        for parser_cls in (HTMLParser, JSONParser):
            p = parser_cls(sub)
            if p.detect_format():
                videos = p.parse()
                for v in videos:
                    v.channel = channel_name
                all_videos.extend(videos)
                break


parse_channel(ege_dir, "ЕГЭ")
parse_channel(python_dir, "Python")
parse_channel(oge_dir, "ОГЭ")

ege_gen = TitleGeneratorFactory.create("ege_auto")
python_gen = TitleGeneratorFactory.create("python_auto")
oge_gen = TitleGeneratorFactory.create("oge_auto")

out_path = Path("tests/title_mapping.csv")
out_path.parent.mkdir(parents=True, exist_ok=True)

with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["Канал", "Первая строка сообщения", "Имя файла", "Сформированный заголовок"])
    for video in all_videos:
        if video.channel == "ЕГЭ":
            gen = ege_gen
        elif video.channel == "Python":
            gen = python_gen
        elif video.channel == "ОГЭ":
            gen = oge_gen
        else:
            gen = TitleGeneratorFactory.create("simple")
        title = gen.generate(video) if gen else video.file_path.stem
        first_line = (video.description or "").split("\n")[0].strip()
        w.writerow([video.channel, first_line, video.file_path.name, title])

print(f"Записано {len(all_videos)} записей в {out_path}")
