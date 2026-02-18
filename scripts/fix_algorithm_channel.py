# -*- coding: utf-8 -*-
"""Выставить channel='Алгоритмы' для записей из выгрузки AlgorithmPythonStruct."""
import sqlite3
from pathlib import Path

db = Path(__file__).resolve().parent.parent / "videos.db"
conn = sqlite3.connect(str(db))
c = conn.cursor()
c.execute("UPDATE videos SET channel = ? WHERE file_path LIKE ?", ("Алгоритмы", "%AlgorithmPythonStruct%"))
n = c.rowcount
conn.commit()
conn.close()
print(f"Обновлено записей: {n}")
