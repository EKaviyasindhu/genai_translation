# app/utils/tts_utils.py

import os
import re
import time
import hashlib
import logging
from typing import Optional
from gtts import gTTS

logger = logging.getLogger(__name__)

DEFAULT_TTS_EXT = "mp3"


# -----------------------------
# Utility: ensure directory
# -----------------------------
def _ensure_dir(path: str) -> None:
    """
    Create directory if it does not exist.
    Safe to call concurrently.
    """
    os.makedirs(path, exist_ok=True)


# -----------------------------
# Smart Tamil Spell Fixer
# -----------------------------
def smart_tamil_spell_fix(text: str) -> str:
    """
    Fix common Tamil spelling mistakes coming from
    ASR / OCR, especially for history & story content.
    """
    replacements = {
        # Buddhism / history
        "பெளத்தம்": "பௌத்தம்",
        "பெளதம்": "பௌதம்",
        "பெள": "பௌ",
        "பொ": "பொ",

        # Maurya related
        "மௌரியப்": "மௌரியப்",
        "மௌரிய": "மௌரிய",
        "மௌரி": "மௌரி",
        "மௌர": "மௌர",

        # Story words – parrots, pigeons etc.
        "கிலி": "கிளி",
        "கீலி": "கிளி",
        "கீலி,": "கிளி,",
        "புரா": "புறா",
        "பூரா": "புறா",

        # spacing fixes
        "வரலாறு.பொது": "வரலாறு. பொதுப்",
        "வரலாறு.பொதுப்": "வரலாறு. பொதுப்",
    }
    for wrong, correct in replacements.items():
        text = text.replace(wrong, correct)
    return text


# -----------------------------
# Tamil Phoneme / Grapheme Fix
# -----------------------------
def fix_tamil_phonemes(text: str) -> str:
    """
    Normalize common incorrect vowel–sign combinations
    that appear when copying / OCR-ing Tamil text.
    """
    word_replacements = {
        "பெளத்தம்": "பௌத்தம்",
        "பெளதம்": "பௌதம்",
        "மௌரியப்": "மௌரியப்",
        "மௌரிய": "மௌரிய",
        "மௌரி": "மௌரி",
        "மௌர": "மௌர",
    }
    for k, v in word_replacements.items():
        text = text.replace(k, v)

    vowel_map = {
        "ொ": "ோ",
        "ௌ": "ௌ",
        "ெௌ": "ௌ",
        "ெொ": "ொ",
        "ெை": "ை",
        "ொை": "ொய்",
        "ொீ": "ோய்",
        "ொு": "ொ",
    }
    for k, v in vowel_map.items():
        text = text.replace(k, v)

    return text


# -----------------------------
# Language-specific normalizer
# -----------------------------
def normalize_text_for_tts(text: str, lang: str) -> str:
    """
    Light text normalization before sending to TTS.
    - Collapse spaces
    - Tamil: spelling + phoneme fixes
    - Hindi: replace '.' with '।' for better prosody
    """
    if not text:
        return text

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    lang = (lang or "en").lower()

    if lang == "ta":
        text = smart_tamil_spell_fix(text)
        text = fix_tamil_phonemes(text)

    elif lang == "hi":
        # Optional: replace ASCII period with danda for sentence endings
        text = text.replace(".", "।")

    return text


# -----------------------------
# Safe filename generator
# -----------------------------
def _make_safe_filename(text: str, lang: str, ext: str = DEFAULT_TTS_EXT) -> str:
    """
    Generate a filesystem-safe, timestamped filename for TTS output.

    We:
    - Use first line (preview) capped at 30 chars
    - Strip invalid path characters
    - Append a short hash for uniqueness
    - Prefix with language and timestamp
    """
    base = (text or "").strip().splitlines()[0] if text else "audio"
    base = base.strip()

    # preview only (this is *not* the text we send to TTS)
    if len(base) > 30:
        base = base[:30]

    # Remove forbidden characters for most file systems
    base = re.sub(r'[\\/:*?"<>|]', "", base)
    base = base.strip() or "audio"

    # short hash based on full text for uniqueness
    hash_id = hashlib.md5((text or "").encode("utf-8")).hexdigest()[:8]

    ts = time.strftime("%Y%m%d_%H%M%S")
    lang = (lang or "en").lower()

    return f"{lang}_{ts}_{hash_id}_{base[:8]}.{ext}"


# -----------------------------
# Main TTS function
# -----------------------------
def save_tts(
    text: str,
    lang: str = "en",
    out_dir: str = "app/static/audio"
) -> str:
    """
    Generate TTS audio with gTTS and save to disk.

    :param text: Full text to synthesize (any length; gTTS will handle chunking internally)
    :param lang: Language code ("en", "ta", "hi")
    :param out_dir: Output directory path
    :return: Absolute or relative path to saved audio file
    :raises ValueError: if text empty
    :raises RuntimeError: if gTTS fails
    """
    if not text or not text.strip():
        raise ValueError("save_tts: text is empty.")

    lang = (lang or "en").lower()
    if lang not in ("en", "ta", "hi"):
        logger.warning("save_tts: unsupported lang '%s', falling back to 'en'", lang)
        lang = "en"

    norm_text = normalize_text_for_tts(text, lang)

    _ensure_dir(out_dir)
    filename = _make_safe_filename(norm_text, lang, DEFAULT_TTS_EXT)
    full_path = os.path.join(out_dir, filename)

    try:
        tts = gTTS(text=norm_text, lang=lang)
        tts.save(full_path)
        logger.info("TTS saved: %s (lang=%s, chars=%d)", full_path, lang, len(norm_text))
    except Exception as e:
        logger.exception("TTS generation failed for lang='%s'", lang)
        raise RuntimeError(f"TTS generation failed for lang='{lang}': {e}")

    return "/" + full_path.replace("\\", "/")