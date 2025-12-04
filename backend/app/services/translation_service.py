import os
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

OPENAI_KEY = os.getenv('OPENAI_API_KEY', '')

# We use OpenAI via ChatOpenAI (langchain) for translation and summarization
llm = ChatOpenAI(model='gpt-4o-mini', temperature=0, api_key=OPENAI_KEY) if OPENAI_KEY else None

from langchain_core.messages import HumanMessage, SystemMessage
import os

# llm must already be created earlier in this module (your existing ChatOpenAI)
# llm = ChatOpenAI(model='gpt-4o-mini', temperature=0, api_key=OPENAI_KEY) 

def translate_text(
    text: str,
    target_lang: str = 'en',
    tone: str = 'neutral',         # 'formal' | 'neutral' | 'casual'
    gender: str = 'auto',          # 'auto' | 'male' | 'female' | 'neutral'
    politeness: str = 'auto'       # 'auto' | 'formal' | 'neutral' | 'casual'
):
    """
    Universal tone-aware, politeness-aware, gender-aware translator.
    Returns a single string (the translated text).
    """
    if not text:
        return ""

    if 'llm' not in globals() or llm is None:
        # fallback: return original with note
        return f"{text} (no-llm-translation)"

    # ---------------------------
    # Auto-detect gender (simple heuristic)
    # ---------------------------
    detected_gender = "neutral"
    lower = text.lower()
    if gender == "auto":
        # simple pronoun heuristics for English input; keep neutral if ambiguous
        if any(w in lower for w in [" he ", " his ", " him ", " he.", " he's", " he,"]):
            detected_gender = "male"
        elif any(w in lower for w in [" she ", " her ", " she.", " she's", " she,"]):
            detected_gender = "female"
        else:
            detected_gender = "neutral"
    else:
        detected_gender = gender

    # ---------------------------
    # Determine politeness (auto)
    # ---------------------------
    if politeness == "auto":
        if tone == "formal":
            detected_politeness = "formal"
        elif tone == "casual":
            detected_politeness = "casual"
        else:
            detected_politeness = "neutral"
    else:
        detected_politeness = politeness

    # ---------------------------
    # Universal rules
    # ---------------------------
    universal_bad_phrases = [
        "literal word-by-word mapping",
        "transliteration instead of translation",
        "robotic/generic phrasing",
        "overly academic formalism in casual contexts",
        "mixing languages (unless original is mixed)"
    ]

    universal_good_guidelines = (
        "Prefer smooth, natural rephrasing. Preserve meaning, intent and tone. "
        "Rewrite sentences when needed for readability and natural flow. "
        "Match cultural norms and grammar of the target language. "
        "Output ONLY the translated text."
    )

    # ---------------------------
    # Language-specific guidance
    # ---------------------------
    lang_bad_good = {
        "ta": {
                "bad_examples": [
                    "சமூகமாக உள்ளவர்",
                    "சமூகவியல் உள்ளவன்",
                    "சமூகமானவர்",
                    "கிட்ட இருந்து",
                    "போயிடுச்சு",
                    "அவன் சமூகமாக இருக்கிறான்",
                    "literal translation of English adjectives into Tamil",
                    "robotic direct sentence-structure copying"
                ],

                "good_guidelines": (
                    "Produce elegant, natural Tamil that feels like it was originally written in Tamil. "
                    "ALWAYS avoid translating 'sociable', 'sociability', 'outgoing' as 'சமூகமாக', 'சமூகமானவர்'. "
                    "Instead ALWAYS use natural Tamil forms such as: "
                    "'பழகும் தன்மையுடையவர்', 'பழகும் குணம் கொண்டவர்', 'அன்பாக பழகும் ஒருவர்'. "

                    "Prefer refined Tamil structures like: "
                    "'நீண்ட காலமாக விலகி உள்ளார்', 'உலகம் முழுவதும் பயணம் செய்துள்ளார்', "
                    "'அவர் பலரை அறியவில்லை'. "

                    "FORMAL tone: Use polished Tamil with 'அவர்', avoid colloquial verbs. "
                    "NEUTRAL: Use standard written Tamil. "
                    "CASUAL: Use friendly Tamil with 'அவன்/அவள்' but avoid slang. "

                    "Do NOT transliterate English unless it is a proper noun. "
                    "Restructure sentences freely to maintain natural Tamil rhythm, clarity, and flow."
                ),

                "additional_rules": (
                    "ABSOLUTELY FORBID: 'சமூகமாக உள்ளவர்'. "
                    "If meaning is 'he is sociable', ALWAYS translate as: "
                    "'அவர் பழகும் தன்மையுடையவர்'. "
                    "This rule overrides all others."
                )
        },
        "hi": {
                "bad_examples": [
                    "literal word-by-word translations",
                    "है न", "मतलब", "तो क्या", "ऐसा बोल सकते हैं",   # filler / slang
                    "incorrect gender endings like किया/किया गया mismatch",
                    "unnatural Sanskrit-heavy constructions in normal contexts",
                    "Hinglish mixing unless original is mixed",
                    "robotic English structure forced into Hindi"
                ],

                "good_guidelines": (
                    "Produce natural, culturally authentic Hindi with correct gender and number agreement. "
                    "Avoid literal translation and restructure sentences to sound natural in Hindi. "
                    "Use smooth connectors like 'हालाँकि', 'लेकिन', 'इसलिए', 'वह/वे', 'उन्होंने/उसने' depending on context. "
                    "Use correct masculine/feminine verb forms consistently (e.g., 'उन्होंने कहा', 'उसने देखा', "
                    "'वह नहीं जानता/जानती'). "

                    "FORMAL tone: Use polished Hindi with clean vocabulary (e.g., 'उन्होंने', 'कृपया', 'ध्यान दें'). "
                    "NEUTRAL tone: Use standard modern Hindi suitable for narration, news, or general writing. "
                    "CASUAL tone: Use friendly modern spoken Hindi without slang (no 'yaar', 'matlab', 'na'). "

                    "NEVER transliterate English words into Devanagari unless they are names. "
                    "NEVER copy English sentence order if it produces unnatural Hindi. "
                    "Prefer elegant phrasing such as: "
                    "'वह लंबे समय से न्यूयॉर्क से दूर हैं', "
                    "'उन्होंने दुनिया भर की यात्रा की है', "
                    "'वह यहाँ बहुत लोगों को नहीं जानते', "
                    "'वह मिलनसार स्वभाव के हैं'."
                ),

                "additional_rules": (
                "Translate 'away from New York for a long time' as "
                "'लंबे समय से न्यूयॉर्क से दूर है', not literal 'दूर रहा है'. "
                "Avoid translating exclamations like 'Oh' unless context requires emotional expression. "
                "Use 'मिलनसार स्वभाव का' or 'मिलनसार' for 'sociable'. "
                "Ensure natural connective phrases such as 'लेकिन', 'हालाँकि', 'इसके बावजूद'. "
            )
        },

        "en": {
                "bad_examples": [
                    "overly literal grammar from source language",
                    "unnatural passive constructions",
                    "robotic or overly formal academic English",
                    "old-fashioned expressions",
                    "excessively stiff tone",
                    "sentence structures that follow Tamil/Hindi order"
                ],

                "good_guidelines": (
                            "Produce natural, fluent, modern English that sounds like it was originally written in English. "
                            "Feel free to restructure sentences to improve clarity, rhythm, and naturalness. "
                            "Use idiomatic English expressions when appropriate. "

                            "FORMAL tone: Use polished English without contractions, maintain respectful language. "
                            "NEUTRAL tone: Use clear, modern English suitable for narration, articles, or general content. "
                            "CASUAL tone: Use friendly conversational English with contractions (e.g., he's, she's, they're). "

                            "Prefer smooth phrases such as: "
                            "'He has been away from New York for a long time', "
                            "'He has traveled all over the world', "
                            "'He doesn't know many people here', "
                            "'He's quite friendly and wants to meet everyone'. "

                            "Avoid literal carryover of structure from Tamil/Hindi. "
                            "Translate meaning, not words. "
                            "Maintain natural tone, punctuation, and phrasing matching the context."
                        ),

                "additional_rules": (
                    "NEVER mimic source language verb order. "
                    "ALWAYS maintain natural English rhythm and cadence. "
                    "Avoid unnatural over-formality unless explicitly requested."
                )
        }

    }

    # If target language isn't in mapping, use generic guidance
    lang_guidance = lang_bad_good.get(target_lang, {
        "bad_examples": [],
        "good_guidelines": universal_good_guidelines
    })

    # ---------------------------
    # Build strong prompt
    # ---------------------------
    prompt = f"""
        You are an expert human translator with deep cultural-linguistic knowledge.

        Translate the following text into the target language: {target_lang}
        Required output: a single string containing ONLY the translated text (no commentary, no explanation).

        Context parameters:
        - tone: {tone}
        - politeness: {detected_politeness}
        - gender: {detected_gender}

        STRICT RULES:
        - DO NOT transliterate English words into target script (unless necessary for proper nouns).
        - DO NOT perform word-by-word literal translation.
        - DO NOT use slang, regional dialect, or crude colloquial forms in formal or neutral tone.
        - DO NOT produce academic or unnatural phrasing in casual contexts.
        - Preserve meaning, nuance, and tone. Rewrite freely for natural readability.

        UNIVERSAL GUIDELINES:
        {universal_good_guidelines}

        LANGUAGE-SPECIFIC GUIDANCE:
        Bad patterns to avoid for {target_lang}: {', '.join(lang_guidance.get('bad_examples', []))}
        Preferred style / examples for {target_lang}: {lang_guidance.get('good_guidelines')}

        If tone is 'formal', produce polished, respectful, and grammatically correct text.
        If tone is 'neutral', produce clear, natural, and balanced text suitable for general purposes.
        If tone is 'casual', produce friendly, conversational text (no vulgar slang).

        Now translate the following input text exactly:

        ### INPUT TEXT:
        {text}

        Provide ONLY the final translation.
        """

    messages = [
        SystemMessage(content="You are a high-quality multilingual translator producing natural, tone-aware outputs."),
        HumanMessage(content=prompt)
    ]

    # ---------------------------
    # Invoke model
    # ---------------------------
    try:
        resp = llm.invoke(messages)
        # resp may be an object with .content
        translated = getattr(resp, "content", None)
        if translated is None and isinstance(resp, list) and len(resp) > 0:
            translated = getattr(resp[0], "content", str(resp[0]))
        if translated is None:
            translated = str(resp)
        return translated.strip()
    except Exception as e:
        # graceful fallback
        return f"{text} (translation failed: {e})"

def summarize_text(text: str, language: str = "en"):
    """
    Summarize the text in the SAME LANGUAGE as the input.
    """
    if not text:
        return ""

    if llm is None:
        return text[:500]  # fallback

    # Language-specific summary instructions
    lang_instruction = {
        "ta": "தமிழில் சுருக்கமாக எழுதவும். மிகச்சுருக்கமாக, தெளிவாக இருக்க வேண்டும்.",
        "hi": "हिंदी में संक्षेप में लिखें। केवल सार ही दें।",
        "en": "Write a concise summary in English.",
    }

    instruction = lang_instruction.get(language, f"Write a short summary in {language}.")

    prompt = f"{instruction}\n\n{text}"

    resp = llm.invoke([HumanMessage(content=prompt)])
    return resp.content.strip()

