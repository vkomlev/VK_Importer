"""Реестр источников экспорта для scan (Phase 2). Централизует алиасы ege/python/oge и пути."""

from pathlib import Path
from typing import List, Optional

from ..utils.env_utils import get_env_var

# Базовый каталог источников и относительные пути алиасов (ege/python/oge)
INPUT_DIR_DEFAULT = Path("input")
SOURCE_ALIASES = {
    "ege": "Экпорты ЕГЭ",
    "python": "Экспорт Python",
    "oge": "Экспорт ОГЭ",
}
OGE_ALTERNATIVE = "ОГЭ по информатике"  # fallback для oge, если основной путь не существует

# Выгрузки TG Parser: из env (TG_PARSER_OUT_DIR, TG_PARSER_FOLDERS — через запятую) или значения по умолчанию
_DEFAULT_TG_PARSER_OUT = Path("d:/Work/TG_Parser/out")
_DEFAULT_TG_PARSER_FOLDERS = [
    "cyberguru_ege__2026-02-19_15-11",
    "cyberguru_excel__2026-02-19_18-32",
    "CyberGuruKomlev__2026-02-19_17-04",
    "CyberGuruPython__2026-02-19_16-24",
    "InfOGELihgt__2026-02-19_17-01",
    "SQLPandasBI__2026-02-19_20-52",
]


def _get_tg_parser_config() -> tuple[Path, List[str]]:
    """Путь к out и список папок TG Parser из env или дефолты."""
    out_str = get_env_var("TG_PARSER_OUT_DIR") or get_env_var("TG_PARSER_OUT")
    out = Path(out_str) if out_str else _DEFAULT_TG_PARSER_OUT
    folders_str = get_env_var("TG_PARSER_FOLDERS")
    if folders_str:
        folders = [s.strip() for s in folders_str.split(",") if s.strip()]
    else:
        folders = _DEFAULT_TG_PARSER_FOLDERS
    return out, folders


def get_export_paths(source_filter: Optional[str] = None, input_dir: Optional[Path] = None) -> List[Path]:
    """Список путей к экспортам по фильтру источника.

    Не обрабатывает «mapped» — его вызывает main с folder_mappings из БД.
    При несуществующем пути для конкретной папки возвращает пустой список (сообщение в main).
    """
    input_dir = input_dir or INPUT_DIR_DEFAULT

    if not source_filter or source_filter == "all":
        export_paths = []
        if input_dir.exists():
            for channel_dir in input_dir.iterdir():
                if channel_dir.is_dir():
                    for export_folder in channel_dir.iterdir():
                        if export_folder.is_dir():
                            export_paths.append(export_folder)
                    export_paths.append(channel_dir)
        return export_paths

    if source_filter == "all_channels":
        export_paths = []
        if input_dir.exists():
            for channel_dir in input_dir.iterdir():
                if channel_dir.is_dir():
                    export_paths.append(channel_dir)
        return export_paths

    key = source_filter.lower()
    if key == "ege":
        ege_dir = input_dir / SOURCE_ALIASES["ege"]
        export_paths = []
        if ege_dir.exists():
            for export_folder in ege_dir.iterdir():
                if export_folder.is_dir():
                    export_paths.append(export_folder)
            export_paths.append(ege_dir)
        return export_paths

    if key == "python":
        python_dir = input_dir / SOURCE_ALIASES["python"]
        export_paths = []
        if python_dir.exists():
            export_paths.append(python_dir)
            for export_folder in python_dir.iterdir():
                if export_folder.is_dir():
                    export_paths.append(export_folder)
        return export_paths

    if key == "oge":
        oge_dir = input_dir / SOURCE_ALIASES["oge"]
        if not oge_dir.exists():
            oge_dir = input_dir / OGE_ALTERNATIVE
        export_paths = []
        if oge_dir.exists():
            export_paths.append(oge_dir)
            for export_folder in oge_dir.iterdir():
                if export_folder.is_dir():
                    export_paths.append(export_folder)
        return export_paths

    if key == "tg_parser":
        tg_out, tg_folders = _get_tg_parser_config()
        export_paths = []
        for name in tg_folders:
            p = tg_out / name
            if p.exists() and p.is_dir():
                export_paths.append(p)
        return export_paths

    # Конкретная папка
    export_path = Path(source_filter)
    if export_path.exists():
        return [export_path]
    return []
