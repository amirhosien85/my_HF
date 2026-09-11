import os


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_API_BASE = os.getenv("HF_API_BASE", "https://router.huggingface.co/v1")
HF_MODEL = os.getenv("HF_MODEL", "meta-llama/Meta-Llama-3-70B-Instruct")
HF_EMBEDDING_MODEL = os.getenv("HF_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

CHROMA_PATH = os.getenv("CHROMA_PATH", "/data/chroma")
IDEAS_COLLECTION = os.getenv("IDEAS_COLLECTION", "user_ideas")

SERVICE_PORT = _int_env("FASTAPI_PORT", 8500)
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "")

COLLISION_THRESHOLD = float(os.getenv("COLLISION_THRESHOLD", "0.35"))
LLM_TIMEOUT_SECONDS = _int_env("LLM_TIMEOUT_SECONDS", 120)
