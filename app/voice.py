import io

from app.config import (ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID,
                        OPENAI_API_KEY, VOICE_ENABLED)

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


def _tts_elevenlabs(text: str) -> bytes:
    audio_iter = _elevenlabs().text_to_speech.convert(
        voice_id=ELEVENLABS_VOICE_ID,
        text=text,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
    )
    buf = io.BytesIO()
    for chunk in audio_iter:
        buf.write(chunk)
    data = buf.getvalue()
    if not data:
        raise ValueError("ElevenLabs returned empty audio")
    return data


def _tts_openai(text: str) -> bytes:
    response = _openai().audio.speech.create(
        model="tts-1",
        voice="nova",
        input=text,
    )
    return response.content


def text_to_speech(text: str, raise_errors: bool = False) -> bytes | None:
    if not text.strip():
        return None

    # Try ElevenLabs when configured
    if VOICE_ENABLED:
        try:
            return _tts_elevenlabs(text)
        except Exception as e:
            print(f"[ElevenLabs TTS] failed, falling back to OpenAI: {e}")
            if raise_errors:
                raise

    # Fallback: OpenAI TTS (tts-1, nova voice)
    if OPENAI_API_KEY:
        try:
            return _tts_openai(text)
        except Exception as e:
            print(f"[OpenAI TTS] failed: {e}")
            if raise_errors:
                raise

    return None
