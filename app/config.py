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

MOCK_MODE = not bool(OPENAI_API_KEY)
VOICE_ENABLED = bool(ELEVENLABS_API_KEY)

AGENT_NAME = "Sarah"
COMPANY_NAME = "TelecomNL"

ESCALATION_TURN_LIMIT = 6
FRUSTRATION_ESCALATION_THRESHOLD = 3
MIN_CONFIDENCE_THRESHOLD = 0.25
