# -*- coding: utf-8 -*-
"""
Тест CLI команд skip/unskip: реальный запуск main.py через subprocess.
Проверяет, что пометка по --file-from (UTF-8 файл) корректно пишется в БД.
Запуск: python tests/test_skip_cli.py
"""
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "videos.db"
MAIN_PY = PROJECT_ROOT / "main.py"

# Имя файла с кириллицей (как в задании)
TEST_FILENAME = "315_Мой_2024_в_профессии.mp4"


def _get_video_id_and_skip_state():
    """Вернуть (id, skip_upload) записи по окончанию пути или None."""
    if not DB_PATH.exists():
        return None, None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT id, skip_upload FROM videos WHERE file_path LIKE ? OR file_path LIKE ?",
        (f"%/{TEST_FILENAME}", f"%\\{TEST_FILENAME}"),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None, None
    return row["id"], bool(row["skip_upload"])


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    """Запуск main.py из корня проекта с UTF-8."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, str(MAIN_PY)] + args,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=15,
    )


def main():
    print("Тест CLI: skip / unskip --file-from (UTF-8 файл с кириллицей)")
    print("=" * 60)

    if not DB_PATH.exists():
        print("ПРОПУСК: videos.db не найден")
        return 1

    video_id, initial_skip = _get_video_id_and_skip_state()
    if video_id is None:
        print(f"ПРОПУСК: в базе нет записи для файла {TEST_FILENAME}")
        return 1

    print(f"Запись в БД: id={video_id}, изначально skip_upload={initial_skip}")

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write(TEST_FILENAME + "\n")
        list_path = f.name

    try:
        # 1) Снять пометку
        r = _run_cli(["unskip", "--id", str(video_id)])
        if r.returncode != 0:
            print("ОШИБКА: unskip --id", r.stderr or r.stdout)
            return 1
        print("  OK: unskip --id", video_id)

        # 2) Пометить через --file-from (файл в UTF-8 — обход кодировки терминала)
        r = _run_cli(["skip", "--file-from", list_path])
        if r.returncode != 0:
            print("ОШИБКА: skip --file-from", r.stderr or r.stdout)
            return 1
        print("  OK: skip --file-from (файл с именем", repr(TEST_FILENAME) + ")")
        print("     Вывод CLI:", (r.stdout or "").strip())

        _, skip_after = _get_video_id_and_skip_state()
        if not skip_after:
            print("ОШИБКА: в БД ожидалось skip_upload=1 после skip --file-from")
            return 1
        print("  OK: в БД установлено skip_upload=1")

        # 3) Снять пометку через --file-from
        r = _run_cli(["unskip", "--file-from", list_path])
        if r.returncode != 0:
            print("ОШИБКА: unskip --file-from", r.stderr or r.stdout)
            return 1
        print("  OK: unskip --file-from")

        _, skip_after_unskip = _get_video_id_and_skip_state()
        if skip_after_unskip:
            print("ОШИБКА: в БД ожидалось skip_upload=0 после unskip --file-from")
            return 1
        print("  OK: в БД установлено skip_upload=0")

        print("=" * 60)
        print("ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ. CLI skip/unskip --file-from работает.")
        return 0
    finally:
        os.unlink(list_path)
        if initial_skip is not None:
            _run_cli(["skip" if initial_skip else "unskip", "--id", str(video_id)])
            print("Восстановлено исходное состояние записи.")


if __name__ == "__main__":
    sys.exit(main())
