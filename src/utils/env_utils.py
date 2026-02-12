"""Утилиты для работы с переменными окружения из .env файла."""

import os
from pathlib import Path
from typing import Optional


def load_env_file(env_path: Optional[Path] = None) -> dict[str, str]:
    """Загрузить переменные окружения из .env файла.
    
    Args:
        env_path: Путь к .env файлу. Если None, ищет .env в корне проекта.
        
    Returns:
        Словарь с переменными окружения.
    """
    if env_path is None:
        # Ищем .env в корне проекта (на уровень выше src)
        project_root = Path(__file__).parent.parent.parent
        env_path = project_root / ".env"
    
    env_vars = {}
    
    if not env_path.exists():
        return env_vars
    
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            
            # Пропускаем пустые строки и комментарии
            if not line or line.startswith("#"):
                continue
            
            # Парсим KEY=VALUE
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                
                # Убираем кавычки если есть
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                
                env_vars[key] = value
    
    return env_vars


def get_env_var(key: str, default: Optional[str] = None, env_path: Optional[Path] = None) -> Optional[str]:
    """Получить переменную окружения из .env файла или системных переменных.
    
    Args:
        key: Имя переменной.
        default: Значение по умолчанию.
        env_path: Путь к .env файлу.
        
    Returns:
        Значение переменной или default.
    """
    # Сначала проверяем системные переменные окружения
    value = os.getenv(key)
    if value:
        return value
    
    # Затем проверяем .env файл
    env_vars = load_env_file(env_path)
    return env_vars.get(key, default)
