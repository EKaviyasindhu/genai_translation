# backend/app/ai_engine/router_bridge.py

from typing import Dict, Any, Optional
from .langgraph_workflow import run_langgraph_workflow as run_flow

def _base_request(kind: str,
                  text: Optional[str],
                  file_path: Optional[str],
                  target_lang: str,
                  output_pref: str,
                  user_id: str,
                  extra_settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "kind": kind,
        "text": text,
        "file_path": file_path,
        "target_lang": target_lang,
        "output_pref": output_pref,
        "user_id": user_id,
        "settings": extra_settings or {},
    }


def process_text_via_graph(
    text: str,
    target_lang: str,
    output_pref: str,
    user_id: str,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    req = _base_request("text", text, None, target_lang, output_pref, user_id, settings)
    return run_flow(req)


def process_audio_via_graph(
    file_path: str,
    target_lang: str,
    output_pref: str,
    user_id: str,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    req = _base_request("audio", None, file_path, target_lang, output_pref, user_id, settings)
    return run_flow(req)


def process_document_via_graph(
    file_path: str,
    target_lang: str,
    output_pref: str,
    user_id: str,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    req = _base_request("document", None, file_path, target_lang, output_pref, user_id, settings)
    return run_flow(req)


def process_video_via_graph(
    file_path: str,
    target_lang: str,
    output_pref: str,
    user_id: str,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    req = _base_request("video", None, file_path, target_lang, output_pref, user_id, settings)
    return run_flow(req)
