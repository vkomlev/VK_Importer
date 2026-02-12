"""Точка входа CLI приложения."""

import sys
from pathlib import Path

# Добавить src в путь для импортов
sys.path.insert(0, str(Path(__file__).parent / "src"))

import click
import logging
from typing import Optional

# TODO: Реализовать CLI интерфейс
# Пока заглушка для структуры проекта

@click.command()
@click.option("--config", "-c", default="config/config.yaml", help="Путь к конфигурационному файлу")
@click.option("--export-path", "-e", help="Путь к экспорту Telegram")
@click.option("--dry-run", is_flag=True, help="Режим тестирования без публикации")
def main(config: str, export_path: Optional[str], dry_run: bool):
    """VK Video Publisher - публикатор видео из Telegram экспорта в VK Video."""
    click.echo("VK Video Publisher")
    click.echo("Проект находится в разработке")
    click.echo(f"Конфигурация: {config}")
    if export_path:
        click.echo(f"Экспорт: {export_path}")
    if dry_run:
        click.echo("Режим: DRY RUN")


if __name__ == "__main__":
    main()
