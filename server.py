"""FastAPI backend — replaces the Streamlit app/main.py."""

import json
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import VOICE_ENABLED
from app.conversation_manager import (ConversationState, build_greeting,
                                      process_message_stream)
from app.escalation import escalate
from app.intent_detector import analyze_intent
from app.stt import speech_to_text
from app.summary_generator import generate_summary
from app.utils import load_customers
from app.voice import text_to_speech

app = FastAPI(title="TelecomNL AI Support")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Request models ────────────────────────────────────────────────────────────


class GreetRequest(BaseModel):
    customer: dict = Field(default_factory=dict)
    language: str = "nl"


class ChatRequest(BaseModel):
    message: str
    messages: list[dict] = Field(default_factory=list)
    customer: dict = Field(default_factory=dict)
    language: str = "nl"
    intent: str = "unknown"
    confidence: float = 0.0
    sentiment: str = "neutral"
    frustration_level: int = 1
    turn_count: int = 0
    escalated: bool = False
    key_issue: str = ""
    troubleshooting_step: int = 0
    summary: dict = Field(default_factory=dict)


class SpeakRequest(BaseModel):
    text: str


# ── State helpers ─────────────────────────────────────────────────────────────


def _rebuild(req: ChatRequest) -> ConversationState:
    s = ConversationState(
        customer=req.customer,
        language=req.language,
        messages=list(req.messages),
        intent=req.intent,
        confidence=req.confidence,
        sentiment=req.sentiment,
        frustration_level=req.frustration_level,
        turn_count=req.turn_count,
        escalated=req.escalated,
        key_issue=req.key_issue,
        troubleshooting_step=req.troubleshooting_step,
        summary=dict(req.summary),
    )
    return s


def _to_dict(state: ConversationState) -> dict:
    return {
        "customer": state.customer,
        "language": state.language,
        "messages": state.messages,
        "intent": state.intent,
        "confidence": state.confidence,
        "sentiment": state.sentiment,
        "frustrationLevel": state.frustration_level,
        "turnCount": state.turn_count,
        "escalated": state.escalated,
        "escalationNeeded": state.escalation_needed,
        "keyIssue": state.key_issue,
        "troubleshootingStep": state.troubleshooting_step,
        "summary": state.summary,
    }


# ── Routes ────────────────────────────────────────────────────────────────────


@app.get("/")
def index():
    return Response(Path("static/index.html").read_bytes(), media_type="text/html")


@app.get("/api/customers")
def get_customers():
    return load_customers()


@app.post("/api/greet")
def greet(req: GreetRequest):
    state = ConversationState.new(customer=req.customer, language=req.language)
    greeting = build_greeting(state)
    state.messages.append({"role": "assistant", "content": greeting})
    return {
        "greeting": greeting,
        "state": _to_dict(state),
        "voiceEnabled": VOICE_ENABLED,
    }


@app.post("/api/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    language: str = Form("nl"),
):
    audio_bytes = await audio.read()
    text = speech_to_text(audio_bytes, language)
    return {"text": text}


@app.post("/api/chat")
def chat(req: ChatRequest):
    """Server-Sent Events stream: text chunks then final state JSON."""

    def _generate():
        state = _rebuild(req)
        result = analyze_intent(req.message, state.messages, state.language)
        state.update_from_intent(result)

        if state.should_escalate() and not state.escalated:
            # Add user message to history before escalating
            state.messages.append({"role": "user", "content": req.message})
            state.turn_count += 1
            state.troubleshooting_step += 1
            state, response = escalate(state)
            state.resolved = False
            state.messages.append({"role": "assistant", "content": response})
            yield f"data: {json.dumps({'type': 'chunk', 'text': response})}\n\n"
        else:
            for chunk in process_message_stream(state, req.message):
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"

        # Optional summary every 5 turns
        if state.escalated or (state.turn_count > 0 and state.turn_count % 5 == 0):
            try:
                generate_summary(state)
            except Exception:
                pass

        yield f"data: {json.dumps({'type': 'done', 'state': _to_dict(state)})}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/speak")
def speak(req: SpeakRequest):
    audio_bytes = text_to_speech(req.text)
    if not audio_bytes:
        return JSONResponse({"error": "TTS niet beschikbaar"}, status_code=503)
    return Response(audio_bytes, media_type="audio/mpeg")


@app.get("/api/voice-check")
def voice_check():
    """Diagnostic endpoint — tests TTS with a short phrase."""
    import traceback

    result = {"voice_enabled": VOICE_ENABLED, "ok": False, "error": None, "bytes": 0}
    if not VOICE_ENABLED:
        result["error"] = "ELEVENLABS_API_KEY not set"
        return result
    try:
        audio = text_to_speech("Hallo, dit is een test.")
        if audio:
            result["ok"] = True
            result["bytes"] = len(audio)
        else:
            result["error"] = "text_to_speech returned None"
    except Exception:
        result["error"] = traceback.format_exc()
    return result
