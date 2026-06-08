import hashlib

import streamlit as st
from app.config import (AGENT_NAME, COMPANY_NAME, DEFAULT_LANGUAGE, MOCK_MODE,
                        VOICE_ENABLED)
from app.conversation_manager import (ConversationState, build_greeting,
                                      process_message)
from app.escalation import escalate
from app.intent_detector import analyze_intent
from app.storage import load_conversations, save_conversation
from app.stt import speech_to_text
from app.summary_generator import generate_summary
from app.utils import (confidence_bar, intent_label, load_customers,
                       sentiment_emoji, truncate)
from app.voice import text_to_speech

st.set_page_config(
    page_title=f"{COMPANY_NAME} AI Support",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

_CSS = """
<style>
[data-testid="stChatMessage"] {
    border-radius: 12px;
    padding: 8px 12px;
    margin-bottom: 4px;
}
.dashboard-card {
    background: #f8f9fa;
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 12px;
    border-left: 4px solid #0066CC;
}
.metric-label {
    font-size: 0.75rem;
    color: #6c757d;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.metric-value {
    font-size: 1.1rem;
    font-weight: 600;
    color: #212529;
}
.sentiment-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
}
.escalation-banner {
    background: #fff3cd;
    border-left: 4px solid #ffc107;
    padding: 10px 14px;
    border-radius: 6px;
    margin: 8px 0;
}
div[data-testid="stAudio"] { margin-top: 4px; }
</style>
"""
st.markdown(_CSS, unsafe_allow_html=True)


# ── Session state helpers ────────────────────────────────────────────────────


def _init():
    defaults = {
        "conv_state": None,
        "greeted": False,
        "audio_output": None,
        "last_audio_hash": "",
        "voice_on": VOICE_ENABLED,
        "pending_summary": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _start_conversation(customer: dict, language: str):
    st.session_state.conv_state = ConversationState.new(
        customer=customer, language=language
    )
    st.session_state.greeted = False
    st.session_state.audio_output = None
    st.session_state.last_audio_hash = ""
    st.session_state.pending_summary = False


def _process_input(text: str):
    state: ConversationState = st.session_state.conv_state
    if not state or not text.strip():
        return

    result = analyze_intent(text, state.messages, state.language)
    state.update_from_intent(result)

    if state.should_escalate() and not state.escalated:
        state, response = escalate(state)
        state.resolved = False
    else:
        state, response = process_message(state, text)

    if st.session_state.voice_on:
        st.session_state.audio_output = text_to_speech(response)

    if state.escalated or state.turn_count % 5 == 0:
        generate_summary(state)

    st.session_state.conv_state = state


# ── Sidebar ──────────────────────────────────────────────────────────────────


def _render_sidebar():
    customers = load_customers()

    with st.sidebar:
        st.markdown(f"## 📡 {COMPANY_NAME}")
        st.caption(f"AI Support • {AGENT_NAME}")
        st.divider()

        lang_choice = st.radio(
            "Taal / Language",
            ["🇳🇱 Nederlands", "🇬🇧 English"],
            index=0 if DEFAULT_LANGUAGE == "nl" else 1,
            horizontal=True,
        )
        selected_lang = "nl" if "Nederlands" in lang_choice else "en"

        st.divider()

        customer_options = [f"{c['id']}: {c['name']}" for c in customers]
        sel = st.selectbox("👤 Klant selecteren", customer_options, index=0)
        cid = sel.split(":")[0].strip()
        selected_customer = next(c for c in customers if c["id"] == cid)

        if selected_customer.get("account_number"):
            with st.expander("Klantgegevens", expanded=False):
                c = selected_customer
                st.caption(f"**Pakket:** {c.get('plan_name', '—')}")
                st.caption(f"**Klantnr:** {c.get('account_number', '—')}")
                st.caption(f"**Status:** {c.get('status', '—')}")
                bal = c.get("outstanding_balance", 0)
                if bal and bal > 0:
                    st.warning(f"⚠️ Openstaand: €{bal:.2f}")
                if c.get("last_support"):
                    st.caption(f"**Laatste contact:** {c['last_support']}")
                if c.get("notes"):
                    st.info(c["notes"])

        if st.button("🔄 Nieuw gesprek", use_container_width=True, type="primary"):
            _start_conversation(selected_customer, selected_lang)
            st.rerun()

        st.divider()
        st.session_state.voice_on = st.toggle(
            "🔊 Stem output (ElevenLabs)",
            value=VOICE_ENABLED,
            disabled=not VOICE_ENABLED,
            help=(
                "Vereist ELEVENLABS_API_KEY"
                if not VOICE_ENABLED
                else "Schakel spraakreactie in/uit"
            ),
        )

        if MOCK_MODE:
            st.warning(
                "**Mock modus actief.**\n\n"
                "Stel `OPENAI_API_KEY` in het `.env` bestand "
                "in voor echte AI-responses.",
                icon="⚠️",
            )

        st.divider()
        recent = load_conversations(limit=5)
        if recent:
            st.caption("🕑 Recente gesprekken")
            for conv in recent:
                name = conv.get("customer", {}).get("name", "Onbekend")
                issue = conv.get("key_issue", "—")
                st.caption(f"• **{name}** — {truncate(issue, 40)}")


# ── Dashboard ────────────────────────────────────────────────────────────────


def _render_dashboard():
    state: ConversationState = st.session_state.conv_state
    lang = state.language if state else DEFAULT_LANGUAGE

    st.subheader("📊 Live Dashboard")

    if not state or state.turn_count == 0:
        st.info(
            "Start een gesprek om het dashboard te zien."
            if lang == "nl"
            else "Start a conversation to see the dashboard."
        )
        return

    col1, col2 = st.columns(2)
    with col1:
        st.metric(
            "Probleem" if lang == "nl" else "Issue",
            intent_label(state.intent, lang),
        )
        st.metric(
            "Vertrouwen" if lang == "nl" else "Confidence",
            f"{state.confidence:.0%}",
        )
    with col2:
        emoji = sentiment_emoji(state.sentiment)
        st.metric(
            "Sentiment",
            f"{emoji} {state.sentiment.capitalize()}",
        )
        turns_label = "Gespreksbeurten" if lang == "nl" else "Turns"
        st.metric(turns_label, state.turn_count)

    st.caption(
        f"{'Zekerheid' if lang == 'nl' else 'Confidence'}: "
        f"`{confidence_bar(state.confidence)}` {state.confidence:.0%}"
    )
    st.divider()

    if state.key_issue:
        st.markdown(
            f"**{'Kerngprobleem' if lang == 'nl' else 'Key issue'}:** "
            f"{state.key_issue}"
        )

    if state.troubleshooting_step > 0:
        max_steps = 6
        progress = min(state.troubleshooting_step / max_steps, 1.0)
        label = (
            f"Stap {state.troubleshooting_step}"
            if lang == "nl"
            else f"Step {state.troubleshooting_step}"
        )
        st.caption(label)
        st.progress(progress)

    if state.escalated:
        st.error(
            "🚨 **Geëscaleerd** — verbinden met menselijke medewerker"
            if lang == "nl"
            else "🚨 **Escalated** — connecting to human agent"
        )
    elif state.should_escalate():
        st.warning(
            "⚠️ Escalatie aanbevolen" if lang == "nl" else "⚠️ Escalation recommended"
        )
    else:
        st.success(
            "✅ Actief in behandeling"
            if lang == "nl"
            else "✅ Active — handling in progress"
        )

    st.divider()

    if state.summary:
        with st.expander(
            "📋 Supportrapportage" if lang == "nl" else "📋 Support Report",
            expanded=state.escalated,
        ):
            s = state.summary
            fields_nl = [
                ("klant_probleem", "Probleem"),
                ("ondernomen_stappen", "Stappen"),
                ("waarschijnlijke_oorzaak", "Oorzaak"),
                ("aanbevolen_actie", "Aanbeveling"),
                ("urgentie", "Urgentie"),
                ("opgelost", "Opgelost"),
                ("klanttevredenheid", "Klanttevredenheid"),
            ]
            fields_en = [
                ("customer_issue", "Issue"),
                ("steps_taken", "Steps taken"),
                ("likely_cause", "Likely cause"),
                ("recommended_action", "Recommendation"),
                ("urgency", "Urgency"),
                ("resolved", "Resolved"),
                ("customer_satisfaction", "Satisfaction"),
            ]
            fields = fields_nl if lang == "nl" else fields_en
            for key, label in fields:
                val = s.get(key)
                if val is None:
                    continue
                if isinstance(val, list):
                    st.markdown(f"**{label}:**")
                    for item in val:
                        st.markdown(f"  - {item}")
                elif isinstance(val, bool):
                    st.markdown(f"**{label}:** {'✅ Ja' if val else '❌ Nee'}")
                else:
                    st.markdown(f"**{label}:** {val}")

        if "handoff_note" in state.summary:
            with st.expander("📤 Overdrachtsnotitie", expanded=False):
                st.markdown(state.summary["handoff_note"])

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button(
            "📋 Genereer rapport" if lang == "nl" else "📋 Generate report",
            use_container_width=True,
        ):
            with st.spinner("Bezig..." if lang == "nl" else "Generating..."):
                generate_summary(state)
            st.rerun()
    with col_b:
        if state.turn_count > 0:
            if st.button(
                "💾 Opslaan" if lang == "nl" else "💾 Save",
                use_container_width=True,
            ):
                path = save_conversation(state)
                st.success("✅ Opgeslagen")
                st.caption(path)


# ── Chat area ────────────────────────────────────────────────────────────────


def _render_chat():
    state: ConversationState = st.session_state.conv_state
    if not state:
        return

    lang = state.language

    if not st.session_state.greeted:
        greeting = build_greeting(state)
        state.messages.append({"role": "assistant", "content": greeting})
        st.session_state.greeted = True
        st.session_state.conv_state = state
        if st.session_state.voice_on:
            st.session_state.audio_output = text_to_speech(greeting)

    chat_container = st.container(height=420)
    with chat_container:
        for msg in state.messages:
            role = msg["role"]
            avatar = "🎧" if role == "assistant" else "👤"
            with st.chat_message(role, avatar=avatar):
                st.markdown(msg["content"])

    if st.session_state.audio_output:
        st.audio(
            st.session_state.audio_output,
            format="audio/mp3",
            autoplay=True,
        )
        st.session_state.audio_output = None

    st.divider()

    audio_col, _ = st.columns([2, 1])
    with audio_col:
        audio_label = (
            "🎤 Spreek uw vraag in" if lang == "nl" else "🎤 Record your message"
        )
        try:
            audio_input = st.audio_input(audio_label)
            if audio_input is not None:
                raw = audio_input.read()
                h = hashlib.md5(raw).hexdigest()
                if h != st.session_state.last_audio_hash:
                    st.session_state.last_audio_hash = h
                    with st.spinner(
                        "Transcriberen…" if lang == "nl" else "Transcribing…"
                    ):
                        text = speech_to_text(raw, lang)
                    if text and not text.startswith("["):
                        st.caption(
                            f"🎙️ {'Herkend' if lang == 'nl' else 'Heard'}: " f"*{text}*"
                        )
                        _process_input(text)
                        st.rerun()
                    else:
                        st.warning(text)
        except AttributeError:
            st.caption(
                "Upgrade Streamlit (≥1.38) voor microfooninvoer."
                if lang == "nl"
                else "Upgrade Streamlit (≥1.38) for microphone input."
            )

    placeholder = "Type uw bericht hier…" if lang == "nl" else "Type your message…"
    if prompt := st.chat_input(placeholder):
        _process_input(prompt)
        st.rerun()


# ── Entry point ──────────────────────────────────────────────────────────────


def main():
    _init()

    st.warning(
        "⚠️ **Demo prototype** — Dit is geen echte TelecomNL klantenservice. "
        "Uitsluitend bedoeld voor demonstratiedoeleinden."
        if (
            st.session_state.conv_state is None
            or st.session_state.conv_state.language == "nl"
        )
        else (
            "⚠️ **Demo prototype** — This is not a real TelecomNL service. "
            "For demonstration purposes only."
        ),
        icon="⚠️",
    )

    st.title(f"📡 {COMPANY_NAME} — AI Klantenservice")
    st.caption(f"Powered by GPT-4o + ElevenLabs • Agent: {AGENT_NAME}")

    if st.session_state.conv_state is None:
        customers = load_customers()
        _start_conversation(customers[0], DEFAULT_LANGUAGE)

    _render_sidebar()

    col_chat, col_dash = st.columns([3, 2], gap="large")
    with col_chat:
        _render_chat()
    with col_dash:
        _render_dashboard()


if __name__ == "__main__":
    main()
