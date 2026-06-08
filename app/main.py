import base64
import hashlib

import streamlit as st
import streamlit.components.v1 as components

from app.config import (AGENT_NAME, COMPANY_NAME, DEFAULT_LANGUAGE, MOCK_MODE,
                        VOICE_ENABLED)
from app.conversation_manager import (ConversationState, build_greeting,
                                      process_message, process_message_stream)
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
.listening-banner {
    background: linear-gradient(90deg, #e3f2fd, #bbdefb);
    border-left: 4px solid #1976d2;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 8px 0;
    font-weight: 600;
    color: #0d47a1;
    animation: pulse 1.5s infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
}
</style>
"""
st.markdown(_CSS, unsafe_allow_html=True)


# ── Audio helpers ────────────────────────────────────────────────────────────


def _play_response(audio_bytes: bytes):
    """Play Sarah's response via iframe-embedded player.

    Streamlit's components.v1.html() iframe carries allow="autoplay" so the
    <audio autoplay> attribute works reliably.  Controls are always visible as
    a click-to-play fallback when the browser blocks autoplay.
    """
    b64 = base64.b64encode(audio_bytes).decode()
    size_kb = len(audio_bytes) // 1024
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:6px;background:transparent;
             font-family:-apple-system,BlinkMacSystemFont,sans-serif;">
  <div style="background:linear-gradient(90deg,#e8f5e9,#c8e6c9);
              border-left:4px solid #388e3c;border-radius:8px;
              padding:8px 14px;margin-bottom:6px;">
    <span style="color:#1b5e20;font-weight:600;font-size:13px;">
      🔊 {AGENT_NAME} &nbsp;
      <span style="font-weight:400;color:#555;font-size:11px;">
        {size_kb} KB — klik ▶ als het niet automatisch start
      </span>
    </span>
  </div>
  <audio controls autoplay id="r"
         style="width:100%;height:40px;display:block;">
    <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
  </audio>
  <script>
    var a = document.getElementById('r');
    a.play().catch(function(e) {{
      console.warn('Autoplay blocked — controls available:', e.message);
    }});
  </script>
</body>
</html>"""
    components.html(html, height=100)


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
    """Blocking path used for typed text input."""
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
        audio = text_to_speech(response)
        if audio:
            st.session_state.audio_output = audio

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
            value=st.session_state.get("voice_on", VOICE_ENABLED),
            disabled=not VOICE_ENABLED,
            help=(
                "Vereist ELEVENLABS_API_KEY"
                if not VOICE_ENABLED
                else "Schakel spraakreactie in/uit"
            ),
        )

        if MOCK_MODE:
            st.warning(
                "**Mock modus actief.**\n\nStel `OPENAI_API_KEY` in voor "
                "echte AI-responses.",
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
        st.metric("Sentiment", f"{emoji} {state.sentiment.capitalize()}")
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
        progress = min(state.troubleshooting_step / 6, 1.0)
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
                save_conversation(state)
                st.success("✅ Opgeslagen")


# ── Chat area ────────────────────────────────────────────────────────────────


def _render_chat():
    state: ConversationState = st.session_state.conv_state
    if not state:
        return

    lang = state.language

    # Send greeting on first load
    if not st.session_state.greeted:
        greeting = build_greeting(state)
        state.messages.append({"role": "assistant", "content": greeting})
        st.session_state.greeted = True
        st.session_state.conv_state = state
        if st.session_state.voice_on:
            audio = text_to_speech(greeting)
            if audio:
                st.session_state.audio_output = audio

    # Conversation history
    chat_container = st.container(height=400)
    with chat_container:
        for msg in state.messages:
            role = msg["role"]
            avatar = "🎧" if role == "assistant" else "👤"
            with st.chat_message(role, avatar=avatar):
                st.markdown(msg["content"])

    # Audio player — shown above the mic so user sees it immediately
    if st.session_state.audio_output:
        _play_response(st.session_state.audio_output)
        st.session_state.audio_output = None

    st.divider()

    # Listening indicator
    if state.turn_count > 0:
        st.markdown(
            '<div class="listening-banner">'
            + (
                "🎤 Uw beurt — druk op de microfoon en spreek"
                if lang == "nl"
                else "🎤 Your turn — click the mic and speak"
            )
            + "</div>",
            unsafe_allow_html=True,
        )

    # ── Voice input (streaming path) ─────────────────────────────────────────
    try:
        audio_label = (
            "🎤 Spreek uw vraag in" if lang == "nl" else "🎤 Record your message"
        )
        audio_input = st.audio_input(audio_label)
        if audio_input is not None:
            raw = audio_input.read()
            h = hashlib.md5(raw).hexdigest()
            if h != st.session_state.last_audio_hash:
                st.session_state.last_audio_hash = h

                # Stage 1 — transcribe
                status = st.empty()
                status.markdown(
                    "🎙️ **Transcriberen…**" if lang == "nl" else "🎙️ **Transcribing…**"
                )
                text = speech_to_text(raw, lang)
                status.empty()

                if text and not text.startswith("["):
                    # Show user message live
                    with chat_container:
                        with st.chat_message("user", avatar="👤"):
                            st.markdown(text)

                    # Analyze intent
                    result = analyze_intent(text, state.messages, state.language)
                    state.update_from_intent(result)

                    # Stage 2 — stream LLM reply
                    if state.should_escalate() and not state.escalated:
                        state, response = escalate(state)
                        state.resolved = False
                        with chat_container:
                            with st.chat_message("assistant", avatar="🎧"):
                                st.markdown(response)
                    else:
                        with chat_container:
                            with st.chat_message("assistant", avatar="🎧"):
                                response = st.write_stream(
                                    process_message_stream(state, text)
                                )

                    # Stage 3 — TTS (turbo model, ~1 s)
                    if st.session_state.voice_on:
                        tts_msg = (
                            "🔊 Stem genereren…"
                            if lang == "nl"
                            else "🔊 Generating voice…"
                        )
                        with st.spinner(tts_msg):
                            audio_bytes = text_to_speech(response)
                        if audio_bytes:
                            st.session_state.audio_output = audio_bytes

                    if state.escalated or state.turn_count % 5 == 0:
                        generate_summary(state)

                    st.session_state.conv_state = state
                    st.rerun()

                elif text.startswith("["):
                    st.error(text)

    except AttributeError:
        st.caption(
            "Upgrade Streamlit (≥1.38) voor microfooninvoer."
            if lang == "nl"
            else "Upgrade Streamlit (≥1.38) for microphone input."
        )

    # ── Text input (fallback) ─────────────────────────────────────────────────
    placeholder = "Of typ uw bericht hier…" if lang == "nl" else "Or type your message…"
    if prompt := st.chat_input(placeholder):
        _process_input(prompt)
        st.rerun()


# ── Entry point ──────────────────────────────────────────────────────────────


def main():
    _init()

    state = st.session_state.conv_state
    lang = state.language if state else DEFAULT_LANGUAGE

    st.warning(
        "⚠️ **Demo prototype** — Dit is geen echte TelecomNL klantenservice. "
        "Uitsluitend bedoeld voor demonstratiedoeleinden."
        if lang == "nl"
        else "⚠️ **Demo prototype** — This is not a real TelecomNL service. "
        "For demonstration purposes only.",
        icon="⚠️",
    )

    st.title(f"📡 {COMPANY_NAME} — AI Klantenservice")
    st.caption(f"Powered by GPT-4o + ElevenLabs Turbo • Agent: {AGENT_NAME}")

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
