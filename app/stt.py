import io

from app.config import MOCK_MODE, OPENAI_API_KEY

_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def _detect_format(audio_bytes: bytes) -> str:
    """Detect audio format from magic bytes — browsers record WebM, not WAV."""
    if len(audio_bytes) > 4:
        if audio_bytes[:4] == b"RIFF":
            return "audio.wav"
        if audio_bytes[:4] == b"\x1a\x45\xdf\xa3":
            return "audio.webm"
        if audio_bytes[:4] == b"OggS":
            return "audio.ogg"
        if audio_bytes[:3] == b"ID3" or audio_bytes[:2] == b"\xff\xfb":
            return "audio.mp3"
    return "audio.webm"  # browsers default to WebM


def speech_to_text(audio_bytes: bytes, language: str = "nl") -> str:
    if MOCK_MODE:
        return "[Microfooninvoer vereist een OpenAI API-sleutel]"
    lang_code = "nl" if language == "nl" else "en"
    try:
        buf = io.BytesIO(audio_bytes)
        buf.name = _detect_format(audio_bytes)
        transcript = _get_client().audio.transcriptions.create(
            model="whisper-1",
            file=buf,
            language=lang_code,
        )
        return transcript.text.strip()
    except Exception as e:
        return f"[Transcriptie mislukt: {e}]"
