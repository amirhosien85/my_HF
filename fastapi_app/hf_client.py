import httpx

from config import (
    HF_API_BASE,
    HF_EMBEDDING_MODEL,
    HF_MODEL,
    HF_TOKEN,
    LLM_TIMEOUT_SECONDS,
)
from persona import PERSONA_SYSTEM_PROMPT, sanitize


class HFError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    if not HF_TOKEN:
        raise HFError("HF_TOKEN is not configured")
    return {"Authorization": f"Bearer {HF_TOKEN}"}


async def chat(user_prompt: str, extra_system: str = "", temperature: float = 0.7) -> str:
    """Call the Hugging Face router (OpenAI-compatible chat completions)."""
    system_prompt = PERSONA_SYSTEM_PROMPT
    if extra_system:
        system_prompt = f"{system_prompt}\n\n{extra_system}"

    payload = {
        "model": HF_MODEL,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT_SECONDS) as client:
        response = await client.post(
            f"{HF_API_BASE}/chat/completions", headers=_headers(), json=payload
        )
    if response.status_code >= 400:
        raise HFError(f"HF chat failed ({response.status_code}): {response.text[:500]}")
    body = response.json()
    return sanitize(body["choices"][0]["message"]["content"])


async def embed(texts: list[str]) -> list[list[float]]:
    """Feature extraction through the HF Inference API."""
    url = f"https://api-inference.huggingface.co/models/{HF_EMBEDDING_MODEL}"
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT_SECONDS) as client:
        response = await client.post(
            url,
            headers=_headers(),
            json={"inputs": texts, "options": {"wait_for_model": True}},
        )
    if response.status_code >= 400:
        raise HFError(f"HF embedding failed ({response.status_code}): {response.text[:500]}")
    vectors = response.json()
    if vectors and isinstance(vectors[0], list) and vectors[0] and isinstance(vectors[0][0], list):
        # token-level output -> mean pool
        vectors = [[sum(dim) / len(dim) for dim in zip(*sentence)] for sentence in vectors]
    return vectors
