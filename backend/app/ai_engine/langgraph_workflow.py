#E:\HOPEAI\PJT\genai_translation\backend\app\ai_engine\langgraph_workflow.py
from typing import TypedDict, Dict, Any, Optional
from langgraph.graph import StateGraph, END

# we reuse your existing handlers & logic
from app.services.file_handlers import (
    handle_text,
    handle_audio,
    handle_document,
    handle_image,
    handle_video,
)

class FlowState(TypedDict, total=False):
    request: Dict[str, Any]
    result: Dict[str, Any]


def node_route_and_run(state: FlowState) -> FlowState:
    """
    Single dynamic node:
    - Looks at request.kind
    - Calls the correct existing handler
    - Returns EXACTLY the same dict your MVC used to return
    """
    req = state["request"]

    kind: str = req.get("kind", "text")
    target_lang: str = req.get("target_lang", "en")
    output_pref: str = req.get("output_pref", "both")
    user_id: str = req.get("user_id", "guest")

    # these exist only depending on type
    text: Optional[str] = req.get("text")
    file_path: Optional[str] = req.get("file_path")

    #Dynamic routing based on kind
    if kind == "text":
        result = handle_text(
            text=text or "",
            target_lang=target_lang,
            output_pref=output_pref,
            user_id=user_id,
        )

    elif kind == "audio":
        if not file_path:
            result = {"error": "missing_file_path", "message": "audio file path required"}
        else:
            result = handle_audio(
                file_path=file_path,
                target_lang=target_lang,
                output_pref=output_pref,
                user_id=user_id,
            )

    elif kind == "document":
        if not file_path:
            result = {"error": "missing_file_path", "message": "document file path required"}
        else:
            result = handle_document(
                file_path=file_path,
                target_lang=target_lang,
                output_pref=output_pref,
                user_id=user_id,
            )

    elif kind == "image":
        if not file_path:
            result = {"error": "missing_file_path", "message": "image file path required"}
        else:
            result = handle_image(
                file_path=file_path,
                target_lang=target_lang,
                output_pref=output_pref,
                user_id=user_id,
            )        

    elif kind == "video":
        if not file_path:
            result = {"error": "missing_file_path", "message": "video file path required"}
        else:
            result = handle_video(
                file_path=file_path,
                target_lang=target_lang,
                output_pref=output_pref,
                user_id=user_id,
            )

    else:
        result = {"error": "invalid_kind", "message": f"Unsupported kind: {kind}"}

    state["result"] = result
    return state


def build_workflow():
    graph = StateGraph(FlowState)

    # one main node that dynamically routes & calls your logic
    graph.add_node("route_and_run", node_route_and_run)

    # entry point
    graph.set_entry_point("route_and_run")

    # end after processing
    graph.add_edge("route_and_run", END)

    return graph.compile()


workflow_app = build_workflow()

def run_langgraph_workflow(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Public function your router calls.
    Returns EXACT output from handle_text/audio/document/video.
    """
    final_state = workflow_app.invoke({"request": request})
    return final_state.get("result", {})

