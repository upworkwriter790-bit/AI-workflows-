"""Environment-driven configuration.

All settings have sane defaults so the project runs with zero setup in stub mode.
"""
import os

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma")
DB_PATH = os.getenv("DB_PATH", "./data/app.db")
CRM_DIR = os.getenv("CRM_DIR", "./data/crm")

USE_CLOUD_LLM = _bool("USE_CLOUD_LLM", False)
USE_STUB_LLM = _bool("USE_STUB_LLM", False)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

RAG_ENABLED = _bool("RAG_ENABLED", True)


def llm_mode() -> str:
    """Resolve which LLM backend to use.

    Returns one of: "stub", "cloud", "ollama".
    """
    if USE_STUB_LLM:
        return "stub"
    if USE_CLOUD_LLM and OPENAI_API_KEY:
        return "cloud"
    return "ollama"
