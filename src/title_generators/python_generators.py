"""Генераторы заголовков для канала Python."""

import re
from typing import Optional

from .base import BaseTitleGenerator
from ..models.video import VideoData


class PythonTopicTitleGenerator(BaseTitleGenerator):
    """Генератор заголовков для разбора тем Python.
    
    Формат: "Разбираем тему "Название темы""
    """
    
    def generate(self, video: VideoData) -> str:
        """Сгенерировать заголовок для темы.
        
        Args:
            video: Данные видео.
            
        Returns:
            Заголовок в формате "Разбираем тему "Название темы"" или имя файла.
        """
        description = video.description.strip()
        if not description:
            return video.file_path.stem
        
        # Извлекаем первую строку
        first_line = description.split('\n')[0].strip()
        first_line_lower = first_line.lower()
        
        # Паттерны для тем
        patterns = [
            r'урок\.\s*(.+?)(?:\.|$)',
            r'видеоурок\.\s*(.+?)(?:\.|$)',
            r'мини-урок\s+по\s+(.+?)(?:\.|$)',  # "Мини-урок по созданию строк"
            r'мини-урок\s+по\s+работе\s+с\s+(.+?)(?:\.|$)',  # "Мини-урок по работе с срезами"
            r'тема\s+["\'](.+?)["\']',
            r'тема\s+(.+?)(?:\.|$)',
        ]
        
        # Специальная обработка для "Мини-урок по X в Python" - берем всю фразу до "в Python"
        mini_urok_match = re.search(r'мини-урок\s+по\s+(.+?)(?:\s+в\s+python|\.|$)', first_line, re.IGNORECASE)
        if mini_urok_match:
            topic = mini_urok_match.group(1).strip()
            # Если есть "работе с", добавляем его
            if 'работе с' in first_line_lower:
                topic = 'работе с ' + topic
            if topic and len(topic) > 2:
                return f'Курс по Python базовый. Разбираем тему "{topic}"'
        
        for pattern in patterns:
            match = re.search(pattern, first_line, re.IGNORECASE)
            if match:
                topic = match.group(1).strip()
                # Убираем "в Python" из конца, если есть
                topic = re.sub(r'\s+в\s+python\s*$', '', topic, flags=re.IGNORECASE)
                if topic and len(topic) > 2:
                    return f'Курс по Python базовый. Разбираем тему "{topic}"'
        
        # Специальная обработка для "X. Как работает..." или "X. Что делает..."
        numbered_topic_match = re.search(r'^\d+\.\s+(как\s+работает\s+.+?|что\s+делает\s+.+?)(?:\.|$)', first_line, re.IGNORECASE)
        if numbered_topic_match:
            topic = numbered_topic_match.group(1).strip()
            # Убираем "в Python" из конца
            topic = re.sub(r'\s+в\s+python\s*$', '', topic, flags=re.IGNORECASE)
            if topic and len(topic) > 5:
                return f'Курс по Python базовый. Разбираем тему "{topic}"'
        
        # Если паттерны не сработали, но текст похож на тему (нет номера задания)
        # Проверяем, что это не задание
        if not re.search(r'задание\s+\d+|задани[ея]\s+\d+', first_line_lower):
            # Берем первую строку до точки как тему
            topic = first_line.split('.')[0].strip()
            # Убираем "в Python" из конца
            topic = re.sub(r'\s+в\s+python\s*$', '', topic, flags=re.IGNORECASE)
            # Убираем "на Python" из конца
            topic = re.sub(r'\s+на\s+python\s*$', '', topic, flags=re.IGNORECASE)
            # Убираем "под Windows" и подобные фразы из конца
            topic = re.sub(r'\s+под\s+\w+\s*$', '', topic, flags=re.IGNORECASE)
            
            # Если тема очень короткая (1-2 слова), но это известная тема
            if len(topic) <= 10 and topic.lower() in ['циклы', 'ооп', 'числа', 'строки', 'списки']:
                return f'Курс по Python базовый. Разбираем тему "{topic}"'
            
            if topic and len(topic) > 3:  # Уменьшил минимальную длину до 3
                return f'Курс по Python базовый. Разбираем тему "{topic}"'
        
        return f"Курс по Python базовый. {video.file_path.stem}"
    
    def get_name(self) -> str:
        """Получить имя генератора."""
        return "python_topic"


