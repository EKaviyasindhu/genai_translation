# backend/app/ai_engine/tools_bridge.py

from typing import Optional
from langchain_core.tools import tool

from app.services.file_handlers import (
    handle_text,
    handle_audio,
    handle_document,
    handle_video,
)

# NOTE:
# These tools CALL your existing business logic functions.
# No translation / summary / moderation logic is duplicated here.

@tool
def process_text_tool(
    text: str,
    target_lang: str = "en",
    output_pref: str = "both",
    user_id: str = "guest",
) -> dict:
    """
    Use this tool when the input is plain TEXT.
    It will call the existing handle_text() pipeline and return its JSON dict.
    """
    return handle_text(text=text, target_lang=target_lang,
                       output_pref=output_pref, user_id=user_id)


@tool
def process_audio_tool(
    file_path: str,
    target_lang: str = "en",
    output_pref: str = "both",
    user_id: str = "guest",
) -> dict:
    """
    Use this tool when the input is an AUDIO file path (local temp file).
    Calls handle_audio().
    """
    return handle_audio(file_path=file_path, target_lang=target_lang,
                        output_pref=output_pref, user_id=user_id)


@tool
def process_document_tool(
    file_path: str,
    target_lang: str = "en",
    output_pref: str = "both",
    user_id: str = "guest",
) -> dict:
    """
    Use this tool when the input is a DOCUMENT file path (pdf/docx/txt).
    Calls handle_document().
    """
    return handle_document(file_path=file_path, target_lang=target_lang,
                           output_pref=output_pref, user_id=user_id)


@tool
def process_video_tool(
    file_path: str,
    target_lang: str = "en",
    output_pref: str = "both",
    user_id: str = "guest",
) -> dict:
    """
    Use this tool when the input is a VIDEO file path.
    Calls handle_video().
    """
    return handle_video(file_path=file_path, target_lang=target_lang,
                        output_pref=output_pref, user_id=user_id)
