import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
CONVERSATIONS_DIR = BASE_DIR / "conversations"
ASSETS_DIR = BASE_DIR / "assets"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "nl")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")


def _is_configured(key: str) -> bool:
    """True only for a real key — an unedited .env.example placeholder doesn't count."""
    return bool(key) and "..." not in key and len(key) > 20


MOCK_MODE = not _is_configured(OPENAI_API_KEY)
VOICE_ENABLED = _is_configured(ELEVENLABS_API_KEY)

AGENT_NAME = "Sarah"
COMPANY_NAME = "TelecomNL"

ESCALATION_TURN_LIMIT = 6
# Must match the threshold the intent prompt uses for escalation_needed
# (see intent_detector.py). At 3 an ordinary complaint escalates on turn one.
FRUSTRATION_ESCALATION_THRESHOLD = 4
MIN_CONFIDENCE_THRESHOLD = 0.25

BACKEND_URL = os.getenv("BACKEND_URL", "https://telecom-voice-assistant.onrender.com")
