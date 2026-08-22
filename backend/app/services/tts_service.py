import re
import logging
from typing import Optional, List, Dict, Any
import httpx
from app.core.config import settings

logger = logging.getLogger("tts_service")

# Supported Kokoro voices catalog
KOKORO_VOICES: List[Dict[str, Any]] = [
    {
        "id": "bm_george",
        "name": "George (J.A.R.V.I.S. British Male)",
        "language": "en-gb",
        "gender": "male",
        "recommended": True,
        "description": "Refined, calm British gentleman cadence — optimal for J.A.R.V.I.S."
    },
    {
        "id": "bm_daniel",
        "name": "Daniel (British Male)",
        "language": "en-gb",
        "gender": "male",
        "recommended": False,
        "description": "Crisp and formal British male voice."
    },
    {
        "id": "bm_lewis",
        "name": "Lewis (British Male)",
        "language": "en-gb",
        "gender": "male",
        "recommended": False,
        "description": "Natural, conversational British male voice."
    },
    {
        "id": "bm_fable",
        "name": "Fable (British Male)",
        "language": "en-gb",
        "gender": "male",
        "recommended": False,
        "description": "Warm British narrative male voice."
    },
    {
        "id": "bf_alice",
        "name": "Alice (British Female)",
        "language": "en-gb",
        "gender": "female",
        "recommended": False,
        "description": "Clear and polite British female voice."
    },
    {
        "id": "bf_emma",
        "name": "Emma (British Female)",
        "language": "en-gb",
        "gender": "female",
        "recommended": False,
        "description": "Friendly British female tone."
    },
    {
        "id": "am_adam",
        "name": "Adam (American Male)",
        "language": "en-us",
        "gender": "male",
        "recommended": False,
        "description": "Deep American male voice."
    },
    {
        "id": "af_bella",
        "name": "Bella (American Female)",
        "language": "en-us",
        "gender": "female",
        "recommended": False,
        "description": "Warm American female voice."
    },
]


def clean_text_for_speech(text: str) -> str:
    """
    Sanitizes markdown and technical text so it sounds natural when synthesized by TTS.
    - Strips code blocks and replaces them with a short verbal placeholder.
    - Strips markdown formatting (headers, bold, italics, links, tables, blockquotes).
    - Removes raw URLs and excess symbols.
    """
    if not text:
        return ""

    cleaned = str(text)

    # 1. Replace multi-line code blocks ```lang ... ``` with verbal cue
    cleaned = re.sub(r'```[\w\-]*\n[\s\S]*?\n```', ' (code block omitted) ', cleaned)
    cleaned = re.sub(r'```[\s\S]*?```', ' (code snippet omitted) ', cleaned)

    # 2. Inline code `code` -> code
    cleaned = re.sub(r'`([^`]+)`', r'\1', cleaned)

    # 3. Markdown images ![alt](url) -> ""
    cleaned = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', '', cleaned)

    # 4. Markdown links [text](url) -> text
    cleaned = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', cleaned)

    # 5. Raw URLs -> "link"
    cleaned = re.sub(r'https?://[^\s]+', 'link', cleaned)

    # 6. Markdown table rows | col1 | col2 | -> strip vertical pipes
    cleaned = re.sub(r'\|[^\n]+\|', ' ', cleaned)
    cleaned = re.sub(r'^[|\-:\s]+$', '', cleaned, flags=re.MULTILINE)

    # 7. Headers (#, ##, ###)
    cleaned = re.sub(r'^\s*#{1,6}\s+', '', cleaned, flags=re.MULTILINE)

    # 8. Bold & Italic (*, _, **, __, ~~)
    cleaned = re.sub(r'[*_~]{1,3}([^*_~]+)[*_~]{1,3}', r'\1', cleaned)

    # 9. Blockquotes (> quote)
    cleaned = re.sub(r'^\s*>\s*', '', cleaned, flags=re.MULTILINE)

    # 10. Unordered list bullets (*, -, •)
    cleaned = re.sub(r'^\s*[\*\-•]\s+', '', cleaned, flags=re.MULTILINE)

    # 11. Strip all Unicode emojis and pictographic symbols so TTS does not speak out emoji names (e.g. "money bag")
    cleaned = re.sub(r'[\U00010000-\U0010ffff\u2600-\u27BF\u2300-\u23FF\u2B50\uFE00-\uFE0F\u200D]', '', cleaned)

    # 12. Normalize excessive whitespace and newlines
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    return cleaned


async def generate_speech(
    text: str,
    voice: Optional[str] = None,
    speed: Optional[float] = None,
    response_format: str = "mp3"
) -> bytes:
    """
    Sends synthesized speech request to the Kokoro TTS service.
    Returns the binary audio data (MP3/WAV/OGG).
    """
    clean_input = clean_text_for_speech(text)
    if not clean_input:
        raise ValueError("Input text is empty after sanitization.")

    selected_voice = voice or settings.TTS_VOICE or "bm_george"
    selected_speed = speed if speed is not None else settings.TTS_SPEED

    target_url = f"{settings.TTS_BASE_URL.rstrip('/')}/v1/audio/speech"
    payload = {
        "model": "kokoro",
        "input": clean_input,
        "voice": selected_voice,
        "speed": selected_speed,
        "response_format": response_format,
    }

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(target_url, json=payload)
            if response.status_code != 200:
                error_msg = f"TTS Service responded with status {response.status_code}: {response.text}"
                logger.error(f"❌ {error_msg}")
                raise RuntimeError(error_msg)
            return response.content
    except httpx.ConnectError:
        error_msg = (
            f"Cannot connect to Kokoro TTS service at '{settings.TTS_BASE_URL}'. "
            "Please ensure the 'tts' docker container or local Kokoro service is running."
        )
        logger.error(f"❌ {error_msg}")
        raise RuntimeError(error_msg)
    except httpx.TimeoutException:
        error_msg = f"Kokoro TTS service timed out at '{settings.TTS_BASE_URL}'."
        logger.error(f"❌ {error_msg}")
        raise RuntimeError(error_msg)
    except Exception as e:
        logger.error(f"❌ Unexpected error in generate_speech: {e}")
        raise


async def check_tts_health() -> Dict[str, Any]:
    """
    Checks whether the Kokoro TTS service is reachable and responsive.
    """
    target_url = f"{settings.TTS_BASE_URL.rstrip('/')}/v1/models"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(target_url)
            if response.status_code == 200:
                return {
                    "status": "connected",
                    "base_url": settings.TTS_BASE_URL,
                    "default_voice": settings.TTS_VOICE,
                }
            return {
                "status": "error",
                "status_code": response.status_code,
                "base_url": settings.TTS_BASE_URL,
            }
    except Exception as e:
        return {
            "status": "offline",
            "base_url": settings.TTS_BASE_URL,
            "error": str(e),
        }
