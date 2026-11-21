"""Настройки приложения. Этот файл разрешено менять в ДЗ."""

import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8080"))
DATA_DIR = Path(os.environ.get("DATA_DIR", str(PROJECT_DIR / "work" / "data")))
INSTANCE_NAME = os.environ.get("INSTANCE_NAME", "csv-reports")
STARTUP_DELAY_SECONDS = float(os.environ.get("STARTUP_DELAY_SECONDS", "0"))
VERSION = 1
