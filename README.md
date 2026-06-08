# 📡 TelecomAI — Voice AI Customer Service Assistant

> A production-grade voice AI prototype that simulates a telecom customer service agent — combining GPT-4o, ElevenLabs realistic voice synthesis, and OpenAI Whisper speech recognition into a fully interactive Streamlit demo.

---

## Why This Project

Telecom providers handle millions of customer interactions annually. The majority are repetitive, predictable, and expensive to staff at scale. AI-powered voice assistants can resolve Tier-1 issues (WiFi troubleshooting, billing inquiries, SIM problems) autonomously — reducing wait times, lowering operational cost, and improving customer satisfaction.

This project demonstrates what a production-ready AI customer service agent looks like in practice: **not a chatbot with preset answers, but a reasoning agent** that understands intent, adapts to sentiment, follows structured troubleshooting flows, and escalates intelligently to human agents when needed.

Built to show AI product thinking, voice AI engineering, and real-world telecom domain knowledge — exactly the skill set needed for an AI Initiatives team.

---

## Features

| Feature | Details |
|---|---|
| **Full voice interaction** | Speak via microphone → Whisper STT → GPT-4o → ElevenLabs voice reply |
| **10 telecom issue categories** | WiFi slow/down, no internet, unstable, mobile data, SIM, billing, subscription, contract, outage, escalation |
| **Live support dashboard** | Intent, confidence score, sentiment, troubleshooting stage, escalation status |
| **Smart escalation** | Triggers on frustration level, unresolved turns, low confidence, or explicit request |
| **Support summary generation** | Structured report: issue, steps, cause, recommendation, urgency |
| **Bilingual** | Dutch (default) + English, with automatic language detection |
| **Editable knowledge base** | JSON-based — update troubleshooting flows without changing code |
| **Realistic customer profiles** | 8 fake Dutch customers with plan, contract, history |
| **Mock mode** | Runs without API keys using rule-based responses |
| **Local conversation storage** | All sessions saved as JSON |

---

## Architecture

```
User Input (voice or text)
       │
       ▼
  Speech-to-Text          ← OpenAI Whisper
       │
       ▼
  Intent Analyzer         ← GPT-4o (structured JSON output)
  (intent, sentiment,
   confidence, escalation)
       │
       ▼
  Conversation Manager    ← GPT-4o + dynamic system prompt
  (telecom KB injected,      with customer profile +
   one question at a time)   knowledge base context
       │
       ├──── Escalation Engine  (rules + LLM-based)
       │
       ▼
  Support Summary         ← GPT-4o (structured report)
       │
       ▼
  Text-to-Speech          ← ElevenLabs eleven_multilingual_v2
       │
       ▼
  Streamlit UI            (chat + live dashboard)
```

---

## Setup

### 1. Clone / navigate to the project

```bash
cd E:\Manar\claude_projects\telecom-voice-assistant
```

### 2. Create a virtual environment

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API keys

Copy `.env.example` to `.env` and fill in your keys:

```bash
copy .env.example .env
```

```env
OPENAI_API_KEY=sk-...
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM   # Rachel (multilingual)
DEFAULT_LANGUAGE=nl
OPENAI_MODEL=gpt-4o
```

> **No keys?** The app runs in **mock mode** with rule-based responses and no voice output. Good for testing the UI.

### 5. Run the app

```bash
python run.py
# or directly:
streamlit run app/main.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## Usage

### Text mode
Type your message in the chat input at the bottom of the screen.

### Voice mode
Click **"🎤 Spreek uw vraag in"** to record. The audio is transcribed via Whisper and processed automatically. Requires Streamlit ≥ 1.38.

### Customer selection
Pick a customer from the sidebar to load their profile (plan, history, balance). The agent will address them by name and personalize responses.

### Language switching
Toggle between Dutch 🇳🇱 and English 🇬🇧 in the sidebar. The agent auto-detects the customer's language from their messages.

### Dashboard
The right panel updates live with:
- Detected issue category
- Confidence score
- Customer sentiment
- Troubleshooting progress
- Escalation status
- Generated support report

---

## Example Conversations

**Slow WiFi (Dutch)**
> Klant: "Mijn wifi is al 2 dagen erg traag, op alle apparaten."
> Sarah: "Speelt het probleem op alle apparaten of op één? Heeft u al geprobeerd de modem opnieuw op te starten?"

**Mobile data not working (English)**
> Customer: "My data stopped working after I switched to a new phone."
> Sarah: "Could you check your APN settings? It should be: internet.telecoomnl.nl"

**Billing dispute → escalation**
> Klant: "Ik ben HEEL boos, jullie hebben zomaar geld afgeschreven!"
> Sarah: [detects anger, frustration level 5] → escalates, generates handoff note

---

## Project Structure

```
telecom-voice-assistant/
├── app/
│   ├── main.py                  # Streamlit UI
│   ├── config.py                # Settings + API keys
│   ├── llm.py                   # OpenAI GPT-4o integration
│   ├── voice.py                 # ElevenLabs TTS
│   ├── stt.py                   # OpenAI Whisper STT
│   ├── intent_detector.py       # Intent + sentiment analysis
│   ├── conversation_manager.py  # State + LLM conversation
│   ├── escalation.py            # Escalation logic + handoff
│   ├── summary_generator.py     # Support report generation
│   ├── storage.py               # Local JSON persistence
│   └── utils.py                 # Helpers
├── data/
│   ├── knowledge_base.json      # Telecom KB (editable)
│   ├── fake_customers.json      # Demo customer profiles
│   └── sample_conversations.json
├── conversations/               # Saved sessions
├── .env.example
├── requirements.txt
└── run.py
```

---

## Customization

**Add a new issue category:** Edit `data/knowledge_base.json` — add a new key under `"categories"` with `name`, `keywords_nl`, `keywords_en`, `troubleshooting_checklist`, and `common_solutions`.

**Change the voice:** Set `ELEVENLABS_VOICE_ID` in `.env` to any ElevenLabs voice ID. The `eleven_multilingual_v2` model supports Dutch and English natively.

**Change the agent name/company:** Update `AGENT_NAME` and `COMPANY_NAME` in `app/config.py`.

**Adjust escalation sensitivity:** Change `ESCALATION_TURN_LIMIT` and `FRUSTRATION_ESCALATION_THRESHOLD` in `app/config.py`.

---

## Future Improvements

- [ ] Real-time voice streaming (WebSocket + ElevenLabs Streaming API)
- [ ] CRM integration (Salesforce / Zendesk) for live account data
- [ ] Intent confidence threshold tuning via feedback loop
- [ ] Multi-turn memory with vector search (RAG over KB)
- [ ] Phone call integration via Twilio + SIP bridge
- [ ] Admin panel for conversation analytics and KB editing
- [ ] A/B testing of agent prompts and escalation thresholds
- [ ] Multilingual expansion (FR, DE, AR)

---

## Tech Stack

| Component | Technology |
|---|---|
| LLM | OpenAI GPT-4o |
| Speech-to-text | OpenAI Whisper |
| Text-to-speech | ElevenLabs eleven_multilingual_v2 |
| UI | Streamlit |
| Language | Python 3.10+ |
| Storage | Local JSON |

---

## Disclaimer

This is a **demo prototype**. It is not affiliated with or endorsed by any real telecom provider. No real customer data is used. Do not use this system for actual customer support.

---

*Built to demonstrate AI product thinking, voice AI engineering, and telecom domain knowledge.*
