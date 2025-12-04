#E:\HOPEAI\PJT\genai_translation\backend\app\services\file_handlers.py
import os, tempfile, shutil,re
from pathlib import Path
from ..config.settings import MAX_UPLOAD_MB, AUDIO_EXTS, VIDEO_EXTS, DOC_EXTS, ALLOWED_EXTS
from ..utils.helpers import validate_file, clean_text, detect_domain_tone, moderate_text
from .transcribe_service import transcribe_with_openai, restore_punctuation
from .translation_service import translate_text, summarize_text
from ..utils.tts_utils import save_tts, fix_tamil_phonemes
from ..utils.cost_utils import (
    estimate_llm_cost,
    estimate_tts_cost,
    estimate_audio_cost,
)
from ..db.mongo import get_db
from .audio_enhance import enhance_voice
from paddleocr import PaddleOCR
from PIL import Image
import json

# PDF Extraction
import pdfplumber
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
from PIL import Image
import fitz  # PyMuPDF

# From Video - extract Audio
import subprocess
import uuid

# -------------------- Language detection --------------------
# Optional high-accuracy detector (Lingua). Falls back to langdetect safe detector if not installed.
try:
    from lingua import Language, LanguageDetectorBuilder

    LANGUAGES = [Language.ENGLISH, Language.TAMIL, Language.HINDI]
    detector = LanguageDetectorBuilder.from_languages(*LANGUAGES).build()

    def detect_lang(text: str):
        try:
            lang = detector.detect_language_of(text)
            if lang is None:
                return "unknown"
            if lang == Language.ENGLISH:
                return "en"
            if lang == Language.TAMIL:
                return "ta"
            if lang == Language.HINDI:
                return "hi"
            # fallback to short name
            return lang.name.lower()[:2]
        except Exception:
            return "unknown"

except Exception:
    # Fallback: simple safe langdetect usage (less accurate but works without extra deps)
    try:
        from langdetect import detect
        from langdetect.lang_detect_exception import LangDetectException

        def detect_lang(text: str):
            try:
                # for very short text default to English
                if not text or len(text.split()) < 2:
                    return "en"
                return detect(text)
            except LangDetectException:
                return "unknown"
            except Exception:
                return "unknown"

    except Exception:
        def detect_lang(text: str):
            return "unknown"


OUTPUT_JSON_DIR = "static/json"
OUTPUT_AUDIO_DIR = "static/audio"

os.makedirs(OUTPUT_JSON_DIR, exist_ok=True)
os.makedirs(OUTPUT_AUDIO_DIR, exist_ok=True)


# -------------------- Helpers --------------------
def _remove_mongo_id(d: dict):
    if "_id" in d:
        try:
            d["_id"] = str(d["_id"])
        except Exception:
            pass
        d.pop("_id", None)


