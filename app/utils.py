import json

from app.config import DATA_DIR

_customers_cache: list = []


def load_customers() -> list[dict]:
    global _customers_cache
    if not _customers_cache:
        path = DATA_DIR / "fake_customers.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                _customers_cache = json.load(f)
    return _customers_cache


def get_customer_by_id(customer_id: str) -> dict | None:
    for c in load_customers():
        if c.get("id") == customer_id:
            return c
    return None


def sentiment_emoji(sentiment: str) -> str:
    return {
        "positive": "😊",
        "neutral": "😐",
        "frustrated": "😤",
        "angry": "😡",
    }.get(sentiment, "😐")


def sentiment_color(sentiment: str) -> str:
    return {
        "positive": "#2ecc71",
        "neutral": "#95a5a6",
        "frustrated": "#e67e22",
        "angry": "#e74c3c",
    }.get(sentiment, "#95a5a6")


def intent_label(intent: str, language: str = "nl") -> str:
    labels = {
        "nl": {
            "wifi_slow": "Trage WiFi",
            "wifi_down": "WiFi storing",
            "internet_down": "Geen internet",
            "internet_unstable": "Onstabiel internet",
            "mobile_data": "Mobiele data",
            "sim_activation": "SIM activering",
            "billing": "Factuurvraag",
            "subscription_change": "Abonnementswijziging",
            "contract": "Contractvraag",
            "outage": "Regionale storing",
            "escalation": "Escalatie gevraagd",
            "unknown": "Onbekend",
        },
        "en": {
            "wifi_slow": "Slow WiFi",
            "wifi_down": "WiFi outage",
            "internet_down": "No internet",
            "internet_unstable": "Unstable internet",
            "mobile_data": "Mobile data",
            "sim_activation": "SIM activation",
            "billing": "Billing question",
            "subscription_change": "Subscription change",
            "contract": "Contract question",
            "outage": "Regional outage",
            "escalation": "Escalation requested",
            "unknown": "Unknown",
        },
    }
    return labels.get(language, labels["nl"]).get(intent, intent)


def confidence_bar(confidence: float) -> str:
    filled = int(confidence * 10)
    return "█" * filled + "░" * (10 - filled)


def truncate(text: str, max_len: int = 80) -> str:
    return text if len(text) <= max_len else text[:max_len] + "…"
