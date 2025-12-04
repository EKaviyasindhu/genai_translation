# app/utils/cost_utils.py

# --- AUDIO COST (OpenAI) ---
AUDIO_COST_PER_MIN = {
    "whisper-1": 0.006,
    "gpt-4o-mini-transcribe": 0.003,
}

def estimate_audio_cost(duration_seconds: float, model: str) -> float:
    try:
        per_min = AUDIO_COST_PER_MIN.get(model, 0.0)
        mins = duration_seconds / 60.0
        return round(per_min * mins, 6)
    except:
        return 0.0


# --- TEXT TOKEN COST (translation / summarization) ---
TOKEN_PRICE = {
    "gpt-4o-mini": 0.0006 / 1000,   # $ per 1k tokens input
    "gpt-4o-mini-out": 0.0009 / 1000   # $ per 1k tokens output
}

def estimate_llm_cost(tokens_in: int, tokens_out: int):
    try:
        cost = (TOKEN_PRICE["gpt-4o-mini"] * tokens_in) + (TOKEN_PRICE["gpt-4o-mini-out"] * tokens_out)
        return round(cost, 6)
    except:
        return 0.0


# --- TTS COST ---
TTS_COST_PER_CHAR = {
    "ta": 0.00001,
    "hi": 0.00001,
    "en": 0.000008
}

def estimate_tts_cost(text: str, lang: str):
    try:
        rate = TTS_COST_PER_CHAR.get(lang, 0.00001)
        return round(len(text) * rate, 6)
    except:
        return 0.0
