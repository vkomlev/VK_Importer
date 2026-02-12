"""Обновление title_mapping.csv с исправленными генераторами."""

import sys
from pathlib import Path
import csv
import io

# Настройка кодировки для Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.parsers.html_parser import HTMLParser
from src.parsers.json_parser import JSONParser
from src.title_generators.factory import TitleGeneratorFactory

# Пути к экспортам
input_dir = Path("input")
ege_dir = input_dir / "Экпорты ЕГЭ"  # Обратите внимание: одна "п" в "Экпорты"
python_dir = input_dir / "Экспорт Python"

# Собираем все видео
all_videos = []

# Обрабатываем ЕГЭ экспорты
for export_folder in ege_dir.iterdir():
    if not export_folder.is_dir():
        continue
    
    # Определяем формат
    parser = None
    if HTMLParser(export_folder).detect_format():
        parser = HTMLParser(export_folder)
    elif JSONParser(export_folder).detect_format():
        parser = JSONParser(export_folder)
    
    if parser:
        videos = parser.parse()
        for video in videos:
            video.channel = "ЕГЭ"
        all_videos.extend(videos)

# Обрабатываем Python экспорт
if python_dir.exists():
    # Python экспорт может быть в корне папки (result.json) или в подпапках
    # Сначала проверяем корень папки
    parser = None
    if HTMLParser(python_dir).detect_format():
        parser = HTMLParser(python_dir)
    elif JSONParser(python_dir).detect_format():
        parser = JSONParser(python_dir)
    
    if parser:
        videos = parser.parse()
        for video in videos:
            video.channel = "Python"
        all_videos.extend(videos)
    
    # Затем проверяем подпапки
    for export_folder in python_dir.iterdir():
        if not export_folder.is_dir():
            continue
        
        parser = None
        if HTMLParser(export_folder).detect_format():
            parser = HTMLParser(export_folder)
        elif JSONParser(export_folder).detect_format():
            parser = JSONParser(export_folder)
        
        if parser:
            videos = parser.parse()
            for video in videos:
                video.channel = "Python"
            all_videos.extend(videos)

# Генерируем заголовки
ege_generator = TitleGeneratorFactory.create("ege_auto")
python_generator = TitleGeneratorFactory.create("python_auto")

# Записываем результаты
with open("title_mapping.csv", "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f, delimiter=";")
    writer.writerow(["Канал", "Первая строка сообщения", "Имя файла", "Сформированный заголовок"])
    
    for video in all_videos:
        # Определяем генератор по каналу
        if video.channel == "ЕГЭ":
            generator = ege_generator
        else:
            generator = python_generator
        
        # Генерируем заголовок
        title = generator.generate(video)
        
        # Получаем первую строку описания
        first_line = video.description.split('\n')[0].strip() if video.description else ""
        
        writer.writerow([
            video.channel,
            first_line,
            video.file_path.name,
            title
        ])

print(f"Обновлено {len(all_videos)} записей в title_mapping.csv")