def _save_json(data: dict, prefix: str = "result") -> str:
    fname = f"{prefix}_{int(os.times()[4])}.json"
    path = os.path.join(OUTPUT_JSON_DIR, fname)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def get_audio_duration(file_path: str) -> float:
    """
    Use ffprobe (FFmpeg) to get audio duration in seconds.
    Returns 0.0 if anything fails.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                file_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


# =====================================================
# TEXT HANDLER
# =====================================================
def handle_text(text: str, target_lang: str = "en", output_pref: str = "both", user_id: str = "guest"):
    # 1. MODERATION
    moderation = moderate_text(text)
    if not moderation.get("is_safe", True):
        return {"error": "unsafe", "moderation": moderation}

    # 2. CLEAN + DETECT
    cleaned = clean_text(text)
    domain_tone = detect_domain_tone(cleaned)
    detected = detect_lang(cleaned) if cleaned else "unknown"

    result = {
        "input": text,
        "cleaned": cleaned,
        "detected_lang": detected,
        "target_lang": target_lang,
        "analysis": domain_tone,
    }

    #Cost Calculation
    translation_cost = 0.0
    tts_cost = 0.0

    try:
        # SAME LANGUAGE TEXT → NO TRANSLATION
        if detected == target_lang:
            result["same_language"] = True
            result["source_text"] = cleaned

            if output_pref in ("audio", "both"):
                try:
                    audio_src = save_tts(cleaned, lang=detected, out_dir=OUTPUT_AUDIO_DIR)
                    result["audio_source"] = audio_src
                    tts_cost += estimate_tts_cost(cleaned, detected)
                except Exception:
                    result["audio_source"] = None

        # DIFFERENT LANGUAGE TEXT → TRANSLATION + 2 AUDIOS
        else:
            result["same_language"] = False
            result["source_text"] = cleaned

            # Source audio (detected language)
            if output_pref in ("audio", "both"):
                try:
                    audio_src = save_tts(cleaned, lang=detected, out_dir=OUTPUT_AUDIO_DIR)
                    result["audio_source"] = audio_src
                    tts_cost += estimate_tts_cost(cleaned, detected)
                except Exception:
                    result["audio_source"] = None

            # Full translation (short text → no summary)
            translated = translate_text(cleaned, target_lang)
            result["translated_text"] = translated

            translation_cost = estimate_llm_cost(cleaned, translated)
            # Target audio
            if output_pref in ("audio", "both"):
                try:
                    audio_tgt = save_tts(translated, lang=target_lang, out_dir=OUTPUT_AUDIO_DIR)
                    result["audio_target"] = audio_tgt
                    tts_cost += estimate_tts_cost(translated, target_lang)
                except Exception:
                    result["audio_target"] = None

        # COST FIELDS
        if translation_cost:
            result["translation_cost_usd"] = round(translation_cost, 6)
        if tts_cost:
            result["tts_cost_usd"] = round(tts_cost, 6)
        result["total_cost_usd"] = round(translation_cost + tts_cost, 6)

        # SAVE JSON + MONGO
        json_path = _save_json(result, prefix="text")
        result["json_path"] = json_path

        try:
            db = get_db()
            db.records.insert_one(result)
        except Exception as e:
            print("DB save failed", e)

        _remove_mongo_id(result)
        return result

    except Exception as e:
        return {"error": "internal", "message": str(e)}


# =====================================================
# AUDIO HANDLER
# =====================================================
def handle_audio(file_path: str, target_lang: str = "en", output_pref: str = "both", user_id: str = "guest"):
    # 1. VALIDATION
    validation = validate_file(file_path, ALLOWED_EXTS, MAX_UPLOAD_MB)
    if isinstance(validation, dict) and "error" in validation:
        return validation

    # 2. ENHANCE VOICE FIRST (Demucs)
    file_path = enhance_voice(file_path)

    # 2.1 DURATION FOR COST
    duration_sec = get_audio_duration(file_path)

    # 3. TRANSCRIBE
    text, stt_model = transcribe_with_openai(file_path)  # stt_model should be like "whisper-1"
    if not text or not text.strip():
        return {
            "error": "no_speech_detected",
            "input_file": file_path,
            "message": "Speech not detected or audio too noisy",
        }

    cleaned = restore_punctuation(clean_text(text))
    domain_tone = detect_domain_tone(cleaned)
    moderation = moderate_text(cleaned)
    detected = detect_lang(cleaned) if cleaned else "unknown"

    # transcription cost
    transcription_cost = estimate_audio_cost(duration_sec, stt_model)

    result = {
        "input_file": file_path,
        "transcribed_text": cleaned,
        "detected_lang": detected,
        "target_lang": target_lang,
        "analysis": domain_tone,
        "whisper": stt_model,
        "stt_model": stt_model,
        "audio_duration_sec": duration_sec,
        "transcription_cost_usd": round(transcription_cost, 6),
    }

    if not moderation.get("is_safe", True):
        result["error"] = "unsafe"
        return result

    word_count = len(cleaned.split())
    is_long = word_count > 500

    translation_cost = 0.0
    tts_cost = 0.0

    try:
        # SAME LANGUAGE AUDIO
        if detected == target_lang:
            result["same_language"] = True

            # LONG AUDIO → SUMMARY
            if is_long:
                summary = summarize_text(cleaned, language=detected)
                result["summary"] = summary

                if output_pref in ("audio", "both"):
                    audio_sum = save_tts(summary, lang=detected, out_dir=OUTPUT_AUDIO_DIR)
                    result["summary_audio_source"] = audio_sum
                    tts_cost += estimate_tts_cost(summary, detected)

            # SHORT AUDIO → DIRECT AUDIO
            else:
                if output_pref in ("audio", "both"):
                    audio_src = save_tts(cleaned, lang=detected, out_dir=OUTPUT_AUDIO_DIR)
                    result["audio_source"] = audio_src
                    tts_cost += estimate_tts_cost(cleaned, detected)

        # DIFFERENT LANGUAGE AUDIO
        else:
            result["same_language"] = False

            # source audio
            if output_pref in ("audio", "both"):
                audio_src = save_tts(cleaned, lang=detected, out_dir=OUTPUT_AUDIO_DIR)
                result["audio_source"] = audio_src
                tts_cost += estimate_tts_cost(cleaned, detected)

            if is_long:
                summary = summarize_text(cleaned, language=detected)
                result["summary"] = summary

                if output_pref in ("audio", "both"):
                    audio_sum = save_tts(summary, lang=detected, out_dir=OUTPUT_AUDIO_DIR)
                    result["summary_audio_source"] = audio_sum
                    tts_cost += estimate_tts_cost(summary, detected)

                translated_full = translate_text(cleaned, target_lang)
                result["translated_text"] = translated_full
                translation_cost = estimate_llm_cost(cleaned, translated_full)

                if output_pref in ("audio", "both"):
                    audio_tgt = save_tts(translated_full, lang=target_lang, out_dir=OUTPUT_AUDIO_DIR)
                    result["translated_audio"] = audio_tgt
                    tts_cost += estimate_tts_cost(translated_full, target_lang)

            else:
                translated = translate_text(cleaned, target_lang)
                result["translated_text"] = translated
                translation_cost = estimate_llm_cost(cleaned, translated)

                if output_pref in ("audio", "both"):
                    audio_tgt = save_tts(translated, lang=target_lang, out_dir=OUTPUT_AUDIO_DIR)
                    result["translated_audio"] = audio_tgt
                    tts_cost += estimate_tts_cost(translated, target_lang)

        # COST FIELDS
        if translation_cost:
            result["translation_cost_usd"] = round(translation_cost, 6)
        if tts_cost:
            result["tts_cost_usd"] = round(tts_cost, 6)

        result["total_cost_usd"] = round(
            transcription_cost + translation_cost + tts_cost,
            6,
        )

        # SAVE JSON + DB
        json_path = _save_json(result, prefix="audio")
        result["json_path"] = json_path

        try:
            db = get_db()
            db.records.insert_one(result)
        except Exception as e:
            print("DB save failed", e)

        _remove_mongo_id(result)
        return result

    except Exception as e:
        return {"error": "internal", "message": str(e)}


# =====================================================
# DOCUMENT HANDLER
# =====================================================

def extract_text_universal(file_path: str):
    """
    Extracts English + Tamil + Hindi text using:
      1. pdfplumber (for digital PDFs)
      2. OCR fallback (eng+tam+hin)
      3. docx extraction
    """
    ext = str(file_path).lower()
    text = ""

    # PDF
    if ext.endswith(".pdf"):
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    txt = page.extract_text() or ""
                    text += txt + "\n"
        except Exception:
            text = ""

        contains_tamil = any("\u0B80" <= ch <= "\u0BFF" for ch in text)
        contains_hindi = any("\u0900" <= ch <= "\u097F" for ch in text)

        if contains_tamil or contains_hindi or len(text.strip()) < 300:
            print("Using OCR for multilingual PDF...")
            ocr_text = ""
            doc = fitz.open(file_path)
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                pix = page.get_pixmap()
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                ocr_text += pytesseract.image_to_string(img, lang="eng+tam+hin") + "\n"
            text = ocr_text

        return text.strip()

    # DOCX
    if ext.endswith(".docx"):
        try:
            import docx

            d = docx.Document(file_path)
            text = "\n".join(p.text for p in d.paragraphs)
        except Exception:
            text = ""
        return text.strip()

    # TXT / others
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    except Exception:
        text = ""
    return text.strip()


def handle_document(
    file_path: str,
    target_lang: str = "en",
    output_pref: str = "both",
    user_id: str = "guest",
):
    """
    SHORT DOC:
        - same lang → source_text + source_audio
        - diff lang → source_text + source_audio + full translation + target_audio

    LONG DOC:
        - same lang → summary_source + source_audio
        - diff lang → summary_source + source_audio + full translation + target_audio
    """
    # 1. VALIDATE
    validation = validate_file(file_path, ALLOWED_EXTS, MAX_UPLOAD_MB)
    if isinstance(validation, dict) and "error" in validation:
        return validation

    # 2. EXTRACT
    text = extract_text_universal(file_path)
    if not text or not text.strip():
        return {
            "error": "empty_document",
            "message": "Could not extract text.",
            "input_file": file_path,
        }

    # 3. MODERATION
    moderation = moderate_text(text)
    if not moderation.get("is_safe", True):
        return {"error": "unsafe", "moderation": moderation, "input_file": file_path}

    # 4. CLEAN + DETECT + ANALYSIS
    cleaned = clean_text(text)
    detected = detect_lang(cleaned) if cleaned else "unknown"
    domain_tone = detect_domain_tone(cleaned)

    pages = max(1, cleaned.count("\f") + 1)
    is_long = pages > 1 or len(cleaned.split()) > 1500

    result = {
        "input_file": file_path,
        "pages": pages,
        "detected_lang": detected,
        "target_lang": target_lang,
        "analysis": domain_tone,
    }
    if not is_long:
        result["source_text"] = cleaned

    translation_cost = 0.0
    tts_cost = 0.0

    # AUDIO WRAPPER
    def _audio(txt: str, lang: str):
        nonlocal tts_cost
        if output_pref in ("audio", "both"):
            try:
                original_txt = txt
                if lang == "ta":
                    txt = fix_tamil_phonemes(txt)
                audio_path = save_tts(txt, lang=lang, out_dir=OUTPUT_AUDIO_DIR)
                tts_cost += estimate_tts_cost(original_txt, lang)
                return audio_path
            except Exception:
                return None
        return None

    # LONG DOCUMENT
    if is_long:
        summary_src = summarize_text(cleaned, language=detected)
        result["summary_source"] = summary_src

        audio_src = _audio(summary_src, detected)
        if audio_src:
            result["summary_audio_source"] = audio_src

        if detected == target_lang:
            # same language, stop here
            json_path = _save_json(result, prefix="document")
            result["json_path"] = json_path

            if tts_cost:
                result["tts_cost_usd"] = round(tts_cost, 6)
            result["total_cost_usd"] = round(tts_cost, 6)

            try:
                ins = get_db().records.insert_one(result)
                result["db_id"] = str(ins.inserted_id)
            except Exception:
                pass

            _remove_mongo_id(result)
            return result

        # diff language → full translation
        translated_full = translate_text(cleaned, target_lang)
        result["translated_text"] = translated_full
        translation_cost = estimate_llm_cost(cleaned, translated_full)

        audio_tgt = _audio(translated_full, target_lang)
        if audio_tgt:
            result["translated_audio"] = audio_tgt

        json_path = _save_json(result, prefix="document")
        result["json_path"] = json_path

        if translation_cost:
            result["translation_cost_usd"] = round(translation_cost, 6)
        if tts_cost:
            result["tts_cost_usd"] = round(tts_cost, 6)
        result["total_cost_usd"] = round(translation_cost + tts_cost, 6)

        try:
            ins = get_db().records.insert_one(result)
            result["db_id"] = str(ins.inserted_id)
        except Exception:
            pass

        _remove_mongo_id(result)
        return result

    # SHORT DOCUMENT
    # same language
    if detected == target_lang:
        audio_src = _audio(cleaned, detected)
        if audio_src:
            result["audio_source"] = audio_src

        json_path = _save_json(result, prefix="document")
        result["json_path"] = json_path

        if tts_cost:
            result["tts_cost_usd"] = round(tts_cost, 6)
        result["total_cost_usd"] = round(tts_cost, 6)

        try:
            ins = get_db().records.insert_one(result)
            result["db_id"] = str(ins.inserted_id)
        except Exception:
            pass

        _remove_mongo_id(result)
        return result

    # diff language
    audio_src = _audio(cleaned, detected)
    if audio_src:
        result["audio_source"] = audio_src

    translated_full = translate_text(cleaned, target_lang)
    result["translated_text"] = translated_full
    translation_cost = estimate_llm_cost(cleaned, translated_full)

    audio_tgt = _audio(translated_full, target_lang)
    if audio_tgt:
        result["translated_audio"] = audio_tgt

    json_path = _save_json(result, prefix="document")
    result["json_path"] = json_path

    if translation_cost:
        result["translation_cost_usd"] = round(translation_cost, 6)
    if tts_cost:
        result["tts_cost_usd"] = round(tts_cost, 6)
    result["total_cost_usd"] = round(translation_cost + tts_cost, 6)

    try:
        ins = get_db().records.insert_one(result)
        result["db_id"] = str(ins.inserted_id)
    except Exception:
        pass

    _remove_mongo_id(result)
    return result

# =====================================================
# VIDEO HANDLER
# =====================================================

def extract_audio_ffmpeg(video_path: str) -> str:
    """
    Converts video → WAV audio using FFmpeg.
    Returns path to temp WAV file.
    """
    out_path = os.path.join(tempfile.gettempdir(), f"video_audio_{uuid.uuid4().hex}.wav")

    command = [
        "ffmpeg",
        "-i",
        video_path,
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        out_path,
    ]

    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return out_path
    except subprocess.CalledProcessError:
        return None


def handle_video(
    file_path: str,
    target_lang: str = "en",
    output_pref: str = "both",
    user_id: str = "guest",
):
    """
    VIDEO → Extract audio using FFmpeg → Process exactly like handle_audio().
    """
    # validate video
    validation = validate_file(file_path, ALLOWED_EXTS, MAX_UPLOAD_MB)
    if isinstance(validation, dict) and "error" in validation:
        return validation

    temp_audio_path = extract_audio_ffmpeg(file_path)
    if not temp_audio_path or not os.path.exists(temp_audio_path):
        return {"error": "audio_extraction_failed", "message": "FFmpeg could not extract audio."}

    # optional: enhance voice of the extracted audio
    temp_audio_path = enhance_voice(temp_audio_path)

    # process audio as usual
    audio_result = handle_audio(
        file_path=temp_audio_path,
        target_lang=target_lang,
        output_pref=output_pref,
        user_id=user_id,
    )

    # store original video path
    audio_result["input_video"] = file_path

    # cleanup
    try:
        os.remove(temp_audio_path)
    except Exception:
        pass

    return audio_result

# =====================================================
# IMAGE HANDLER – Tamil + Hindi + English OCR Upgrade
# =====================================================
_OCR_CACHE = {}

def get_ocr(lang):
    if lang not in _OCR_CACHE:
        _OCR_CACHE[lang] = PaddleOCR(lang=lang, use_gpu=False)
    return _OCR_CACHE[lang]


# ---------- Language Detection (Priority-based) ----------
def detect_image_lang(file_path):

    def score_tamil(txt):
        tamil_chars = sum(1 for c in txt if "\u0B80" <= c <= "\u0BFF")
        return tamil_chars / max(len(txt), 1)

    def score_hindi(txt):
        hindi_chars = sum(1 for c in txt if "\u0900" <= c <= "\u097F")
        return hindi_chars / max(len(txt), 1)

    # Read OCR via both first layer (fast check, not return)
    try:
        raw_hi = extract_text_from_ocr(get_ocr("devanagari").ocr(file_path))
    except:
        raw_hi = ""

    try:
        raw_ta = extract_text_from_ocr(get_ocr("ta").ocr(file_path))
    except:
        raw_ta = ""

    s_hi = score_hindi(raw_hi)
    s_ta = score_tamil(raw_ta)

    # Priority rule
    if s_ta >= 0.10 and s_ta > s_hi:     # ≥10% Tamil chars
        return "ta"
    if s_hi >= 0.10 and s_hi > s_ta:     # ≥10% Hindi chars
        return "devanagari"

    return "en"

# ---------- OCR extraction ----------
def extract_text_from_ocr(res):
    texts = []
    for block in res:
        for line in block:
            v = line[1]
            if isinstance(v, (list, tuple)) and len(v) > 0:
                texts.append(str(v[0]))
    return "\n".join(texts).strip()


# ---------- FONT-SHADOW DENOISING ----------
def remove_shadow_noise(text):
    text = re.sub(r'[|_/\\<>@#$%^~`*+=•●◉○]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# ---------- Tamil Fix ----------
def join_tamil_glyphs(text):
    parts = text.split()
    out = ""
    for p in parts:
        if len(p) == 1 or all("\u0B80 <= ch <= \u0BFF" for ch in p):
            out += p
        else:
            out += " " + p + " "
    return out.strip()

def fix_tamil(text):
    text = join_tamil_glyphs(text)
    text = re.sub(r'(?<=[\u0B80-\u0BFF])(?=[\u0B80-\u0BFF])',' ', text)
    return re.sub(r'\s+',' ', text).strip()


# ---------- Hindi Fix (matra + consonant normalization) ----------
def fix_hindi(text):
    # fix broken matras like "क ि" → "कि", "क ी" → "की"
    text = re.sub(r'(\w)\s+ि', r'ि\1', text)
    text = re.sub(r'(\w)\s+ी', r'\1ी', text)
    text = re.sub(r'(\w)\s+ु', r'\1ु', text)
    text = re.sub(r'(\w)\s+ू', r'\1ू', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# ---------- English Fix ----------
def fix_english(text):
    text = re.sub(r'(?<=[a-z])(?=[A-Z])',' ', text)
    return re.sub(r'\s+',' ', text).strip()


# ---------- POSTER QUOTE LINE RESTRUCTURING ----------
def restructure_lines(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if len(lines) <= 2:  # long text skip
        return text

    # If many lines → form a paragraph
    merged = " ".join(lines)
    merged = re.sub(r'\s+', ' ', merged)
    return merged.strip()


# ---------- Apply Fixes Based on OCR-Language ----------
def polish(text, lang):
    text = remove_shadow_noise(text)
    text = restructure_lines(text)

    if lang == "ta":
        return fix_tamil(text)
    if lang == "devanagari":
        return fix_hindi(text)
    return fix_english(text)


# =================================================
# MAIN IMAGE HANDLER
# =================================================
def handle_image(file_path: str, target_lang="en", output_pref="both", user_id="guest"):
    try:
        detected = detect_image_lang(file_path)
        ocr = get_ocr(detected)
        extracted = extract_text_from_ocr(ocr.ocr(file_path))
    except Exception as e:
        return {"error": "ocr_failed", "message": str(e)}

    if not extracted.strip():
        return {"error": "no_text_detected", "input_file": file_path}

    cleaned = polish(extracted, detected)
    cleaned = clean_text(cleaned)
    domain_tone = detect_domain_tone(cleaned)

    result = {
        "input_file": file_path,
        "ocr_engine": f"PaddleOCR-{detected}",
        "detected_lang": detected,
        "source_text": cleaned,
        "target_lang": target_lang,
        "analysis": domain_tone,
    }

    # same language
    if detected == target_lang:
        if output_pref in ("audio", "both"):
            result["audio_source"] = save_tts(cleaned, detected, OUTPUT_AUDIO_DIR)

    # different language
    else:
        translated = translate_text(cleaned, target_lang)
        result["translated_text"] = translated
        if output_pref in ("audio", "both"):
            result["audio_target"] = save_tts(translated, target_lang, OUTPUT_AUDIO_DIR)

    # ---- COST CALC ----
    translation_cost = estimate_llm_cost(cleaned, result.get("translated_text", cleaned)) if "translated_text" in result else 0
    tts_cost = 0
    if "audio_source" in result: tts_cost += estimate_tts_cost(cleaned, detected)
    if "audio_target" in result: tts_cost += estimate_tts_cost(result["translated_text"], target_lang)
    if translation_cost: result["translation_cost_usd"] = round(translation_cost, 6)
    if tts_cost: result["tts_cost_usd"] = round(tts_cost, 6)
    result["total_cost_usd"] = round(translation_cost + tts_cost, 6)

    # ---- SAVE ----
    json_path = _save_json(result, prefix="image")
    result["json_path"] = json_path
    try:
        ins = get_db().records.insert_one(result)
        result["db_id"] = str(ins.inserted_id)
    except: pass

    _remove_mongo_id(result)
    return result
