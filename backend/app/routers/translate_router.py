#E:\HOPEAI\PJT\genai_translation\backend\app\routers\translate_router.py
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import tempfile
import shutil

from app.ai_engine.langgraph_workflow import run_langgraph_workflow

router = APIRouter()


# ---------- TEXT REQUEST BODY ----------
class TextIn(BaseModel):
    text: str
    target_lang: str = "en"
    output_pref: str = "both"
    user_id: str = "guest"
    translate: bool = True
    original_actions: dict = {}


# ---------- TEXT ----------
@router.post("/text/translate")
async def translate_text_endpoint(payload: TextIn):
    try:
        request = {
            "kind": "text",
            "text": payload.text,
            "file_path": None,
            "target_lang": payload.target_lang,
            "output_pref": payload.output_pref,
            "user_id": payload.user_id,
            "translate": payload.translate,
            "original_actions": payload.original_actions,
        }
        res = run_langgraph_workflow(request)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- AUDIO ----------
@router.post("/audio/upload")
async def upload_audio(
    file: UploadFile = File(...),
    target_lang: str = Form("en"),
    output_pref: str = Form("both"),
    user_id: str = Form("guest")
):
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, file.filename)

    with open(temp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        request = {
            "kind": "audio",
            "text": None,
            "file_path": temp_path,
            "target_lang": target_lang,
            "output_pref": output_pref,
            "user_id": user_id,
        }
        res = run_langgraph_workflow(request)
        return res
    finally:
        try:
            os.remove(temp_path)
        except:
            pass


# ---------- DOCUMENT ----------
@router.post("/document/upload")
async def upload_document(
    file: UploadFile = File(...),
    target_lang: str = Form("en"),
    output_pref: str = Form("both"),
    user_id: str = Form("guest")
):
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, file.filename.replace(" ", "_"))

    with open(temp_path, "wb") as f:
        f.write(await file.read())

    try:
        request = {
            "kind": "document",
            "text": None,
            "file_path": temp_path,
            "target_lang": target_lang,
            "output_pref": output_pref,
            "user_id": user_id,
        }
        res = run_langgraph_workflow(request)
        return res

    finally:
        try:
            os.remove(temp_path)
        except:
            pass

@router.post("/image/upload")
async def upload_image(
    file: UploadFile = File(...),
    target_lang: str = Form("en"),
    output_pref: str = Form("both"),
    user_id: str = Form("guest")
):
    temp_dir = tempfile.gettempdir()
    filename = file.filename.replace(" ", "_")
    temp_path = os.path.join(temp_dir, filename)

    with open(temp_path, "wb") as f:
        f.write(await file.read())

    try:
        request = {
            "kind": "image",
            "text": None,
            "file_path": temp_path,
            "target_lang": target_lang,
            "output_pref": output_pref,
            "user_id": user_id,
        }
        res = run_langgraph_workflow(request)
        return res

    finally:
        try:
            os.remove(temp_path)
        except:
            pass


# ---------- VIDEO ----------
@router.post("/video/upload")
async def upload_video(
    file: UploadFile = File(...),
    target_lang: str = Form("en"),
    output_pref: str = Form("both"),
    user_id: str = Form("guest")
):
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, file.filename)

    with open(temp_path, "wb") as f:
        f.write(await file.read())

    try:
        request = {
            "kind": "video",
            "text": None,
            "file_path": temp_path,
            "target_lang": target_lang,
            "output_pref": output_pref,
            "user_id": user_id,
        }
        res = run_langgraph_workflow(request)
        return res

    finally:
        try:
            os.remove(temp_path)
        except:
            pass


# ---------- WORKFLOW GRAPH IN ENDPOINT ----------
@router.get("/workflow/graph")
def get_graph(refresh: bool = False):
    return {
        "status": "ok",
        "visualization": False,
        "note": "Graph visualization removed in LangGraph ≥ 1.0. No file is generated."
    }

