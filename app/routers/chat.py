from fastapi import APIRouter, Request
from groq import AsyncGroq

from app.config import get_settings
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/v1", tags=["chat"])

_MODEL = "llama-3.3-70b-versatile"


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, payload: ChatRequest):
    """Protected endpoint — requires X-API-Key. Rate-limited per tier."""
    settings = get_settings()
    client = AsyncGroq(api_key=settings.GROQ_API_KEY)

    completion = await client.chat.completions.create(
        model=_MODEL,
        messages=[{"role": "user", "content": payload.message}],
        max_tokens=1024,
    )

    return ChatResponse(
        response=completion.choices[0].message.content,
        model=_MODEL,
        tier=request.state.tier,
    )