class PythonTaskTitleGenerator(BaseTitleGenerator):
    """Генератор заголовков для разбора заданий Python.
    
    Формат: "Разбираем задание по теме "Название темы" номер X"
    или "Разбираем задание номер X" (если тема не найдена)
    """
    
    def generate(self, video: VideoData) -> str:
        """Сгенерировать заголовок для задания.
        
        Args:
            video: Данные видео.
            
        Returns:
            Заголовок в формате "Разбираем задание по теме "X" номер Y" или имя файла.
        """
        description = video.description.strip()
        if not description:
            return video.file_path.stem
        
        # Извлекаем первую строку
        first_line = description.split('\n')[0].strip()
        
        # Извлекаем номер задания
        task_number = None
        patterns = [
            r'задание\s+[№#]?\s*(\d+)',
            r'задани[ея]\s+(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, first_line, re.IGNORECASE)
            if match:
                task_number = int(match.group(1))
                break
        
        if not task_number:
            return video.file_path.stem
        
        # Извлекаем тему
        topic = None
        topic_patterns = [
            r'по\s+теме\s+["\'](.+?)["\']',
            r'тема\s+["\'](.+?)["\']',
            r'тема\s+(.+?)(?:\.|$)',
            r'\(тема\s+["\'](.+?)["\']\)',
            r'\(тема\s+(.+?)\)',
        ]
        
        for pattern in topic_patterns:
            match = re.search(pattern, first_line, re.IGNORECASE)
            if match:
                topic = match.group(1).strip()
                # Убираем лишние пробелы и кавычки
                topic = topic.strip('"\'')
                if topic and len(topic) > 2:
                    break
        
        # Если тема не найдена, пробуем найти в тексте описания
        if not topic:
            # Паттерны для поиска темы в тексте
            topic_patterns_in_text = [
                r'на\s+цикл[ыа]?',
                r'на\s+вложенные\s+цикл[ыа]?',
                r'по\s+теме\s+["\'](.+?)["\']',
                r'\(тема\s+["\'](.+?)["\']\)',
                r'\(тема\s+(.+?)\)',
                r'тема\s+["\'](.+?)["\']',
            ]
            
            for pattern in topic_patterns_in_text:
                match = re.search(pattern, first_line, re.IGNORECASE)
                if match:
                    if match.lastindex:
                        topic = match.group(1).strip().strip('"\'')
                    else:
                        # Для паттернов без группы извлекаем контекст
                        if 'цикл' in pattern:
                            topic = "Циклы"
                        elif 'списк' in pattern:
                            topic = "Списки"
                        elif 'строк' in pattern:
                            topic = "Строки"
                    if topic and len(topic) > 2:
                        break
            
            # Если все еще не найдено, ищем ключевые слова
            if not topic:
                keyword_map = {
                    r'цикл[ыа]?': "Циклы",
                    r'списк[иа]?': "Списки",
                    r'строк[иа]?': "Строки",
                    r'функци[ия]?': "Функции",
                    r'рекурси[яи]?': "Рекурсия",
                    r'словар[ия]?': "Словари",
                    r'множеств[ао]?': "Множества",
                }
                
                for pattern, default_topic in keyword_map.items():
                    if re.search(pattern, first_line, re.IGNORECASE):
                        topic = default_topic
                        break
        
        if topic:
            return f'Курс по Python базовый. Разбираем задание по теме "{topic}" номер {task_number}'
        else:
            return f"Курс по Python базовый. Разбираем задание номер {task_number}"
    
    def get_name(self) -> str:
        """Получить имя генератора."""
        return "python_task"


class PythonAutoTitleGenerator(BaseTitleGenerator):
    """Автоматический генератор заголовков для Python.
    
    Определяет тип контента (тема или задание) и генерирует соответствующий заголовок.
    """
    
    def __init__(self):
        """Инициализировать генератор."""
        self.topic_generator = PythonTopicTitleGenerator()
        self.task_generator = PythonTaskTitleGenerator()
    
    def generate(self, video: VideoData) -> str:
        """Сгенерировать заголовок автоматически.
        
        Args:
            video: Данные видео.
            
        Returns:
            Заголовок для темы или задания.
        """
        description = video.description.strip()
        if not description:
            # Если описание пустое, пытаемся извлечь информацию из имени файла
            filename_stem = video.file_path.stem
            # Если имя файла начинается с "video" и содержит только цифры - это запись
            if filename_stem.startswith('video') and len(filename_stem) > 5 and filename_stem[5:].isdigit():
                return f"Курс по Python базовый. Запись урока"
            # Если имя файла в формате "X (Y)" или просто число - это задание
            match = re.match(r'^(\d+)\s*\(', filename_stem)
            if match:
                task_num = match.group(1)
                return f"Курс по Python базовый. Разбираем задание номер {task_num}"
            # Если имя файла - это только число
            if filename_stem.isdigit():
                return f"Курс по Python базовый. Разбираем задание номер {filename_stem}"
            return f"Курс по Python базовый. {filename_stem}"
        
        first_line = description.split('\n')[0].strip()
        first_line_lower = first_line.lower()
        
        # Проверяем, является ли это темой (урок без номера задания)
        # Паттерны для тем: "Урок.", "Видеоурок.", "Мини-урок", "Как...", "Понятие...", "Работа с...", "Методы...", "Первая программа", "Знакомство...", "Самые главные..."
        # Также "X. Как работает..." или "X. Что делает..." - это темы
        is_topic_pattern = (
            re.search(r'^урок\.', first_line_lower) or 
            re.search(r'^видеоурок\.', first_line_lower) or
            re.search(r'^мини-урок', first_line_lower) or
            re.search(r'^как\s+', first_line_lower) or
            re.search(r'^понятие\s+', first_line_lower) or
            re.search(r'^работа\s+с\s+', first_line_lower) or
            re.search(r'^методы\s+', first_line_lower) or
            re.search(r'^первая\s+программа', first_line_lower) or
            re.search(r'^знакомство\s+', first_line_lower) or
            re.search(r'^самые\s+главные', first_line_lower) or
            re.search(r'^\d+\.\s+как\s+', first_line_lower) or  # "2. Как работает цикл for"
            re.search(r'^\d+\.\s+что\s+', first_line_lower) or  # "4. Что делает функция range()"
            re.search(r'^\d+\.\s+как\s+работает', first_line_lower) or  # "2. Как работает цикл for"
            re.search(r'^\d+\.\s+что\s+делает', first_line_lower) or  # "4. Что делает функция range()"
            re.search(r'^циклы', first_line_lower) or  # "Циклы. Их назначение" или "Циклы..."
            re.search(r'^ооп', first_line_lower) or  # "ООП..."
            re.search(r'^числа', first_line_lower)  # "Числа ..."
        )
        
        if is_topic_pattern and not re.search(r'задание\s+\d+', first_line_lower):
            return self.topic_generator.generate(video)
        
        # Проверяем, есть ли номер задания
        if re.search(r'задание\s+[№#]?\s*\d+', first_line_lower) or \
           re.search(r'задани[ея]\s+\d+', first_line_lower):
            return self.task_generator.generate(video)
        
        # По умолчанию пробуем тему (если нет номера задания)
        if not re.search(r'задание\s+\d+|задани[ея]\s+\d+', first_line_lower):
            return self.topic_generator.generate(video)
        
        # Если ничего не подошло, возвращаем имя файла
        return f"Курс по Python базовый. {video.file_path.stem}"
    
    def get_name(self) -> str:
        """Получить имя генератора."""
        return "python_auto"
