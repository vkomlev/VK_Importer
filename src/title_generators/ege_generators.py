"""Генераторы заголовков для канала ЕГЭ."""

import re
from typing import Optional

from .base import BaseTitleGenerator
from ..models.video import VideoData


class EGETopicTitleGenerator(BaseTitleGenerator):
    """Генератор заголовков для разбора тем ЕГЭ.
    
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
        # Урок с подчеркиванием (23_1, 23_2)
        lesson_match = re.search(r'урок\s+(\d+[._]\d+)\.\s*(.+?)(?:\.|$)', first_line, re.IGNORECASE)
        if lesson_match:
            lesson_num = lesson_match.group(1).replace('.', '_')
            topic = lesson_match.group(2).strip()
            if topic and len(topic) > 3:
                return f'Курс ЕГЭ по информатике. Урок {lesson_num}. Разбираем тему "{topic}"'
        
        # Обычный урок (2, 11 и т.д.)
        lesson_match = re.search(r'урок\s+(\d+)\.\s*(.+?)(?:\.|$)', first_line, re.IGNORECASE)
        if lesson_match:
            lesson_num = lesson_match.group(1)
            topic = lesson_match.group(2).strip()
            if topic and len(topic) > 3:
                return f'Курс ЕГЭ по информатике. Урок {lesson_num}. Разбираем тему "{topic}"'
        
        # "Разбор заданий X. Название темы" - извлекаем тему
        task_topic_match = re.search(r'разбор\s+задани[ий]\s+\d+\.\s*(.+?)(?:\.|$)', first_line, re.IGNORECASE)
        if task_topic_match:
            topic = task_topic_match.group(1).strip()
            if topic and len(topic) > 3:
                return f'Курс ЕГЭ по информатике. Разбираем тему "{topic}"'
        
        # Задание с темой
        task_match = re.search(r'задание\s+\d+\.\s*(.+?)(?:\.|$)', first_line, re.IGNORECASE)
        if task_match:
            topic = task_match.group(1).strip()
            if topic and len(topic) > 3:
                return f'Курс ЕГЭ по информатике. Разбираем тему "{topic}"'
        
        # "Термины и теория задания X. Тема" - извлекаем тему после точки
        if 'термин' in first_line_lower and 'теори' in first_line_lower:
            topic_match = re.search(r'термин[ы]?\s+и\s+теори[ия]\s+задани[яе]\s+\d+\.\s*(.+?)(?:\.|$)', first_line, re.IGNORECASE)
            if topic_match:
                topic = topic_match.group(1).strip()
                if topic and len(topic) > 3:
                    return f'Курс ЕГЭ по информатике. Разбираем тему "{topic}"'
        
        return f"Курс ЕГЭ по информатике. {video.file_path.stem}"
    
    def get_name(self) -> str:
        """Получить имя генератора."""
        return "ege_topic"


class EGETaskTitleGenerator(BaseTitleGenerator):
    """Генератор заголовков для разбора заданий ЕГЭ.
    
    Формат: "Разбираем задание №X" или "Разбираем задание №X (подтип) (ресурс)"
    """
    
    def _extract_resource(self, text: str) -> Optional[str]:
        """Извлечь название ресурса из текста.
        
        Args:
            text: Текст для анализа.
            
        Returns:
            Название ресурса или None.
        """
        # Паттерны для ресурсов в скобках
        resource_patterns = [
            r'\(Решу\s+ЕГЭ\)',
            r'\(РешуЕГЭ\)',  # Без пробела
            r'\(КЕГЭ\)',
            r'\(Поляков\)',
            r'\(Комп\s+ЕГЭ\)',
            r'\(КЕГЭ\.\w+\)',
        ]
        
        for pattern in resource_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0).strip('()')
        
        # Проверяем без скобок (например, "Поляков" в конце)
        if re.search(r'\s+Поляков\s*$', text, re.IGNORECASE):
            return "Поляков"
        
        return None
    
    def generate(self, video: VideoData) -> str:
        """Сгенерировать заголовок для задания.
        
        Args:
            video: Данные видео.
            
        Returns:
            Заголовок в формате "Разбираем задание №X" или имя файла.
        """
        description = video.description.strip()
        if not description:
            return f"Курс ЕГЭ по информатике. {video.file_path.stem}"
        
        # Извлекаем первую строку
        first_line = description.split('\n')[0].strip()
        
        # Паттерны для номеров заданий (расширенные)
        patterns = [
            r'тип\s+(\d+)[_\d]',  # "Тип 13_3784"
            r'разбор\s+(\d+)[_\d]',  # "Разбор 8_40724"
            r'решение\s+(\d+)[_\d]',  # "Решение 13_69921", "Решение 6_58245"
            r'^(\d+)[_\d]',  # "26_27423" в начале строки
            r'вспомогательные\s+примеры\s+для\s+решения\s+(\d+)',  # "Вспомогательные примеры для решения 17"
            r'разбор\s+задани[ий]\s+(\d+)$',  # "Разбор заданий 23" (в конце строки)
            r'разбор\s+задани[ий]\s+(\d+)\s*\.',  # "Разбор заданий 23." (с точкой)
            r'вспомогательного\s+задани[яе]\s*[№#]?\s*(\d+)',  # "вспомогательного задания №8"
            r'в\s+задани[ии]\s+(\d+)',  # "в задании 17"
            r'тонкости\s+решений\s+задани[ий]\s+(\d+)',  # "тонкости решений заданий 14"
            r'теори[ия]\s+по\s+задани[ям]\s+(\d+)',  # "теории по заданиям 5"
            r'задани[яе]\s*[№#]?\s*(\d+)',  # "задание №25"
            r'задани[ея]\s+(\d+)',  # "задание 3"
            r'задач[аи]\s+(\d+)',  # "задача 16"
            r'разбор\s+решений\s+задани[ий]\s+(\d+)',  # "разбор решений заданий 3"
            r'разбор\s+некоторых\s+задани[ий]\s+(\d+)',  # "разбор некоторых заданий 5"
            r'разбор\s+задани[ея]\s+(\d+)',  # "разбор задания 5"
            r'разбор\s+задач[иа]\s+(\d+)',  # "разбор задачи 16"
            r'разбор\s+задани[ий]\s+по\s+теме\s+(\d+)',  # "разбор заданий по теме 3"
            r'разбор\s+задани[ий]\s+(\d+)[,\s]',  # "разбор заданий 12," или "разбор заданий 12 "
            r'разбор\s+задани[ий]\s+(\d+)[-_](\d+)',  # "разбор заданий 19-21"
            r'разбор\s+задани[ий]\s+(\d+)\s+егэ',  # "разбор заданий 7 ЕГЭ"
            r'решение\s+задани[яе]\s*[№#]?\s*(\d+)',  # "решение задания №25"
            r'решение\s+задани[ий]\s+егэ\s+(\d+)',  # "решение заданий ЕГЭ 9"
            r'решение\s+(\d+)\s+задани[ий]',  # "решение 8 заданий", "решение 4 заданий"
            r'решения\s+задани[ий]\s+(\d+)',  # "решения заданий 13"
            r'решение\s+задани[ея]\s+(\d+)',
            r'решение\s+задани[ий]\s+(\d+)',  # "решение заданий 7"
            r'решение\s+нескольких\s+задач\s+из\s+блока\s+(\d+)',  # "решение нескольких задач из блока 3"
            r'при\s+решении\s+задани[ий]\s+(\d+)',  # "при решении заданий 3"
            r'для\s+задани[ий]\s+(\d+)',  # "для заданий 13"
            r'задани[яе]\s+номер\s+(\d+)',  # "заданий номер 9"
            r'разбор\s+задани[ий]\s+номер\s+(\d+)',  # "разбор заданий номер 9"
            r'в\s+файле\s+\w+\s+задани[яе]\s+(\d+)',  # "в файле B задания 27"
            r'видео\s+решения?\s+задани[ея]\s+(\d+)',  # "Видео решения задания 1"
            r'видеоразбор\s+задани[яе]\s+(\d+)',  # "Видеоразбор задания 1"
            r'для\s+решения\s+\d+%\s+задани[ий]\s+(\d+)',  # "для решения 98% заданий 14"
            r'при\s+решении\s+(\d+)\s+задани[ий]',  # "при решении 14 заданий"
        ]
        
        task_number = None
        task_type = None
        task_range = None
        
        # Сначала проверяем диапазон заданий (19-21)
        range_match = re.search(r'задани[ий]\s+(\d+)[-_](\d+)', first_line, re.IGNORECASE)
        if range_match:
            task_number = int(range_match.group(1))
            task_range = f"{range_match.group(1)}-{range_match.group(2)}"
        else:
            # Ищем одиночный номер задания
            for pattern in patterns:
                match = re.search(pattern, first_line, re.IGNORECASE)
                if match:
                    task_number = int(match.group(1))
                    break
        
        if not task_number:
            return f"Курс ЕГЭ по информатике. {video.file_path.stem}"
        
        # Проверяем наличие подтипа (например, 22_4708k или 16_55633 или 9_58517)
        # Сначала проверяем формат "9 - 58517" (с пробелами вокруг дефиса)
        subtype_match = re.search(r'(\d+)\s*-\s*(\d+)', first_line)
        if subtype_match and not task_range:
            num1, num2 = int(subtype_match.group(1)), int(subtype_match.group(2))
            # Если первый номер совпадает с номером задания и второй намного больше - это подтип
            if num1 == task_number and num2 > 100:
                task_type = f"{subtype_match.group(1)}_{subtype_match.group(2)}"
        
        # Если подтип не найден, проверяем формат с подчеркиванием
        if not task_type:
            subtype_match = re.search(r'(\d+)[_](\d+)', first_line)
            if subtype_match and not task_range:
                num1, num2 = int(subtype_match.group(1)), int(subtype_match.group(2))
                if abs(num1 - num2) > 5:  # Если разница большая, это подтип, а не диапазон
                    task_type = f"{subtype_match.group(1)}_{subtype_match.group(2)}"
        
        # Извлекаем ресурс (улучшенное извлечение)
        resource = self._extract_resource(first_line)
        # Также проверяем "РешуЕГЭ" без пробела
        if not resource and re.search(r'решуегэ', first_line, re.IGNORECASE):
            resource = "Решу ЕГЭ"
        
        # Формируем заголовок
        if task_range:
            parts = [f"Курс ЕГЭ по информатике. Разбираем задание №{task_range}"]
        else:
            parts = [f"Курс ЕГЭ по информатике. Разбираем задание №{task_number}"]
        
        if task_type:
            parts.append(f"({task_type})")
        
        if resource:
            parts.append(f"({resource})")
        
        return " ".join(parts)
    
    def get_name(self) -> str:
        """Получить имя генератора."""
        return "ege_task"


class EGEAutoTitleGenerator(BaseTitleGenerator):
    """Автоматический генератор заголовков для ЕГЭ.
    
    Определяет тип контента (тема или задание) и генерирует соответствующий заголовок.
    """
    
    def __init__(self):
        """Инициализировать генератор."""
        self.topic_generator = EGETopicTitleGenerator()
        self.task_generator = EGETaskTitleGenerator()
    
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
            # Если имя файла содержит "Встреча_в_Телемосте", это запись встречи
            if "Встреча_в_Телемосте" in filename_stem:
                return f"Курс ЕГЭ по информатике. Запись встречи"
            # Если имя файла - это только число (возможно, номер задания из Решу ЕГЭ)
            if filename_stem.isdigit():
                return f"Курс ЕГЭ по информатике. Разбираем задание №{filename_stem} (Решу ЕГЭ)"
            # Если имя файла в формате "X_Y" (например, 25_2) - это задание с подтипом
            match = re.match(r'^(\d+)[_\d]', filename_stem)
            if match:
                task_num = match.group(1)
                return f"Курс ЕГЭ по информатике. Разбираем задание №{task_num}"
            # Если имя файла в формате "X (Y)" (например, 5 (2)) - это задание
            match = re.match(r'^(\d+)\s*\(', filename_stem)
            if match:
                task_num = match.group(1)
                return f"Курс ЕГЭ по информатике. Разбираем задание №{task_num}"
            return f"Курс ЕГЭ по информатике. {filename_stem}"
        
        first_line = description.split('\n')[0].strip()
        first_line_lower = first_line.lower()
        
        # "Видео решения задания X" и "Видеоразбор задания X" - это задания (проверяем ПЕРВЫМИ)
        if 'видео' in first_line_lower and 'задани' in first_line_lower:
            # Проверяем паттерны для заданий
            video_patterns = [
                r'видео\s+решения?\s+задани[ея]\s+(\d+)',  # "Видео решения задания 1"
                r'видеоразбор\s+задани[яе]\s+(\d+)',  # "Видеоразбор задания 1"
            ]
            for pattern in video_patterns:
                match = re.search(pattern, first_line, re.IGNORECASE)
                if match:
                    task_number = int(match.group(1))
                    return f'Курс ЕГЭ по информатике. Разбираем задание №{task_number}'
        
        # "Пример X для задания Y" или "Пример X в файле B задания Y" - это тема (проверяем ПЕРВОЙ)
        if 'пример' in first_line_lower and 'задани' in first_line_lower:
            # Проверяем различные варианты - упрощаем паттерн
            if 'в файле' in first_line_lower or 'для задани' in first_line_lower:
                topic = first_line.split('.')[0].strip()
                if len(topic) > 5:
                    return f'Курс ЕГЭ по информатике. Разбираем тему "{topic}"'
        
        # Проверяем, является ли это темой
        # Уроки с подчеркиванием или точкой
        if re.search(r'урок\s+\d+[._]\d+\.', first_line_lower) or \
           re.search(r'урок\s+\d+\.', first_line_lower):
            return self.topic_generator.generate(video)
        
        # "Разбор заданий X. Название темы" - это тема, а не задание
        # Проверяем наличие точки после номера и текста после точки
        # Но исключаем "Видео решения" и "Видеоразбор" - это задания
        if not re.search(r'видео\s+решения?\s+задани[яе]|видеоразбор\s+задани[яе]', first_line_lower):
            topic_match = re.search(r'разбор\s+задани[ий]\s+(\d+)\.\s+(.+?)(?:\.|$)', first_line, re.IGNORECASE)
            if topic_match:
                topic_text = topic_match.group(2).strip()
                # Если после точки есть текст (не просто номер), это тема
                if topic_text and len(topic_text) > 5:
                    return self.topic_generator.generate(video)
        
        # "Разбор заданий по теме X. Название" - это тема
        topic_theme_match = re.search(r'разбор\s+задани[ий]\s+по\s+теме\s+\d+\.\s*(.+?)(?:\.|$)', first_line, re.IGNORECASE)
        if topic_theme_match:
            topic = topic_theme_match.group(1).strip()
            if topic and len(topic) > 3:
                return f'Курс ЕГЭ по информатике. Разбираем тему "{topic}"'
        
        # "Задание X. Название темы" без слов "разбор" или "решение"
        if re.search(r'задани[ея]\s+\d+\.\s+[А-Яа-я]', first_line) and \
           not re.search(r'разбор|решение', first_line_lower):
            return self.topic_generator.generate(video)
        
        # "Пример X для задания Y" или "Пример X в файле B задания Y" - это тема
        if 'пример' in first_line_lower and 'задани' in first_line_lower:
            # Проверяем различные варианты - упрощаем паттерн
            if 'в файле' in first_line_lower or 'для задани' in first_line_lower:
                topic = first_line.split('.')[0].strip()
                if len(topic) > 5:
                    return f'Курс ЕГЭ по информатике. Разбираем тему "{topic}"'
        
        # Инструкции и темы без номеров
        if re.search(r'инструкция|способ[овы]|ответы\s+на\s+вопросы|карта\s+егэ|агрегатные\s+функции|лайфхак|несколько\s+приемов|особенности\s+и\s+тонкости|регулярные\s+выражения|заполняем\s+карту|теория\s+сетей|группы\s+в\s+регулярных|опережающие\s+проверки|переводим\s+число', first_line_lower):
            # Формируем заголовок из первой строки
            topic = first_line.split('.')[0].strip()
            if len(topic) > 5:
                return f'Курс ЕГЭ по информатике. Разбираем тему "{topic}"'
        
        # "Термины и теория задания X" - это тема, а не задание
        # Учитываем возможные двойные пробелы - используем более гибкий паттерн
        if 'термин' in first_line_lower and 'теори' in first_line_lower and 'задани' in first_line_lower:
            # Извлекаем тему из первой строки (после точки)
            topic_match = re.search(r'термин[ы]?\s+и\s+теори[ия]\s+задани[яе]\s+\d+\.\s*(.+?)(?:\.|$)', first_line, re.IGNORECASE)
            if topic_match:
                topic = topic_match.group(1).strip()
                if len(topic) > 5:
                    return f'Курс ЕГЭ по информатике. Разбираем тему "{topic}"'
            # Или просто берем первую часть до точки
            topic = first_line.split('.')[0].strip()
            # Убираем лишние пробелы
            topic = ' '.join(topic.split())
            if len(topic) > 5:
                return f'Курс ЕГЭ по информатике. Разбираем тему "{topic}"'
        
        # "Использование X для решения Y задач" - это тема
        if re.search(r'использование\s+.+?\s+для\s+решения\s+\d+\s+задач', first_line_lower):
            topic = first_line.split('.')[0].strip()
            if len(topic) > 5:
                return f'Курс ЕГЭ по информатике. Разбираем тему "{topic}"'
        
        # Темы, начинающиеся с "Как", "Еще", "Немного"
        if re.search(r'^(как|еще|немного|некоторые)', first_line_lower):
            # Извлекаем тему из первой строки (до первой точки или до конца)
            # Но ограничиваем длину разумным значением
            topic_match = re.search(r'^(.+?)(?:\.|$)', first_line)
            if topic_match:
                topic = topic_match.group(1).strip()
                # Ограничиваем длину темы (максимум 80 символов для читаемости)
                if len(topic) > 80:
                    # Пытаемся обрезать по последнему пробелу до 80 символов
                    truncated = topic[:80].rsplit(' ', 1)[0]
                    if len(truncated) > 50:  # Если получилось достаточно длинное
                        topic = truncated
                    else:
                        topic = topic[:77] + "..."
                if len(topic) > 10:  # Минимальная длина для темы
                    return f'Курс ЕГЭ по информатике. Разбираем тему "{topic}"'
        
        # Проверяем наличие номера задания (если есть - это задание)
        # Но исключаем случаи, когда это тема (например, "Разбор заданий 2. Тема")
        # Исключаем "Пример X в файле B задания Y" - это тема
        if re.search(r'задани[ея]\s+\d+\.\s+[А-Яа-я]', first_line) and \
           not (first_line_lower.startswith('пример') and 'в файле' in first_line_lower):
            # Это тема, а не задание
            return self.topic_generator.generate(video)
        
        # "Разбор заданий по теме X" - это тема, а не задание
        if re.search(r'разбор\s+задани[ий]\s+по\s+теме\s+\d+', first_line_lower):
            return self.topic_generator.generate(video)
        
        # Исключаем "Пример X в файле B задания Y" из проверки заданий
        if re.search(r'задани[ея]\s+\d+|задач[аи]\s+\d+|блока\s+\d+', first_line_lower) and \
           not (first_line_lower.startswith('пример') and 'в файле' in first_line_lower):
            return self.task_generator.generate(video)
        
        # Иначе пробуем задание
        result = self.task_generator.generate(video)
        # Если получилось имя файла, значит не распозналось - возвращаем как есть
        if video.file_path.stem in result:
            return result
        
        return result
    
    def get_name(self) -> str:
        """Получить имя генератора."""
        return "ege_auto"
