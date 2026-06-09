"""
ElevenLabs Conversational AI agent lifecycle.
Creates one persistent agent per persona (Sarah / Alex / Nina),
caches their ElevenLabs agent IDs in data/el_agent_ids.json,
and issues per-session signed WebSocket URLs.
"""

import json
from pathlib import Path

import requests

from app.agents import get_agent
from app.config import COMPANY_NAME, ELEVENLABS_API_KEY, ESCALATION_TURN_LIMIT

_BASE = "https://api.elevenlabs.io"
_CACHE = Path("data") / "el_agent_ids.json"


# ── HTTP helpers ──────────────────────────────────────────────────────────────


def _h() -> dict:
    return {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}


def _load_cache() -> dict:
    try:
        return json.loads(_CACHE.read_text())
    except Exception:
        return {}


def _save_cache(data: dict) -> None:
    _CACHE.parent.mkdir(exist_ok=True)
    _CACHE.write_text(json.dumps(data, indent=2))


# ── Tool definitions (webhook-based) ─────────────────────────────────────────


def _tool_defs(backend_url: str) -> list[dict]:
    base = backend_url.rstrip("/") + "/api/tools"

    def _webhook(name: str, description: str) -> dict:
        return {
            "type": "webhook",
            "name": name,
            "description": description,
            "api_schema": {
                "url": f"{base}/{name}",
                "method": "POST",
                "request_body_schema": {
                    "type": "object",
                    "properties": {
                        "account_id": {
                            "type": "string",
                            "description": "Customer account number",
                        }
                    },
                    "required": ["account_id"],
                },
            },
        }

    return [
        _webhook(
            "check_line_quality",
            "Check real-time line quality and diagnostics for a customer. "
            "Use for slow internet, disconnections, or unstable connection.",
        ),
        _webhook(
            "restart_modem",
            "Remotely restart the customer's modem/router. "
            "Use after basic troubleshooting fails.",
        ),
        _webhook(
            "check_area_outage",
            "Check for known outages in the customer's area. "
            "Use when customer reports complete internet outage.",
        ),
        _webhook(
            "lookup_account",
            "Look up account details, subscription plan, billing, and open tickets.",
        ),
    ]


# ── System prompt ─────────────────────────────────────────────────────────────


def _system_prompt(agent) -> str:
    if agent.default_language == "en":
        return (
            f"You are {agent.name}, a customer service agent at {COMPANY_NAME}.\n"
            f"Personality: {agent.personality}\n\n"
            "LANGUAGE: Always speak English unless the customer switches to Dutch.\n\n"
            "RULES:\n"
            "1. Ask exactly ONE question per turn.\n"
            "2. Be empathetic first — acknowledge the problem before troubleshooting.\n"
            "3. Follow troubleshooting steps logically; confirm each step before continuing.\n"
            f"4. Offer escalation to a human after {ESCALATION_TURN_LIMIT} turns"
            " without resolution.\n"
            "5. Address the customer by name when you know it.\n"
            "6. Keep responses to 1-2 sentences — this is a VOICE conversation.\n"
            "7. Use diagnostic tools proactively for technical issues.\n"
            "CUSTOMER INFO: injected at conversation start via system context."
        )
    return (
        f"Je bent {agent.name}, een klantenservicemedewerker van {COMPANY_NAME}.\n"
        f"Persoonlijkheid: {agent.personality}\n\n"
        "TAAL: Spreek ALTIJD Nederlands tenzij de klant expliciet Engels spreekt.\n\n"
        "GEDRAGSREGELS:\n"
        "1. Stel precies ÉÉN vraag per bericht.\n"
        "2. Erken eerst het probleem voor je begint te troubleshooten.\n"
        "3. Volg troubleshooting-stappen logisch; bevestig elke stap voor je verdergaat.\n"
        f"4. Bied escalatie aan naar een menselijke medewerker na {ESCALATION_TURN_LIMIT} "
        "beurten zonder oplossing.\n"
        "5. Spreek de klant bij naam aan als je die kent.\n"
        "6. Houd antwoorden op 1-2 zinnen — dit is een GESPROKEN conversatie.\n"
        "7. Gebruik diagnostische tools proactief bij technische problemen.\n"
        "KLANTINFO: wordt aan het begin van elk gesprek via systeemcontext meegegeven."
    )


# ── Agent creation ────────────────────────────────────────────────────────────


def _create_agent(agent_id: str, backend_url: str) -> str:
    agent = get_agent(agent_id)
    payload = {
        "name": f"TelecomNL-{agent.name}",
        "conversation_config": {
            "agent": {
                "prompt": {
                    "prompt": _system_prompt(agent),
                    "llm": "gpt-4o",
                    "temperature": 0.65,
                    "tools": _tool_defs(backend_url),
                },
                "first_message": "",  # overridden per-session
                "language": agent.default_language,
            },
            "tts": {
                "model_id": (
                    "eleven_multilingual_v2"
                    if agent.default_language == "en"
                    else "eleven_turbo_v2_5"
                ),
                "voice_id": agent.elevenlabs_voice_id,
                "stability": 0.50,
                "similarity_boost": 0.75,
                "agent_output_audio_format": "pcm_16000",
            },
            "asr": {
                "quality": "high",
                "user_input_audio_format": "pcm_16000",
            },
            "turn": {
                "turn_timeout": 8,
                "silence_end_call_timeout": 60,
            },
        },
    }

    r = requests.post(
        f"{_BASE}/v1/convai/agents/create",
        headers=_h(),
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["agent_id"]


# ── Public API ────────────────────────────────────────────────────────────────


def build_agent_prompt(agent, customer_ctx: str = "") -> str:
    """Full system prompt for a session — base personality + customer context."""
    return _system_prompt(agent) + customer_ctx


def get_or_create_agent(agent_id: str, backend_url: str) -> str:
    """Return ElevenLabs agent ID for this persona, creating it if not cached."""
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY not set")
    cache = _load_cache()
    if agent_id in cache:
        return cache[agent_id]
    el_id = _create_agent(agent_id, backend_url)
    cache[agent_id] = el_id
    _save_cache(cache)
    return el_id


def get_signed_url(el_agent_id: str) -> str:
    """Issue an ephemeral signed WebSocket URL for a private session."""
    r = requests.get(
        f"{_BASE}/v1/convai/conversation/get_signed_url",
        params={"agent_id": el_agent_id},
        headers=_h(),
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["signed_url"]


def delete_cached_agents() -> None:
    """Clear the cache so agents will be recreated on next call. For dev use."""
    if _CACHE.exists():
        _CACHE.unlink()
