import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data"
CHROMA_PATH = BASE_DIR / "chroma_db"
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"
LEADS_FILE = BASE_DIR / "leads.csv"
STORAGE_DIR = BASE_DIR / "storage"
DB_PATH = STORAGE_DIR / "app.db"

CHROMA_COLLECTION_NAME = "inquirybot_documents"
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-large")

DEFAULT_CHAT_MODEL = os.environ.get("DEFAULT_CHAT_MODEL", "gpt-4.1-mini")
_choices_str = os.environ.get("CHAT_MODEL_CHOICES", "gpt-4.1-mini,gpt-4o-mini")
CHAT_MODEL_CHOICES = [m.strip() for m in _choices_str.split(",") if m.strip()]
if DEFAULT_CHAT_MODEL not in CHAT_MODEL_CHOICES:
    CHAT_MODEL_CHOICES.insert(0, DEFAULT_CHAT_MODEL)

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
RETRIEVAL_K = 5

_threshold_str = os.environ.get("SIMILARITY_SCORE_THRESHOLD", "0.35")
try:
    SIMILARITY_SCORE_THRESHOLD = float(_threshold_str)
except (TypeError, ValueError):
    SIMILARITY_SCORE_THRESHOLD = 0.35

REFUSAL_MESSAGE = (
    "I could not find enough information in the ingested documents to answer that "
    "confidently. Please upload or ingest a relevant document and try again."
)

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
APP_ENV = os.environ.get("APP_ENV", "local")
ACTIVE_USER_TIMEOUT_MINUTES = 10
