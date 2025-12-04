import re, os
import unicodedata
from functools import lru_cache
from pathlib import Path

# transformers optional
try:
    import torch
except Exception:
    torch = None
try:
    from transformers import pipeline
except Exception:
    pipeline = None

# simple preprocess
def clean_text(text: str) -> str:
    """
    Clean text while preserving non-Latin (Unicode) letters (e.g., Tamil, Hindi).
    - Normalize Unicode (NFKC)
    - Remove control chars and invisible separators
    - Collapse multiple spaces/newlines
    - Trim edges
    """
    if not text:
        return ""

    # Normalize (preserves diacritics properly)
    text = unicodedata.normalize("NFKC", text)

    # Remove C0/C1 control characters (keep printable Unicode)
    # \p{C} class would catch controls; Python re lacks \p, so use category test
    cleaned_chars = []
    for ch in text:
        cat = unicodedata.category(ch)
        # categories starting with C are control, Cf is format; remove them
        if cat.startswith("C"):
            continue
        cleaned_chars.append(ch)
    text = "".join(cleaned_chars)

    # Replace weird invisible characters (zero-width joiner/nb)
    text = text.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")

    # Normalize whitespace: newlines -> single newline, then collapse to single space
    text = re.sub(r'\r\n|\r', '\n', text)
    text = re.sub(r'\n{2,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = text.strip()

    return text

#Moderate Text
def moderate_text(text: str) -> dict:
    """
    Context-aware moderation:
    - Allows technology, cybersecurity, engineering content.
    - Detects REAL violence, abuse, hate speech, sexual content, self-harm.
    - Works for English + Indian languages.
    """

    if not text or not text.strip():
        return {"is_safe": True, "category": None, "reason": None, "flagged_word": None}

    t = text.lower()

    # ---------------------------
    # SAFE TECH CONTEXT WHITELIST
    # ---------------------------
    tech_whitelist = [
        "kill process", "kill -9", "kill command", "kill switch",
        "threat detection", "cyber threat", "ddos attack", 
        "virus scanner", "malware", "exploit", "payload",
        "penetration testing", "ethical hacking", "attack vector",
        "memory dump", "terminate process", "debug", "traceback"
    ]

    for phrase in tech_whitelist:
        if phrase in t:
            return {
                "is_safe": True,
                "category": "technical",
                "reason": "Technical terminology allowed",
                "flagged_word": None
            }

    # ---------------------------
    # VIOLENCE / THREAT DETECTION
    # ---------------------------
    violence = [
        "i will kill you", "will kill you", "going to kill you",
        "kill him", "kill her", "kill you",
        "murder you", "shoot you", "stab you",
        "hurt you", "harm you", "beat you", "attack you",
        "bomb you"
    ]

    indian_violence = [
        "உன்னை கொன்று விடுவேன்", "உன்னை கொல்லப்போகிறேன்",
        "मार डालूँगा", "तुझे मार दूँगा", "मार दूँगा",
        "కొడిస్తా", "நான் உன்னை அடித்து கொல்வேன்"
    ]

    for word in violence + indian_violence:
        if word in t:
            return {
                "is_safe": False,
                "category": "violence/threat",
                "reason": "Threatening or violent intent detected",
                "flagged_word": word
            }

    # ---------------------------
    # ABUSE / HARASSMENT
    # ---------------------------
    abuse = [
        "fuck you", "bitch", "bastard", "asshole",
        "slut", "idiot", "moron",
        "நாயே", "டா வெறி", "கொசுறி",
        "कमीना", "कुत्ता", "हरामी"
    ]

    for word in abuse:
        if word in t:
            return {
                "is_safe": False,
                "category": "abusive language",
                "reason": "Abusive or harassing content detected",
                "flagged_word": word
            }

    # ---------------------------
    # SEXUAL CONTENT
    # ---------------------------
    sexual = [
        "sex", "porn", "nude", "naked", "boobs", "fuck me",
        "oral sex", "anal sex", "breasts", "lick you"
    ]

    for word in sexual:
        if word in t:
            return {
                "is_safe": False,
                "category": "sexual content",
                "reason": "Sexual content detected",
                "flagged_word": word
            }

    # ---------------------------
    # HATE SPEECH
    # ---------------------------
    hate = [
        "kill muslim", "kill hindu", "kill christian",
        "dirty indian", "terrorist community",
        "rape threat", "ethnic cleansing"
    ]

    for word in hate:
        if word in t:
            return {
                "is_safe": False,
                "category": "hate speech",
                "reason": "Hateful or extremist content detected",
                "flagged_word": word
            }

    # ---------------------------
    # SELF-HARM
    # ---------------------------
    self_harm = [
        "i want to die", "i will die", "i want to kill myself",
        "suicide", "end my life", "i want to end everything"
    ]

    for word in self_harm:
        if word in t:
            return {
                "is_safe": False,
                "category": "self-harm",
                "reason": "Self-harm intent detected",
                "flagged_word": word
            }

    # ---------------------------
    # SAFE CONTENT
    # ---------------------------
    return {
        "is_safe": True,
        "category": "safe",
        "reason": "No harmful content detected",
        "flagged_word": None
    }

# file helpers
def validate_file(path: str, allowed_exts, max_mb: int):
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    
    ext = Path(path).suffix.lower()
    if ext not in allowed_exts:
        return {
            "error": "unsupported_format",
            "message": f"File format {ext} not supported",
            "allowed_formats": list(allowed_exts)
        }

    size_mb = os.path.getsize(path)/(1024*1024)
    if size_mb > max_mb:
        return {
            "error": "file_too_large",
            "message": f"File size {size_mb:.2f} MB exceeds limit {max_mb} MB",
            "allowed_size_mb": max_mb
        }

    return ext, size_mb


# domain & tone using transformers if available, else heuristics
DOMAIN_LABELS = ['business','education','technology','legal','medical','news','entertainment','general']

@lru_cache(maxsize=200)
def detect_domain_tone(text: str):
    if not text or len(text.split())<3:
        return {'domain':'casual','tone':'neutral','confidence':0.0}
    # prefer transformers zero-shot
    if pipeline is not None:
        try:
            clf = pipeline('zero-shot-classification', model='facebook/bart-large-mnli')
            res = clf(text, candidate_labels=DOMAIN_LABELS)
            return {'domain': res.get('labels',[ 'general' ])[0], 'tone':'neutral', 'confidence': float(res.get('scores',[0.0])[0])}
        except Exception:
            pass
    # fallback heuristics
    low = text.lower()
    if 'hospital' in low or 'doctor' in low: return {'domain':'medical','tone':'neutral','confidence':0.6}
    if 'school' in low or 'student' in low: return {'domain':'education','tone':'neutral','confidence':0.6}
    return {'domain':'general','tone':'neutral','confidence':0.2}
