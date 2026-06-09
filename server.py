"""FastAPI backend — TelecomNL Voice AI Assistant."""

import json
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.agents import DEFAULT_AGENT_ID, get_agent
from app.config import BACKEND_URL, COMPANY_NAME, VOICE_ENABLED
from app.conversation_manager import (ConversationState, build_greeting,
                                      process_turn_with_tools)
from app.elevenlabs_agents import get_or_create_agent, get_signed_url
from app.escalation import escalate
from app.intent_detector import analyze_intent
from app.stt import speech_to_text
from app.summary_generator import generate_summary
from app.utils import load_customers
from app.voice import text_to_speech, text_to_speech_stream

app = FastAPI(title="TelecomNL AI Support")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Request / response models ─────────────────────────────────────────────────


class GreetRequest(BaseModel):
    customer: dict = Field(default_factory=dict)
    language: str = "nl"
    agent_id: str = DEFAULT_AGENT_ID


class ChatRequest(BaseModel):
    message: str
    messages: list[dict] = Field(default_factory=list)
    customer: dict = Field(default_factory=dict)
    language: str = "nl"
    agent_id: str = DEFAULT_AGENT_ID
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
    agent_id: str = DEFAULT_AGENT_ID
    frustration_level: int = 1


class CallEndRequest(BaseModel):
    session_id: str = ""
    agent_id: str = DEFAULT_AGENT_ID
    customer_name: str = ""
    intent: str = "unknown"
    turns: int = 0
    sentiment: str = "neutral"
    escalated: bool = False
    resolved: bool = False
    rating: int = 0


class RealtimeSessionRequest(BaseModel):
    agent_id: str = DEFAULT_AGENT_ID
    customer: dict = Field(default_factory=dict)
    language: str = "nl"


class AnalyzeRequest(BaseModel):
    text: str
    language: str = "nl"


# ── State helpers ─────────────────────────────────────────────────────────────


