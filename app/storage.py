import json
from datetime import datetime

from app.config import CONVERSATIONS_DIR
from app.conversation_manager import ConversationState


def save_conversation(state: ConversationState) -> str:
    CONVERSATIONS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"conv_{state.session_id}_{timestamp}.json"
    path = CONVERSATIONS_DIR / filename

    data = {
        "session_id": state.session_id,
        "started_at": state.started_at,
        "saved_at": datetime.now().isoformat(),
        "customer": state.customer,
        "language": state.language,
        "intent": state.intent,
        "confidence": state.confidence,
        "sentiment": state.sentiment,
        "frustration_level": state.frustration_level,
        "key_issue": state.key_issue,
        "turn_count": state.turn_count,
        "resolved": state.resolved,
        "escalated": state.escalated,
        "summary": state.summary,
        "messages": state.messages,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return str(path)


def load_conversations(limit: int = 20) -> list[dict]:
    if not CONVERSATIONS_DIR.exists():
        return []
    files = sorted(CONVERSATIONS_DIR.glob("conv_*.json"), reverse=True)
    results = []
    for f in files[:limit]:
        try:
            with open(f, encoding="utf-8") as fp:
                results.append(json.load(fp))
        except Exception:
            continue
    return results
