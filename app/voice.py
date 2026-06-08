import io

from app.config import ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, VOICE_ENABLED

_client = None


def _get_client():
    global _client
    if _client is None:
        from elevenlabs import ElevenLabs

        _client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
    return _client


def text_to_speech(text: str, raise_errors: bool = False) -> bytes | None:
    if not VOICE_ENABLED or not text.strip():
        return None
    try:
        client = _get_client()
        audio_iter = client.text_to_speech.convert(
            voice_id=ELEVENLABS_VOICE_ID,
            text=text,
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )
        buf = io.BytesIO()
        for chunk in audio_iter:
            buf.write(chunk)
        data = buf.getvalue()
        return data if data else None
    except Exception as e:
        print(f"[ElevenLabs TTS fout]: {e}")
        if raise_errors:
            raise
        return None
