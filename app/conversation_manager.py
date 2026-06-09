import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.agents import DEFAULT_AGENT_ID, get_agent
from app.config import (COMPANY_NAME, DATA_DIR, DEFAULT_LANGUAGE,
                        ESCALATION_TURN_LIMIT,
                        FRUSTRATION_ESCALATION_THRESHOLD)
from app.intent_detector import IntentResult
from app.llm import chat, chat_stream, chat_with_tools
from app.tools import TOOLS_SCHEMA, execute_tool, tool_icon, tool_label

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
    agent_id: str = DEFAULT_AGENT_ID
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
    def new(
        cls,
        customer: dict = None,
        language: str = DEFAULT_LANGUAGE,
        agent_id: str = DEFAULT_AGENT_ID,
    ):
        return cls(language=language, customer=customer or {}, agent_id=agent_id)

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
    agent = get_agent(state.agent_id)
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
    else:
        lang_instruction = "Always speak English unless the customer switches to Dutch."

    tools_instruction = (
        "\nDIAGNOSTISCHE TOOLS: Je hebt toegang tot real-time diagnosegereedschappen. "
        "Gebruik check_line_quality bij verbindingsproblemen, restart_modem als basis "
        "troubleshooting niet helpt, check_area_outage bij volledige uitval, en "
        "lookup_account voor factuur- of abonnementsvragen. "
        "Kondig de tool-actie aan voordat je hem uitvoert."
    )

    escalation_note = ""
    if state.escalated:
        escalation_note = (
            "\nLET OP: Dit gesprek is geëscaleerd. "
            "Bevestig de escalatie en vat het probleem samen."
        )

    agent_name = agent.name
    personality = agent.personality

    return (
        f"Je bent {agent_name}, een klantenservicemedewerker van {COMPANY_NAME}.\n"
        f"Persoonlijkheid: {personality}\n"
        f"{lang_instruction}\n"
        f"\nBEDRIJFSINFORMATIE:\n"
        f"  Support: {company.get('support_phone', '0800-1234')} "
        f"({company.get('support_hours', 'Ma-Za 08:00-22:00')})\n"
        f"  Spoedlijn: {company.get('emergency_outage', '0800-5678')}\n"
        f"{customer_info}{kb_section}{tools_instruction}\n"
        f"\nGEDRAGSREGELS:\n"
        f"1. Stel PRECIES ÉÉN vraag per bericht.\n"
        f"2. Wees empathisch bij frustratie. Erken het probleem eerst.\n"
        f"3. Volg troubleshooting stappen logisch en systematisch.\n"
        f"4. Vraag bevestiging na elke stap voordat je verder gaat.\n"
        f"5. Bied escalatie aan na {ESCALATION_TURN_LIMIT} beurten zonder oplossing.\n"
        f"6. Noem de klant bij naam als je die kent.\n"
        f"7. Wees bondig: max 3-4 zinnen per antwoord.\n"
        f"8. Gebruik diagnostische tools proactief bij technische problemen."
        f"{escalation_note}"
    )


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


def process_message_stream(state: ConversationState, user_message: str):
    """Yields text chunks (legacy — used by escalation path)."""
    state.messages.append({"role": "user", "content": user_message})
    state.turn_count += 1
    state.troubleshooting_step += 1

    system = _build_system_prompt(state)
    full_messages = [{"role": "system", "content": system}] + state.messages

    chunks: list[str] = []
    for chunk in chat_stream(full_messages, temperature=0.65):
        chunks.append(chunk)
        yield chunk

    state.messages.append({"role": "assistant", "content": "".join(chunks)})


def process_turn_with_tools(
    state: ConversationState, user_message: str, customer: dict
):
    """
    Yields structured event dicts:
      {"type": "tool_call",  "name": str, "label": str, "icon": str}
      {"type": "tool_done",  "name": str, "result": dict}
      {"type": "chunk",      "text": str}
    Updates state.messages on completion.
    """
    state.messages.append({"role": "user", "content": user_message})
    state.turn_count += 1
    state.troubleshooting_step += 1

    system = _build_system_prompt(state)
    full_messages = [{"role": "system", "content": system}] + state.messages

    msg, tool_calls = chat_with_tools(full_messages, TOOLS_SCHEMA, temperature=0.65)

    if tool_calls:
        tool_results: dict[str, dict] = {}
        tool_call_dicts = []

        for tc in tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments)
            lang = state.language

            yield {
                "type": "tool_call",
                "name": name,
                "label": tool_label(name, lang),
                "icon": tool_icon(name),
            }

            result = execute_tool(name, args, customer)
            tool_results[tc.id] = result
            tool_call_dicts.append(
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": tc.function.arguments,
                    },
                }
            )

            yield {"type": "tool_done", "name": name, "result": result}

        # Append assistant tool-call message
        full_messages.append(
            {"role": "assistant", "content": None, "tool_calls": tool_call_dicts}
        )

        # Append each tool result
        for tc in tool_calls:
            full_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(tool_results[tc.id], ensure_ascii=False),
                }
            )

        # Stream the follow-up response
        chunks: list[str] = []
        for chunk in chat_stream(full_messages, temperature=0.65):
            chunks.append(chunk)
            yield {"type": "chunk", "text": chunk}

        response = "".join(chunks)

    else:
        # No tools — fall back to regular streaming
        chunks_list: list[str] = []
        for chunk in chat_stream(full_messages, temperature=0.65):
            chunks_list.append(chunk)
            yield {"type": "chunk", "text": chunk}

        response = "".join(chunks_list)

    state.messages.append({"role": "assistant", "content": response})


def build_greeting(state: ConversationState, agent_id: str = DEFAULT_AGENT_ID) -> str:
    lang = state.language
    agent = get_agent(agent_id)
    name = state.customer.get("name", "") if state.customer else ""

    if lang == "nl":
        greeting = f"Goedendag{', ' + name if name else ''}! "
        greeting += (
            f"U spreekt met {agent.name} van {COMPANY_NAME}. "
            "Hoe kan ik u vandaag helpen?"
        )
    else:
        greeting = f"Good day{', ' + name if name else ''}! "
        greeting += (
            f"You're speaking with {agent.name} from {COMPANY_NAME}. "
            "How can I help you today?"
        )
    return greeting
