from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.auth.permissions import Permission
from app.common.responses import success
from app.core.database import get_db
from app.models.user import User
from app.schemas.ai import ChatRequest, ChatResponse

router = APIRouter(prefix="/ai", tags=["ai"])

# Simple in-process rate limiter for the AI endpoint specifically (in
# addition to the global rate limiter in app/core/middleware — AI calls are
# far more expensive than a typical CRUD request, so they get a tighter,
# separate budget). Keyed by user id; a Redis-backed limiter would replace
# this in a multi-process deployment.
_ai_call_log: dict[int, list[float]] = {}


def _check_ai_rate_limit(user_id: int, limit_per_minute: int) -> None:
    import time

    now = time.time()
    window = _ai_call_log.setdefault(user_id, [])
    window[:] = [t for t in window if now - t < 60]
    if len(window) >= limit_per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": {"code": "AI_RATE_LIMIT_EXCEEDED", "message": "Too many AI requests — please wait a moment."}},
        )
    window.append(now)


@router.post("/chat")
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.AI_USE)),
):
    from app.ai.chat_service import run_chat_turn
    from app.core.config import get_settings

    settings = get_settings()
    _check_ai_rate_limit(user.id, settings.ai_rate_limit_per_minute)

    result = run_chat_turn(db, user.id, payload.conversation_id, payload.message)
    return success(ChatResponse(**result).model_dump())
