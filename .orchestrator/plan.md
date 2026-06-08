# Telecom Voice AI Assistant — Build Plan

## Goal
Polished Streamlit voice AI demo for telecom customer service. Interview-ready.

## Stack
- Python 3.10+
- Streamlit >= 1.38 (st.audio_input for mic)
- OpenAI GPT-4o (conversation + intent analysis)
- OpenAI Whisper (STT)
- ElevenLabs eleven_multilingual_v2 (TTS)
- python-dotenv

## Architecture
User Input (voice/text)
  → STT (Whisper) or direct text
  → Conversation Manager (builds prompt + calls GPT-4o)
  → Intent Analyzer (parallel structured LLM call)
  → ElevenLabs TTS (voice output)
  → Streamlit UI (chat + dashboard)

## Tickets
1. Config + data files (knowledge_base.json, fake_customers.json)
2. Core modules: llm.py, voice.py, stt.py
3. Conversation logic: intent_detector.py, conversation_manager.py, escalation.py, summary_generator.py
4. Storage + utils
5. Streamlit UI (main.py)
6. README + run.py + .env.example
