import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from app.services.tts_service import (
    generate_speech,
    check_tts_health,
    KOKORO_VOICES,
)

logger = logging.getLogger("tts_routes")

router = APIRouter()


class SpeakRequest(BaseModel):
    text: str = Field(..., description="The text to synthesize into spoken audio.")
    voice: Optional[str] = Field(None, description="Optional Kokoro voice ID (e.g. bm_george).")
    speed: Optional[float] = Field(None, ge=0.5, le=2.0, description="Speech playback speed multiplier (0.5 - 2.0).")
    response_format: Optional[str] = Field("mp3", description="Audio container format (mp3 or wav).")


@router.post("/speak", tags=["TTS"])
async def text_to_speech(payload: SpeakRequest):
    """
    Synthesizes the provided text into audio using Kokoro TTS.
    Returns binary audio/mpeg streaming data.
    """
    if not payload.text or not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    try:
        audio_bytes = await generate_speech(
            text=payload.text,
            voice=payload.voice,
            speed=payload.speed,
            response_format=payload.response_format or "mp3",
        )
        
        media_type = "audio/wav" if payload.response_format == "wav" else "audio/mpeg"
        filename = "jarvis_speech.wav" if payload.response_format == "wav" else "jarvis_speech.mp3"
        
        return Response(
            content=audio_bytes,
            media_type=media_type,
            headers={
                "Content-Disposition": f"inline; filename={filename}",
                "Cache-Control": "public, max-age=3600",
            },
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as re:
        logger.error(f"TTS Synthesis error: {re}")
        raise HTTPException(status_code=503, detail=str(re))
    except Exception as e:
        logger.error(f"Unexpected TTS endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal TTS generation error: {str(e)}")


@router.get("/voices", tags=["TTS"])
async def list_voices():
    """
    Returns the catalog of supported Kokoro voices with languages and descriptions.
    """
    return {
        "status": "success",
        "voices": KOKORO_VOICES,
    }


@router.get("/status", tags=["TTS"])
async def get_tts_status():
    """
    Returns the operational and connectivity status of the Kokoro TTS service.
    """
    health = await check_tts_health()
    return health
