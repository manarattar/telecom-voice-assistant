import json
import re

from app.config import MOCK_MODE, OPENAI_API_KEY, OPENAI_MODEL
from openai import OpenAI

_client = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def chat(messages: list[dict], temperature: float = 0.7) -> str:
    if MOCK_MODE:
        return _mock_response(messages)
    try:
        response = get_client().chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"[LLM fout: {e}]"


def chat_json(messages: list[dict], temperature: float = 0.0) -> dict:
    if MOCK_MODE:
        return _mock_intent()
    try:
        response = get_client().chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        return json.loads(raw)
    except Exception as e:
        return {"error": str(e)}


def _mock_response(messages: list[dict]) -> str:
    last = messages[-1]["content"].lower() if messages else ""
    if any(w in last for w in ["wifi", "draadloos", "wireless"]):
        return "Ik begrijp dat u problemen heeft met uw WiFi. Kunt u mij vertellen: speelt het probleem op alle apparaten of slechts één?"
    if any(w in last for w in ["internet", "verbinding", "connection"]):
        return "Vervelend dat uw internet niet werkt. Heeft u al geprobeerd de modem opnieuw op te starten?"
    if any(w in last for w in ["factuur", "bill", "rekening", "betaling"]):
        return "Ik help u graag met uw factuurvraag. Heeft u een specifieke factuur of periode waarnaar u vraagt?"
    if any(w in last for w in ["sim", "mobiel", "data", "mobile"]):
        return "Ik help u graag met het mobiele probleem. Kunt u controleren of de vliegtuigmodus uitgeschakeld is?"
    return (
        "Bedankt voor uw bericht. Kunt u mij vertellen wat voor probleem u ondervindt?"
    )


def _mock_intent() -> dict:
    return {
        "intent": "unknown",
        "confidence": 0.5,
        "sentiment": "neutral",
        "frustration_level": 1,
        "escalation_needed": False,
        "key_issue": "Mock mode — geen analyse beschikbaar",
        "language_detected": "nl",
    }


def extract_json_from_text(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return {}