def _rebuild(req: ChatRequest) -> ConversationState:
    return ConversationState(
        customer=req.customer,
        language=req.language,
        agent_id=req.agent_id,
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


def _to_dict(state: ConversationState) -> dict:
    return {
        "customer": state.customer,
        "language": state.language,
        "agentId": state.agent_id,
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


@app.get("/api/agents")
def get_agents():
    from app.agents import AGENTS

    return [
        {
            "id": a.id,
            "name": a.name,
            "emoji": a.emoji,
            "color": a.color,
            "language": a.default_language,
        }
        for a in AGENTS.values()
    ]


@app.post("/api/greet")
def greet(req: GreetRequest):
    state = ConversationState.new(
        customer=req.customer,
        language=req.language,
        agent_id=req.agent_id,
    )
    greeting = build_greeting(state, agent_id=req.agent_id)
    state.messages.append({"role": "assistant", "content": greeting})
    agent = get_agent(req.agent_id)
    return {
        "greeting": greeting,
        "state": _to_dict(state),
        "voiceEnabled": VOICE_ENABLED,
        "agent": {
            "id": agent.id,
            "name": agent.name,
            "emoji": agent.emoji,
            "color": agent.color,
        },
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
    """SSE stream: tool_call / tool_done / chunk / done events."""

    def _generate():
        state = _rebuild(req)
        result = analyze_intent(req.message, state.messages, state.language)
        state.update_from_intent(result)

        if state.should_escalate() and not state.escalated:
            state.messages.append({"role": "user", "content": req.message})
            state.turn_count += 1
            state.troubleshooting_step += 1
            state, response = escalate(state)
            state.resolved = False
            state.messages.append({"role": "assistant", "content": response})
            yield f"data: {json.dumps({'type': 'chunk', 'text': response})}\n\n"
        else:
            for event in process_turn_with_tools(state, req.message, req.customer):
                yield f"data: {json.dumps(event)}\n\n"

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
    audio_bytes = text_to_speech(
        req.text,
        agent_id=req.agent_id,
        frustration_level=req.frustration_level,
    )
    if not audio_bytes:
        return JSONResponse({"error": "TTS niet beschikbaar"}, status_code=503)
    return Response(audio_bytes, media_type="audio/mpeg")


@app.post("/api/speak-stream")
def speak_stream(req: SpeakRequest):
    def _generate():
        for chunk in text_to_speech_stream(
            req.text,
            agent_id=req.agent_id,
            frustration_level=req.frustration_level,
        ):
            if isinstance(chunk, (bytes, bytearray)):
                yield chunk

    return StreamingResponse(
        _generate(),
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/call-end")
def call_end(req: CallEndRequest):
    """Acknowledge call end — could persist to DB in future."""
    return {"ok": True, "session": req.session_id}


@app.post("/api/realtime-session")
def realtime_session(req: RealtimeSessionRequest):
    """Return a signed ElevenLabs WebSocket URL + per-session context."""
    try:
        el_agent_id = get_or_create_agent(req.agent_id, BACKEND_URL)
        signed_url = get_signed_url(el_agent_id)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=503)

    agent = get_agent(req.agent_id)
    c = req.customer
    name = c.get("name", "")
    lang = req.language

    if lang == "nl":
        first_message = (
            f"Goedendag{', ' + name if name else ''}! "
            f"U spreekt met {agent.name} van {COMPANY_NAME}. "
            "Hoe kan ik u vandaag helpen?"
        )
        customer_ctx = (
            (
                f"\nACTUELE KLANT:\n"
                f"  Naam: {c.get('name', 'onbekend')}\n"
                f"  Klantnummer: {c.get('account_number', 'onbekend')}\n"
                f"  Pakket: {c.get('plan_name', 'onbekend')}\n"
                f"  Status: {c.get('status', 'onbekend')}\n"
                f"  Openstaand: €{c.get('outstanding_balance', 0):.2f}\n"
                f"  Opmerking: {c.get('notes', '')}\n"
            )
            if name
            else ""
        )
    else:
        first_message = (
            f"Good day{', ' + name if name else ''}! "
            f"You're speaking with {agent.name} from {COMPANY_NAME}. "
            "How can I help you today?"
        )
        customer_ctx = (
            (
                f"\nCURRENT CUSTOMER:\n"
                f"  Name: {c.get('name', 'unknown')}\n"
                f"  Account: {c.get('account_number', 'unknown')}\n"
                f"  Plan: {c.get('plan_name', 'unknown')}\n"
                f"  Status: {c.get('status', 'unknown')}\n"
                f"  Balance: €{c.get('outstanding_balance', 0):.2f}\n"
                f"  Notes: {c.get('notes', '')}\n"
            )
            if name
            else ""
        )

    return {
        "signed_url": signed_url,
        "first_message": first_message,
        "customer_context": customer_ctx,
        "agent": {
            "id": agent.id,
            "name": agent.name,
            "emoji": agent.emoji,
            "color": agent.color,
        },
    }


@app.post("/api/tools/{tool_name}")
async def tool_webhook(tool_name: str, request: Request):
    """ElevenLabs calls this when the LLM invokes a diagnostic tool."""
    from app.tools import execute_tool

    try:
        args = await request.json()
    except Exception:
        args = {}

    # Resolve customer from account_id if present
    account_id = args.get("account_id", "")
    customers = load_customers()
    customer = next((c for c in customers if c.get("account_number") == account_id), {})

    result = execute_tool(tool_name, args, customer)
    return result


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    """Lightweight intent + sentiment analysis for ConvAI transcript events."""
    result = analyze_intent(req.text, [], req.language)
    return {
        "intent": result.intent,
        "sentiment": result.sentiment,
        "frustration_level": result.frustration_level,
        "confidence": result.confidence,
        "key_issue": result.key_issue,
    }


@app.get("/api/voice-check")
def voice_check():
    """Diagnostic: test TTS with a short phrase."""
    import traceback

    result = {"voice_enabled": VOICE_ENABLED, "ok": False, "error": None, "bytes": 0}
    if not VOICE_ENABLED:
        result["error"] = "ELEVENLABS_API_KEY not set"
        return result
    try:
        audio = text_to_speech("Hallo, dit is een test.", raise_errors=True)
        if audio:
            result["ok"] = True
            result["bytes"] = len(audio)
        else:
            result["error"] = "API returned empty audio"
    except Exception:
        result["error"] = traceback.format_exc()
    return result
