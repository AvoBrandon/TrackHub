import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "sqlite://")  # in-memory for tests
os.environ.setdefault("SCHEDULER_ENABLED", "false")
os.environ.setdefault("API_TOKEN", "test-token")
