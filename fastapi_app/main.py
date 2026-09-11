import os

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import vector_store
from config import COLLISION_THRESHOLD, HF_ROUTER_BASE, LLM_TIMEOUT_SECONDS, SERVICE_TOKEN
from hf_client import HFError, chat
from persona import BUTTERFLY_EFFECT_PROMPT, RED_PILL_PROMPT

app = FastAPI(title="Cyber Orchestrator Cognitive Engine", version="1.0.0")

ASR_MODEL = os.getenv("HF_ASR_MODEL", "openai/whisper-large-v3")


@app.exception_handler(HFError)
async def hf_error_handler(_: Request, error: HFError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(error)})


def require_token(x_service_token: str = Header(default="")) -> None:
    if SERVICE_TOKEN and x_service_token != SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="invalid service token")


class IdeaIn(BaseModel):
    text: str
    user_id: str = ""
    source: str = "telegram"
    chat_id: str = ""


class NewsIn(BaseModel):
    title: str
    summary: str = ""
    url: str = ""
    category: str = "ai"
    top_k: int = Field(default=3, ge=1, le=10)


class RedPillIn(BaseModel):
    title: str
    summary: str = ""
    url: str = ""


class VoiceIn(BaseModel):
    file_id: str
    user_id: str = ""
    chat_id: str = ""


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "ideas": vector_store.count()}


@app.post("/ideas", dependencies=[Depends(require_token)])
async def create_idea(payload: IdeaIn) -> dict:
    if not payload.text.strip():
        raise HTTPException(status_code=422, detail="empty idea")
    idea_id = await vector_store.add_idea(
        payload.text,
        {"user_id": payload.user_id, "source": payload.source, "chat_id": payload.chat_id},
    )
    return {"id": idea_id, "total": vector_store.count()}


@app.post("/ideas/search", dependencies=[Depends(require_token)])
async def search_ideas(payload: NewsIn) -> dict:
    matches = await vector_store.query(f"{payload.title}\n{payload.summary}", payload.top_k)
    return {"matches": matches}


@app.post("/collide", dependencies=[Depends(require_token)])
async def collide(payload: NewsIn) -> dict:
    """Idea Collider: cross-reference fresh news with the user's stored ideas."""
    news_text = f"{payload.title}\n{payload.summary}"
    matches = await vector_store.query(news_text, payload.top_k)
    relevant = [m for m in matches if m["distance"] <= COLLISION_THRESHOLD]
    if not relevant:
        return {"collision": False, "matches": matches, "text": ""}

    ideas_block = "\n".join(f"- {m['document']}" for m in relevant)
    prompt = (
        "خبر تازه:\n"
        f"{news_text}\nلینک: {payload.url}\n\n"
        "ایده‌های قدیمی خود کاربر:\n"
        f"{ideas_block}\n\n"
        "یک بخش کوتاه با تیتر «💥 برخورد ایده‌ها» بنویس و نشان بده این خبر دقیقاً "
        "چطور به ایدهٔ قدیمی کاربر وصل می‌شود و الان چه کاری می‌شود با آن کرد. حداکثر ۵ خط."
    )
    try:
        text = await chat(prompt, temperature=0.8)
    except HFError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return {"collision": True, "matches": relevant, "text": text}


@app.post("/butterfly", dependencies=[Depends(require_token)])
async def butterfly(payload: NewsIn) -> dict:
    """Dystopian Butterfly Effect: 6-24 month systemic ripple projection."""
    prompt = (
        f"خبر:\n{payload.title}\n{payload.summary}\nلینک: {payload.url}\n\n"
        "فقط بخش اثر پروانه‌ای را بنویس."
    )
    try:
        text = await chat(prompt, extra_system=BUTTERFLY_EFFECT_PROMPT, temperature=0.6)
    except HFError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return {"text": text}


@app.post("/redpill", dependencies=[Depends(require_token)])
async def redpill(payload: RedPillIn) -> dict:
    context = await vector_store.query(f"{payload.title}\n{payload.summary}", 3)
    context_block = "\n".join(f"- {m['document']}" for m in context)
    prompt = (
        f"موضوع:\n{payload.title}\n{payload.summary}\nلینک: {payload.url}\n\n"
        f"زمینهٔ ایده‌های قبلی کاربر (اگر مرتبط بود استفاده کن):\n{context_block or 'ندارد'}"
    )
    try:
        text = await chat(prompt, extra_system=RED_PILL_PROMPT, temperature=0.75)
    except HFError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return {"text": text}


@app.post("/voice", dependencies=[Depends(require_token)])
async def voice(payload: VoiceIn) -> dict:
    """Download a Telegram voice note, transcribe it, and store it as an idea."""
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    hf_token = os.getenv("HF_TOKEN", "")
    if not telegram_token or not hf_token:
        raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN/HF_TOKEN missing")

    async with httpx.AsyncClient(timeout=LLM_TIMEOUT_SECONDS) as client:
        meta = await client.get(
            f"https://api.telegram.org/bot{telegram_token}/getFile",
            params={"file_id": payload.file_id},
        )
        meta.raise_for_status()
        file_path = meta.json()["result"]["file_path"]
        audio = await client.get(
            f"https://api.telegram.org/file/bot{telegram_token}/{file_path}"
        )
        audio.raise_for_status()
        asr = await client.post(
            f"{HF_ROUTER_BASE}/hf-inference/models/{ASR_MODEL}",
            headers={"Authorization": f"Bearer {hf_token}", "Content-Type": "audio/ogg"},
            content=audio.content,
        )
    if asr.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"ASR failed: {asr.text[:300]}")

    transcript = asr.json().get("text", "").strip()
    if not transcript:
        raise HTTPException(status_code=422, detail="empty transcript")
    idea_id = await vector_store.add_idea(
        transcript,
        {"user_id": payload.user_id, "source": "telegram_voice", "chat_id": payload.chat_id},
    )
    return {"id": idea_id, "transcript": transcript}
