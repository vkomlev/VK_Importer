# -*- coding: utf-8 -*-
import sqlite3
from pathlib import Path

db = Path(__file__).resolve().parent.parent / "videos.db"
conn = sqlite3.connect(str(db))
c = conn.cursor()
c.execute("SELECT DISTINCT channel FROM videos WHERE channel IS NOT NULL")
print("Channels:", c.fetchall())
c.execute("SELECT id, channel, substr(title,1,50), substr(file_path,1,70) FROM videos WHERE file_path LIKE '%AlgorithmPythonStruct%' OR file_path LIKE '%Algorithm%' LIMIT 10")
for row in c.fetchall():
    print(row)
conn.close()
