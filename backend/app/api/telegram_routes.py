import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.config import settings
from app.services.telegram_service import telegram_bot
from app.services.tools import send_telegram_message

logger = logging.getLogger("telegram_routes")

router = APIRouter()


class SendTestMessageRequest(BaseModel):
    message: Optional[str] = "🔔 Test notification from J.A.R.V.I.S. Web Dashboard! Telegram is connected and operational. 🚀"


@router.get("/status", tags=["Telegram"])
async def get_telegram_status():
    """
    Returns the live status of the Telegram Bot service and configuration.
    """
    bot_info = None
    if telegram_bot.application and telegram_bot.application.bot:
        try:
            me = await telegram_bot.application.bot.get_me()
            bot_info = {
                "id": me.id,
                "username": me.username,
                "first_name": me.first_name,
            }
        except Exception:
            pass

    has_token = bool(settings.TELEGRAM_BOT_TOKEN and not settings.TELEGRAM_BOT_TOKEN.startswith("your_"))
    
    return {
        "status": "success",
        "is_active": telegram_bot._is_running,
        "bot_info": bot_info,
        "has_token_configured": has_token,
        "chat_id_configured": bool(settings.TELEGRAM_CHAT_ID),
        "chat_id": settings.TELEGRAM_CHAT_ID if settings.TELEGRAM_CHAT_ID else None,
    }


@router.post("/test-message", tags=["Telegram"])
async def send_test_notification(payload: SendTestMessageRequest):
    """
    Dispatches a test notification to the configured Telegram chat.
    """
    try:
        msg = payload.message or "🔔 Test notification from J.A.R.V.I.S. Web Dashboard!"
        result = await send_telegram_message.ainvoke({"message": msg})
        return {
            "status": "success",
            "result": str(result),
        }
    except Exception as e:
        logger.error(f"Error sending test Telegram message: {e}")
        raise HTTPException(status_code=500, detail=str(e))
