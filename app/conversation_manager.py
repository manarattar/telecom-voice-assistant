import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from app.config import (AGENT_NAME, COMPANY_NAME, DATA_DIR, DEFAULT_LANGUAGE,
                        ESCALATION_TURN_LIMIT,
                        FRUSTRATION_ESCALATION_THRESHOLD)
from app.intent_detector import IntentResult
from app.llm import chat

KB_PATH = DATA_DIR / "knowledge_base.json"
_kb_cache: dict = {}


def _load_kb() -> dict:
    global _kb_cache
    if not _kb_cache and KB_PATH.exists():
        with open(KB_PATH, encoding="utf-8") as f:
            _kb_cache = json.load(f)
    return _kb_cache


@dataclass
class ConversationState:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    customer: dict = field(default_factory=dict)
    language: str = DEFAULT_LANGUAGE
    messages: list[dict] = field(default_factory=list)
    intent: str = "unknown"
    confidence: float = 0.0
    sentiment: str = "neutral"
    frustration_level: int = 1
    escalation_needed: bool = False
    key_issue: str = ""
    troubleshooting_step: int = 0
    resolved: bool = False
    escalated: bool = False
    turn_count: int = 0
    summary: dict = field(default_factory=dict)
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @classmethod
    def new(cls, customer: dict = None, language: str = DEFAULT_LANGUAGE):
        state = cls(language=language, customer=customer or {})
        return state

    def update_from_intent(self, result: IntentResult) -> None:
        self.intent = result.intent
        self.confidence = result.confidence
        self.sentiment = result.sentiment
        self.frustration_level = result.frustration_level
        self.key_issue = result.key_issue
        if result.language_detected in ("nl", "en"):
            self.language = result.language_detected
        if result.escalation_needed:
            self.escalation_needed = True

    def should_escalate(self) -> bool:
        if self.escalated:
            return False
        if self.escalation_needed:
            return True
        if self.frustration_level >= FRUSTRATION_ESCALATION_THRESHOLD:
            return True
        if self.turn_count >= ESCALATION_TURN_LIMIT:
            return True
        return False


def _build_system_prompt(state: ConversationState) -> str:
    kb = _load_kb()
    lang = state.language
    company = kb.get("company", {})

    kb_section = ""
    if state.intent and state.intent != "unknown":
        cat = kb.get("categories", {}).get(state.intent, {})
        if cat:
            steps = cat.get("troubleshooting_checklist", [])
            solutions = cat.get("common_solutions", [])
            steps_text = "\n".join(f"  - {s}" for s in steps)
            sol_text = "\n".join(f"  - {s}" for s in solutions)
            kb_section = (
                f"\nRELEVANTE KENNISBANK ({state.intent}):\n"
                f"Troubleshooting stappen:\n{steps_text}\n"
                f"Oplossingen:\n{sol_text}\n"
            )

    customer_info = ""
    if state.customer and state.customer.get("name"):
        c = state.customer
        customer_info = (
            f"\nKLANTINFORMATIE:\n"
            f"  Naam: {c.get('name')}\n"
            f"  Klantnummer: {c.get('account_number', 'onbekend')}\n"
            f"  Pakket: {c.get('plan_name', 'onbekend')}\n"
            f"  Status: {c.get('status', 'onbekend')}\n"
            f"  Openstaand bedrag: €{c.get('outstanding_balance', 0):.2f}\n"
            f"  Laatste contact: {c.get('last_support', 'geen')}\n"
            f"  Opmerking: {c.get('notes', '')}\n"
        )

    if lang == "nl":
        lang_instruction = (
            "Spreek ALTIJD Nederlands tenzij de klant expliciet "
            "Engels spreekt of vraagt."
        )
        tone = (
            "professioneel maar vriendelijk, zoals een echte "
            "klantenservicemedewerker"
        )
    else:
        lang_instruction = "Always speak English unless the customer switches to Dutch."
        tone = "professional yet friendly, like a real customer support agent"

    escalation_note = ""
    if state.escalated:
        escalation_note = (
            "\nLET OP: Dit gesprek is geëscaleerd. "
            "Bevestig de escalatie en vat het probleem samen."
        )

    return f"""Je bent {AGENT_NAME}, een klantenservicemedewerker van {COMPANY_NAME}.
{lang_instruction}
Toon: {tone}

BEDRIJFSINFORMATIE:
  Support: {company.get('support_phone', '0800-1234')} \
({company.get('support_hours', 'Ma-Za 08:00-22:00')})
  Spoedlijn bij storingen: {company.get('emergency_outage', '0800-5678')}
{customer_info}{kb_section}
GEDRAGSREGELS:
1. Stel PRECIES ÉÉN vraag per bericht — geen meerdere vragen tegelijk.
2. Wees empathisch bij frustratie. Erken het probleem eerst.
3. Volg de troubleshooting stappen logisch en systematisch.
4. Vraag om bevestiging na elke stap voordat je verder gaat.
5. Bied escalatie aan na {ESCALATION_TURN_LIMIT} beurten zonder oplossing.
6. Noem de klant bij naam als je die kent.
7. Wees bondig: max 3-4 zinnen per antwoord.
8. Sluit elk gesprek af met een samenvatting en vervolgstap.{escalation_note}"""


def process_message(
    state: ConversationState, user_message: str
) -> tuple[ConversationState, str]:
    state.messages.append({"role": "user", "content": user_message})
    state.turn_count += 1
    state.troubleshooting_step += 1

    system = _build_system_prompt(state)
    full_messages = [{"role": "system", "content": system}] + state.messages

    response = chat(full_messages, temperature=0.65)

    state.messages.append({"role": "assistant", "content": response})
    return state, response


def build_greeting(state: ConversationState) -> str:
    lang = state.language
    name = state.customer.get("name", "") if state.customer else ""
    company = COMPANY_NAME

    if lang == "nl":
        greeting = f"Goedendag{', ' + name if name else ''}! "
        greeting += (
            f"U spreekt met {AGENT_NAME} van {company}. " "Hoe kan ik u vandaag helpen?"
        )
    else:
        greeting = f"Good day{', ' + name if name else ''}! "
        greeting += (
            f"You're speaking with {AGENT_NAME} from {company}. "
            "How can I help you today?"
        )
    return greeting
