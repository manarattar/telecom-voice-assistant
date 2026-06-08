from dataclasses import dataclass, field

from app.llm import chat_json


@dataclass
class IntentResult:
    intent: str = "unknown"
    confidence: float = 0.5
    sentiment: str = "neutral"
    frustration_level: int = 1
    escalation_needed: bool = False
    key_issue: str = ""
    language_detected: str = "nl"


VALID_INTENTS = {
    "wifi_slow",
    "wifi_down",
    "internet_down",
    "internet_unstable",
    "mobile_data",
    "sim_activation",
    "billing",
    "subscription_change",
    "contract",
    "outage",
    "escalation",
    "unknown",
}

VALID_SENTIMENTS = {"positive", "neutral", "frustrated", "angry"}


def analyze_intent(
    user_message: str,
    conversation_history: list[dict],
    language: str = "nl",
) -> IntentResult:
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in conversation_history[-6:]
    )
    prompt = f"""Analyseer het volgende klantgesprek bij een telecomprovider.

GESPREK:
{history_text}
LAATSTE BERICHT: {user_message}

Geef een JSON-object terug met EXACT deze velden:
{{
  "intent": "<een van: wifi_slow, wifi_down, internet_down, internet_unstable, \
mobile_data, sim_activation, billing, subscription_change, contract, outage, \
escalation, unknown>",
  "confidence": <getal 0.0-1.0>,
  "sentiment": "<een van: positive, neutral, frustrated, angry>",
  "frustration_level": <getal 1-5>,
  "escalation_needed": <true of false>,
  "key_issue": "<korte omschrijving van het probleem in 1 zin>",
  "language_detected": "<nl of en>"
}}

Regels:
- escalation_needed=true als: klant boos is (frustration_level>=4), \
probleem niet oplosbaar lijkt, of klant expliciet om medewerker vraagt
- confidence geeft aan hoe zeker je bent van de intent (0=onzeker, 1=zeker)
- Beantwoord ALLEEN met JSON, geen tekst eromheen."""

    raw = chat_json([{"role": "user", "content": prompt}], temperature=0.0)

    intent = raw.get("intent", "unknown")
    if intent not in VALID_INTENTS:
        intent = "unknown"

    sentiment = raw.get("sentiment", "neutral")
    if sentiment not in VALID_SENTIMENTS:
        sentiment = "neutral"

    return IntentResult(
        intent=intent,
        confidence=float(raw.get("confidence", 0.5)),
        sentiment=sentiment,
        frustration_level=int(raw.get("frustration_level", 1)),
        escalation_needed=bool(raw.get("escalation_needed", False)),
        key_issue=str(raw.get("key_issue", "")),
        language_detected=str(raw.get("language_detected", language)),
    )
