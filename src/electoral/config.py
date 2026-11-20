from pathlib import Path
import os
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("ELECTORAL_DATA_DIR", ROOT / "data"))
DB_PATH = Path(os.getenv("ELECTORAL_DB_PATH", DATA_DIR / "observatory.duckdb"))
for layer in ("raw", "bronze", "silver", "gold"):
    (DATA_DIR / layer).mkdir(parents=True, exist_ok=True)
