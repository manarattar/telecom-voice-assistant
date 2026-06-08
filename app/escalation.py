from app.conversation_manager import ConversationState
from app.llm import chat


def escalate(state: ConversationState) -> tuple[ConversationState, str]:
    state.escalated = True
    lang = state.language

    history = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in state.messages[-10:]
    )
    customer_name = state.customer.get("name", "klant") if state.customer else "klant"
    account = (
        state.customer.get("account_number", "onbekend")
        if state.customer
        else "onbekend"
    )

    if lang == "nl":
        prompt = f"""Je bent een klantenservicemedewerker van TelecomNL.
Genereer een korte, professionele overdrachtsnotitie voor een menselijke medewerker.

KLANT: {customer_name} | KLANTNUMMER: {account}
PROBLEEM: {state.key_issue}
SENTIMENT: {state.sentiment} | GESPREKSBEURTEN: {state.turn_count}

GESPREKSVERLOOP:
{history}

Schrijf de overdrachtsnotitie in het Nederlands. Formaat:
- Probleem in 1 zin
- Ondernomen stappen (max 3 bullets)
- Aanbevolen vervolgactie
- Urgentieniveau (Laag/Normaal/Hoog)"""
    else:
        prompt = f"""You are a TelecomNL customer service agent.
Generate a concise professional handoff note for a human agent.

CUSTOMER: {customer_name} | ACCOUNT: {account}
ISSUE: {state.key_issue}
SENTIMENT: {state.sentiment} | TURNS: {state.turn_count}

CONVERSATION:
{history}

Write the handoff note in English. Format:
- Issue in 1 sentence
- Steps taken (max 3 bullets)
- Recommended next action
- Urgency level (Low/Normal/High)"""

    note = chat([{"role": "user", "content": prompt}], temperature=0.3)
    state.summary["handoff_note"] = note

    if lang == "nl":
        msg = (
            f"Ik begrijp dat dit een vervelende situatie is, "
            f"{customer_name}. Ik verbind u nu door met een van onze "
            f"specialisten die u verder kan helpen. Uw klantnummer is "
            f"{account}. Zij zijn op de hoogte van ons gesprek, "
            f"zodat u niets opnieuw hoeft uit te leggen. Eén moment."
        )
    else:
        msg = (
            f"I understand this has been frustrating, {customer_name}. "
            f"I'm now transferring you to one of our specialists who can "
            f"assist you further. Your account number is {account}. "
            f"They'll be briefed on our conversation. One moment please."
        )

    return state, msg
