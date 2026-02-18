import sqlite3
from pathlib import Path
p = Path(__file__).resolve().parent.parent / "videos.db"
print("DB exists:", p.exists())
conn = sqlite3.connect(str(p))
r = conn.execute("SELECT COUNT(*) FROM videos WHERE file_path LIKE ?", ("%AlgorithmPythonStruct%",)).fetchone()
print("Count AlgorithmPythonStruct:", r[0])
conn.close()
