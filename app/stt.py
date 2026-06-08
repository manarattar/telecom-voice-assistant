import io

from app.config import MOCK_MODE, OPENAI_API_KEY

_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def speech_to_text(audio_bytes: bytes, language: str = "nl") -> str:
    if MOCK_MODE:
        return "[Microfooninvoer vereist een OpenAI API-sleutel]"
    lang_code = "nl" if language == "nl" else "en"
    try:
        buf = io.BytesIO(audio_bytes)
        buf.name = "audio.wav"
        transcript = _get_client().audio.transcriptions.create(
            model="whisper-1",
            file=buf,
            language=lang_code,
        )
        return transcript.text.strip()
    except Exception as e:
        return f"[Transcriptie mislukt: {e}]"
