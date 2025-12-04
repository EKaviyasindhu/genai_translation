# backend/app/ai_engine/agents.py

from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from .llm_config import get_router_llm
from .tools_bridge import (
    process_text_tool,
    process_audio_tool,
    process_document_tool,
    process_video_tool,
)

tools = [
    process_text_tool,
    process_audio_tool,
    process_document_tool,
    process_video_tool,
]

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
            You are a routing agent for a multilingual translation backend.
            You NEVER do translation, summarization, transcription, or TTS yourself.
            You ONLY select and call the correct tool.

            request JSON fields:
            - kind: "text" | "audio" | "document" | "video"
            - text (if kind=text)
            - file_path (if kind=audio/document/video)
            - target_lang
            - output_pref ("audio" | "text" | "both")
            - user_id
            - translate: true / false
            - original_actions:
                - text_to_audio
                - audio_to_text
                - generate_summary

            CASE 1 → translate = true
               Always run FULL translation pipeline:
               • text → process_text_tool
               • audio → process_audio_tool
               • document → process_document_tool
               • video → process_video_tool

            CASE 2 → translate = false
               Run ONLY ONE original action:
               • text_to_audio → process_text_tool (return ONLY audio)
               • audio_to_text → process_audio_tool (return ONLY transcript)
               • generate_summary → summary handled inside each tool

            RULES:
            - Call EXACTLY ONE tool
            - Never translate when translate = false
            - Never generate audio when output_pref = "text"
            - Return ONLY tool result — no explanations, no markdown.
            """
        ),
        ("human", "{request}"),
    ]
)


def run_router_agent(request: Dict[str, Any]) -> Dict[str, Any]:
    llm = get_router_llm()
    bound_llm = llm.bind_tools(tools)
    response = bound_llm.invoke(prompt.format(request=request))
    return response  # tool output is returned directly

def decide_actions(settings: dict) -> dict:
    """
    Decide which stage of the workflow is needed
    based on translate flag + original actions.
    This enables conditional routing inside LangGraph.
    """
    translate = settings.get("translate", True)
    actions = settings.get("original_actions", {})

    if translate:
        return {
            "detect_language": True,
            "summarize": True,
            "translate": True,
            "tamil_spell_fix": True,
            "moderate": True,
            "tts": settings.get("output_pref") in ("audio", "both")
        }

    # translate = false → run only original actions
    return {
        "detect_language": actions.get("audio_to_text", False),   # only needed for transcripts
        "summarize": actions.get("generate_summary", False),
        "translate": False,
        "tamil_spell_fix": False,
        "moderate": True,
        "tts": actions.get("text_to_audio", False)
    }
