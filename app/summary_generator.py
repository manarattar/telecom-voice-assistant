from app.conversation_manager import ConversationState
from app.llm import chat


def generate_summary(state: ConversationState) -> dict:
    if not state.messages:
        return {}

    history = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in state.messages)
    lang = state.language
    customer_name = (
        state.customer.get("name", "Onbekend") if state.customer else "Onbekend"
    )
    account = (
        state.customer.get("account_number", "Onbekend")
        if state.customer
        else "Onbekend"
    )

    if lang == "nl":
        prompt = f"""Genereer een professionele supportrapportage voor een telecomgesprek.

KLANTGEGEVENS:
- Naam: {customer_name}
- Klantnummer: {account}
- Intent: {state.intent}
- Sentiment: {state.sentiment}
- Geëscaleerd: {"Ja" if state.escalated else "Nee"}
- Gespreksbeurten: {state.turn_count}

GESPREKSVERLOOP:
{history}

Maak een JSON-object met deze velden:
{{
  "klant_probleem": "Samenvatting van het probleem in 1-2 zinnen",
  "ondernomen_stappen": ["stap 1", "stap 2", "stap 3"],
  "waarschijnlijke_oorzaak": "Meest waarschijnlijke oorzaak",
  "aanbevolen_actie": "Concrete vervolgstap voor klant of medewerker",
  "opgelost": true of false,
  "escalatie_nodig": true of false,
  "urgentie": "Laag / Normaal / Hoog",
  "gespreksduur": "{state.turn_count} beurten",
  "klanttevredenheid": "Positief / Neutraal / Negatief"
}}
Antwoord ALLEEN met JSON."""
    else:
        prompt = f"""Generate a professional support report for a telecom conversation.

CUSTOMER INFO:
- Name: {customer_name}
- Account: {account}
- Intent: {state.intent}
- Sentiment: {state.sentiment}
- Escalated: {"Yes" if state.escalated else "No"}
- Turns: {state.turn_count}

CONVERSATION:
{history}

Return a JSON object with these fields:
{{
  "customer_issue": "Summary of the issue in 1-2 sentences",
  "steps_taken": ["step 1", "step 2", "step 3"],
  "likely_cause": "Most probable root cause",
  "recommended_action": "Concrete next step for customer or agent",
  "resolved": true or false,
  "escalation_needed": true or false,
  "urgency": "Low / Normal / High",
  "conversation_length": "{state.turn_count} turns",
  "customer_satisfaction": "Positive / Neutral / Negative"
}}
Reply ONLY with JSON."""

    from app.llm import chat_json

    raw = chat_json([{"role": "user", "content": prompt}], temperature=0.0)

    if "error" not in raw:
        state.summary.update(raw)

    return raw
