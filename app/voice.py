import io

from app.agents import get_agent
from app.config import ELEVENLABS_API_KEY, OPENAI_API_KEY, VOICE_ENABLED

_el_client = None
_oai_client = None


def _elevenlabs():
    global _el_client
    if _el_client is None:
        from elevenlabs import ElevenLabs

        _el_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
    return _el_client


def _openai():
    global _oai_client
    if _oai_client is None:
        from openai import OpenAI

        _oai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _oai_client


def _voice_settings(frustration_level: int):
    """Return ElevenLabs VoiceSettings tuned to customer frustration level."""
    try:
        from elevenlabs import VoiceSettings
    except ImportError:
        return None

    if frustration_level >= 4:
        # Very frustrated: slower, measured, extra empathetic
        return VoiceSettings(stability=0.82, similarity_boost=0.62, style=0.08)
    if frustration_level == 3:
        # Moderately frustrated: slightly softer
        return VoiceSettings(stability=0.68, similarity_boost=0.70, style=0.02)
    # Normal: natural and warm
    return VoiceSettings(stability=0.50, similarity_boost=0.75, style=0.00)


def _tts_elevenlabs(
    text: str,
    voice_id: str,
    frustration_level: int = 1,
) -> bytes:
    kwargs: dict = dict(
        voice_id=voice_id,
        text=text,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
    )
    settings = _voice_settings(frustration_level)
    if settings is not None:
        kwargs["voice_settings"] = settings

    audio_iter = _elevenlabs().text_to_speech.convert(**kwargs)
    buf = io.BytesIO()
    for chunk in audio_iter:
        buf.write(chunk)
    data = buf.getvalue()
    if not data:
        raise ValueError("ElevenLabs returned empty audio")
    return data


def _tts_openai(text: str, voice: str = "nova") -> bytes:
    response = _openai().audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
    )
    return response.content


def text_to_speech_stream(
    text: str,
    agent_id: str = "sarah",
    frustration_level: int = 1,
):
    """Yield raw MP3 bytes using ElevenLabs streaming, fallback to OpenAI."""
    if not text.strip():
        return

    agent = get_agent(agent_id)
    settings = _voice_settings(frustration_level)

    if VOICE_ENABLED:
        kwargs: dict = dict(
            voice_id=agent.elevenlabs_voice_id,
            text=text,
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )
        if settings is not None:
            kwargs["voice_settings"] = settings
        try:
            yield from _elevenlabs().text_to_speech.convert_as_stream(**kwargs)
            return
        except Exception as e:
            print(f"[ElevenLabs stream TTS] failed, falling back: {e}")

    if OPENAI_API_KEY:
        try:
            yield _tts_openai(text, voice=agent.openai_voice)
        except Exception as e:
            print(f"[OpenAI TTS] failed: {e}")


def text_to_speech(
    text: str,
    agent_id: str = "sarah",
    frustration_level: int = 1,
    raise_errors: bool = False,
) -> bytes | None:
    if not text.strip():
        return None

    agent = get_agent(agent_id)

    # Try ElevenLabs when configured
    if VOICE_ENABLED:
        try:
            return _tts_elevenlabs(
                text,
                voice_id=agent.elevenlabs_voice_id,
                frustration_level=frustration_level,
            )
        except Exception as e:
            print(f"[ElevenLabs TTS] failed, falling back to OpenAI: {e}")
            if raise_errors:
                raise

    # Fallback: OpenAI TTS — use agent's configured voice
    if OPENAI_API_KEY:
        try:
            return _tts_openai(text, voice=agent.openai_voice)
        except Exception as e:
            print(f"[OpenAI TTS] failed: {e}")
            if raise_errors:
                raise

    return None
