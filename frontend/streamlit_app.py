# streamlit_app.py
# Production-ready Streamlit frontend (WhatsApp-style chat bubbles)
# - Single-page, no duplicate processing
# - File uploads processed only when user clicks SEND
# - Handles text, audio, image, video, document (short/long)
# - Shows only required outputs + JSON link + audio download
# - Uses callbacks to avoid Streamlit session_state write errors

import os
import html
import tempfile
from datetime import datetime
from pathlib import Path
import urllib.parse

import requests
import streamlit as st
from audio_recorder_streamlit import audio_recorder

import requests
from PIL import Image
from io import BytesIO

# ---------------- CONFIG ----------------
#BACKEND_BASE = "http://localhost:8000"  # change if needed
BACKEND_BASE = "http://ec2-13-126-132-148.ap-south-1.compute.amazonaws.com:8000"
BACKEND_STATIC_DIR = os.path.abspath("../backend/app/static/graph")
WORKFLOW_LOCAL_PATH = os.path.join(BACKEND_STATIC_DIR, "langgraph_workflow.png")

st.set_page_config(page_title="Translation Chat", layout="wide", page_icon="💬")

# ---------------- CSS (WhatsApp-style bubbles) ----------------
st.markdown(
    """
<style>
.block-container { padding-top: 1rem !important; padding-left:1rem !important; padding-right:1rem !important; }
.stApp { background: #f6f7fb; color: #0f172a; }

.chat-area { max-height: calc(100vh - 220px); overflow-y:auto; padding:12px; }

.msg { display:flex; margin-bottom:10px; }
/* user (left) */
.msg.user .bubble {
    background: linear-gradient(90deg,#e6f0ff,#dbeeff);
    color:#022047;
    padding:10px 14px;
    border-radius:12px;
    max-width:72%;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}
/* system (right) */
.msg.system { justify-content:flex-end; }
.msg.system .bubble {
    background: linear-gradient(90deg,#fff9e6,#fff3cd);
    color:#2b2b0b;
    padding:10px 14px;
    border-radius:12px;
    max-width:72%;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}

/* small metadata */
.meta { font-size:12px; color:#475569; margin-top:6px; }
.meta a { color: #0366d6; text-decoration:none; }

/* audio responsive */
.bubble audio { max-width:100%; display:block; margin-top:6px; }
.download-link { margin-left:8px; font-size:13px; color:#0366d6;}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------- Session state defaults ----------------
if "messages" not in st.session_state:
    st.session_state["messages"] = []  # each message: {role:'user'|'system', user:'A'|'B', text:str, meta:dict, ts:iso}

if "settings" not in st.session_state:
    st.session_state["settings"] = {
        "translate": True,
        "target_lang": "ta",
        "output_pref": "both",  # audio | text | both
        #"original_actions": {"text_to_audio": False, "audio_to_text": False, "generate_summary": False},
    }

if "active_user" not in st.session_state:
    st.session_state["active_user"] = "A"

if "mic_audio_last" not in st.session_state:
    st.session_state["mic_audio_last"] = None

LANG_LABEL = {"en": "English", "ta": "Tamil", "hi": "Hindi", "devanagari": "Hindi (Devanagari)", "unknown": "Unknown"}


# ---------------- Helpers ----------------
def add_message(role: str, user: str, text: str, meta: dict | None = None):
    st.session_state["messages"].append(
        {"role": role, "user": user, "text": text or "", "meta": meta or {}, "ts": datetime.utcnow().isoformat()}
    )


def current_payload_base():
    s = st.session_state["settings"]
    return {
        "target_lang": s["target_lang"],
        "output_pref": s["output_pref"],
        "user_id": st.session_state["active_user"],
        "translate": s["translate"],
        #"original_actions": s["original_actions"],
    }


def _best_text_from_result(r: dict) -> str:
    return (
        r.get("summary")
        or r.get("translated_text")
        or r.get("source_text")
        or r.get("transcribed_text")
        or ""
    )


def _audio_url_for(path: str) -> str:
    # backend stores path under static/..., it might return relative path or absolute. Ensure proper quoting.
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{BACKEND_BASE}/{urllib.parse.quote(path)}"


def _json_url_for(path: str) -> str:
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{BACKEND_BASE}/{urllib.parse.quote(path)}"


# ---------------- Backend interaction helpers ----------------
def call_text_translate(payload: dict) -> dict:
    try:
        resp = requests.post(f"{BACKEND_BASE}/api/text/translate", json=payload, timeout=60)
        if resp.status_code == 200:
            return resp.json()
        return {"error": "backend_error", "status_code": resp.status_code, "text": resp.text}
    except Exception as e:
        return {"error": "request_failed", "message": str(e)}


def call_file_upload(endpoint: str, tmp_path: str, filename: str, mime: str, payload: dict) -> dict:
    try:
        with open(tmp_path, "rb") as fh:
            files = {"file": (filename, fh, mime or "application/octet-stream")}
            resp = requests.post(f"{BACKEND_BASE}{endpoint}", files=files, data=payload, timeout=240)
        if resp.status_code == 200:
            return resp.json()
        return {"error": "backend_error", "status_code": resp.status_code, "text": resp.text}
    except Exception as e:
        return {"error": "request_failed", "message": str(e)}


# ---------------- Action handlers (callbacks) ----------------
def handle_send_callback():
    """
    Called by SEND button. Reads current widget values (text or file) and processes exactly once.
    After processing we call st.rerun()so uploader resets cleanly.
    """
    uploaded_file = st.session_state.get("file_up")  # widget key
    chat_input = st.session_state.get("chat_input", "").strip()

    # If there's an uploaded file -> process file (priority). Else process text (if any).
    if uploaded_file is not None:
        # Add user bubble
        add_message("user", st.session_state["active_user"], f"[File uploaded] {uploaded_file.name}")

        # Save temp file
        tmp_dir = tempfile.gettempdir()
        safe_name = uploaded_file.name.replace(" ", "_")
        tmp_path = os.path.join(tmp_dir, safe_name)
        with open(tmp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Choose endpoint by extension
        name = uploaded_file.name.lower()
        if name.endswith((".mp3", ".wav", ".m4a")):
            endpoint = "/api/audio/upload"
            mime = uploaded_file.type or "audio/*"
        elif name.endswith((".mp4", ".mkv", ".avi", ".mov", ".mpeg", ".mpg")):
            endpoint = "/api/video/upload"
            mime = uploaded_file.type or "video/*"
        elif name.endswith((".jpg", ".jpeg", ".png")):
            endpoint = "/api/image/upload"
            mime = uploaded_file.type or "image/*"
        elif name.endswith((".pdf", ".docx", ".txt")):
            endpoint = "/api/document/upload"
            mime = uploaded_file.type or "application/octet-stream"
        else:
            add_message("assistant", "system", f"Unsupported file type: {uploaded_file.name}")
            try:
                os.remove(tmp_path)
            except:
                pass
            st.rerun()
            return

        payload = current_payload_base()
        r = call_file_upload(endpoint, tmp_path, uploaded_file.name, mime, payload)

        # Clean up temp file
        try:
            os.remove(tmp_path)
        except:
            pass

        # Build assistant bubble (respect output_pref)
        if r.get("error"):
            err = r.get("error")

            # ===== 1) Unsafe content =====
            if err in ("unsafe_content", "unsafe"):
                cat = r.get("category", "unknown")
                flagged = r.get("flagged_word", "")
                reason = r.get("reason", "Unsafe content detected")

                add_message(
                    "assistant",
                    "system",
                    f" Message blocked (unsafe content)\n\n"
                    f"**Category:** {cat}\n"
                    f"**Reason:** {reason}\n"
                    f"**Flagged phrase:** {flagged}",
                    meta={"source": r}
                )

                # Clear the UI inputs so user sees cleared uploader/text
                st.session_state["clear_file"] = True
                st.session_state["chat_input"] = ""
                st.rerun()
                return

            # ===== 2) File too large =====
            if err == "file_too_large":
                msg = r.get("message", "File too large")
                limit = r.get("allowed_size_mb", 0)
                add_message(
                    "assistant",
                    "system",
                    f"File too large.\n\n{msg}\n\nMax allowed: {limit} MB",
                    meta={"source": r}
                )

                st.session_state["clear_file"] = True
                st.session_state["chat_input"] = ""
                st.rerun()
                return

            # ===== 3) Unsupported format =====
            if err == "unsupported_format":
                allowed = ", ".join(r.get("allowed_formats", []))
                add_message(
                    "assistant",
                    "system",
                    f"Unsupported file format.\nAllowed formats: {allowed}",
                    meta={"source": r}
                )

                st.session_state["clear_file"] = True
                st.session_state["chat_input"] = ""
                st.rerun()
                return

            # ===== 4) Generic error =====
            add_message(
                "assistant",
                "system",
                f"Error: {html.escape(str(r))}",
                meta={"source": r}
            )

            st.session_state["clear_file"] = True
            st.session_state["chat_input"] = ""
            st.rerun()
            return

        else:
            raw = _best_text_from_result(r)
            safe = html.escape(raw, quote=False)
            if st.session_state["settings"]["output_pref"] == "audio":
                safe = ""

            add_message("assistant", "system", "", meta={"source": r, "raw_text": raw})

        # force rerun to reset uploader widget
        st.rerun()
        return

    # No file - process text if any
    if chat_input:
        add_message("user", st.session_state["active_user"], chat_input)

        payload = current_payload_base()
        payload["text"] = chat_input

        r = call_text_translate(payload)

        if r.get("error"):
            err = r.get("error")

            # ===== UNSAFE CONTENT =====
            if err in ("unsafe", "unsafe_content"):
                cat = r.get("category", "unknown")
                flagged = r.get("flagged_word", "")
                reason = r.get("reason", "Unsafe content detected")

                add_message(
                    "assistant",
                    "system",
                    f"Message blocked (unsafe content)\n\n"
                    f"**Category:** {cat}\n"
                    f"**Reason:** {reason}\n"
                    f"**Flagged phrase:** {flagged}",
                    meta={"source": r}
                )
                st.session_state["clear_file"] = True
                st.session_state["chat_input"] = ""
                st.rerun()
                return

            # ===== GENERIC ERROR =====
            add_message(
                "assistant",
                "system",
                "Something went wrong while processing your message.",
                #f" Error: {html.escape(str(r))}",
                meta={"source": r}
            )
            st.rerun()
            return
        
        # ---------- SUCCESS ----------
        raw = _best_text_from_result(r)
        safe = html.escape(raw, quote=False)

        if st.session_state["settings"]["output_pref"] == "audio":
            safe = ""

        add_message("assistant", "system", "", meta={"source": r, "raw_text": raw})

        # Clear chat_input safely by setting session_state inside callback
        # (allowed since this is a callback triggered by the button)
        st.session_state["chat_input"] = ""
        # no need to rerun here — but rerun keeps UI consistent
        st.rerun()
        return

    # nothing to send
    return


def handle_mic_process(audio_bytes: bytes):
    """
    Processes mic-recorded audio. Called from main loop when audio_bytes appears.
    Runs independently (simple).
    """
    if not audio_bytes:
        return

    # Avoid reprocessing same audio
    if audio_bytes == st.session_state.get("mic_audio_last"):
        return

    st.session_state["mic_audio_last"] = audio_bytes

    # show user bubble with audio player (local)
    add_message("user", st.session_state["active_user"], "[Mic recording]", meta={"mic_bytes": audio_bytes})

    # save temporary wav and upload to backend
    tmp_path = os.path.join(tempfile.gettempdir(), f"mic_{int(datetime.utcnow().timestamp())}.wav")
    with open(tmp_path, "wb") as f:
        f.write(audio_bytes)

    payload = current_payload_base()
    r = call_file_upload("/api/audio/upload", tmp_path, os.path.basename(tmp_path), "audio/wav", payload)

    try:
        os.remove(tmp_path)
    except:
        pass

    # if r.get("error"):
    #     add_message("assistant", "system", f"[Mic error] {html.escape(str(r))}", meta={"source": r})
    #     # do not rerun here — allow user to continue
    #     return

    if r.get("error"):
        err = r.get("error")

        # Unified unsafe detection
        if err in ("unsafe", "unsafe_content"):
            cat = r.get("category", "unknown")
            flagged = r.get("flagged_word", "")
            reason = r.get("reason", "Unsafe content detected")

            add_message(
                "assistant",
                "system",
                f"Message blocked (unsafe content)\n\n"
                f"**Category:** {cat}\n"
                f"**Reason:** {reason}\n"
                f"**Flagged phrase:** {flagged}",
                meta={"source": r}
            )

            return

        # Other mic errors
        add_message(
            "assistant",
            "system",
            f"[Mic error] {err}",
            meta={"source": r}
        )

        #st.session_state["audio_bytes"] = None
        #st.rerun()

        return

    raw = _best_text_from_result(r)
    safe = html.escape(raw, quote=False)
    if st.session_state["settings"]["output_pref"] == "audio":
        safe = ""
    #add_message("assistant", "system", "", meta={"source": r, "raw_text": raw})
    
    meta_data = {"source": r, "raw_text": raw}

    # If backend returns only translated audio => duplicate as audio_source for UI
    if r.get("translated_audio") and not r.get("audio_source"):
        meta_data["source"]["audio_source"] = r["translated_audio"]

    # DEBUG: see what backend really returned
    meta_data["debug_keys"] = list(r.keys())
    meta_data["debug_raw"] = r    

    add_message("assistant", "system", "", meta=meta_data)
    # no rerun here


# ---------------- UI LAYOUT ----------------
left_col, right_col = st.columns([3, 1])

# ---------------- Right column: Settings & workflow ----------------
with right_col:
    st.markdown("")
    st.header("⚙️ Settings")
    s = st.session_state["settings"]

    translate_choice = st.radio("Translate chat?", ("Yes", "No"), index=0 if s["translate"] else 1)
    translate_enabled = translate_choice == "Yes"
    disable_trans = not translate_enabled
    disable_orig_actions = translate_enabled

    lang_options = {"ta (Tamil)": "ta", "en (English)": "en", "hi (Hindi)": "hi"}
    labels = list(lang_options.keys())
    try:
        current_index = list(lang_options.values()).index(s["target_lang"])
    except:
        current_index = 0

    selected_label = st.selectbox("Target Language", labels, index=current_index, disabled=disable_trans)
    output_choice = st.radio(
        "Output Preference",
        ("Only Audio", "Only Text", "Both Audio and Text"),
        index=0 if s["output_pref"] == "audio" else 1 if s["output_pref"] == "text" else 2,
        disabled=disable_trans,
    )

    apply_btn = st.button("💾 Apply settings")

    st.markdown("---")
    if st.button("🔁 Switch User (A ⇄ B)"):
        st.session_state["active_user"] = "B" if st.session_state["active_user"] == "A" else "A"

    st.write("Active user:", st.session_state["active_user"])

    # with st.expander("📌 Workflow Visualization", expanded=False):
    #     static_graph_path = os.path.join("static", "graph", "langgraph_workflow.png")
    #     if os.path.exists(static_graph_path):
    #         st.image(static_graph_path, use_container_width=True)
    #     elif os.path.exists(WORKFLOW_LOCAL_PATH):
    #         try:
    #             st.image(WORKFLOW_LOCAL_PATH, use_container_width=True)
    #         except:
    #             st.info(f"Workflow image at {WORKFLOW_LOCAL_PATH} could not be loaded.")
    #     else:
    #         st.info("Workflow image not found.")

    with st.expander("📌 Workflow Visualization", expanded=False):
        backend_image_url = f"{BACKEND_BASE}/static/graph/langgraph_workflow.png"

        try:
            response = requests.get(backend_image_url, timeout=5)

            if response.status_code == 200:
                img = Image.open(BytesIO(response.content))
                st.image(img, use_container_width=True)
            else:
                st.info("Workflow image not found on backend.")
        except Exception:
            st.info("Workflow image not found.")

    if apply_btn:
        s["translate"] = translate_enabled
        s["target_lang"] = lang_options[selected_label]
        s["output_pref"] = "audio" if output_choice == "Only Audio" else "text" if output_choice == "Only Text" else "both"
        
        st.success("Settings applied ✔")

# ---------------- Left column: Chat + Input ----------------
with left_col:

    st.markdown("")
    st.header("Chat ↻")
    st.markdown("---")

    # SAFELY clear the uploader after rerun
    if st.session_state.get("clear_file"):
        st.session_state["clear_file"] = False
        st.session_state.pop("file_up", None)
    
    # Chat scroll area
    st.markdown("<div class='chat-area'>", unsafe_allow_html=True)

    for msg in st.session_state["messages"]:
        role = msg["role"]
        user = msg["user"]
        text = msg["text"]
        meta = msg.get("meta", {}) or {}

        if role == "user":
            # user left bubble
            html_block = f"""
            <div class='msg user'>
                <div class='bubble'>
                    <b>User {html.escape(user)}</b><br>
                    {html.escape(text)}
                </div>
            </div>
            """
            st.markdown(html_block, unsafe_allow_html=True)
            # show mic bytes if present
            if meta.get("mic_bytes"):
                st.audio(meta["mic_bytes"], format="audio/wav")
            continue

        # system bubble (right)
        src = meta.get("source", {}) or {}
        attachments = ""

        # ================= DEBUG DISPLAY (ADD THIS) =================
        # if "debug_keys" in meta:
        #     attachments += f"<div class='meta'><b>DEBUG Keys:</b> {meta['debug_keys']}</div>"

        # if "debug_raw" in meta:
        #     attachments += (
        #         "<pre style='font-size:10px;color:#444;background:#eee;"
        #         "padding:6px;border-radius:6px;'>"
        #         f"{html.escape(str(meta['debug_raw']))}"
        #         "</pre>"
        #     )
        # ============================================================


        # Show main system message text (errors, moderation, notices)
        main_text_html = ""
        if msg["text"]:
            main_text_html = f"<div class='meta'>{html.escape(msg['text'])}</div>"

        # Detected language
        det = src.get("detected_lang")
        if det:
            attachments += f"<div class='meta'><b>Detected Language:</b> {LANG_LABEL.get(det, det)}</div>"

        tlang = src.get("target_lang")
        if tlang:
            attachments += f"<div class='meta'><b>Target Language:</b> {LANG_LABEL.get(tlang, tlang)}</div>"

        # JSON link
        jp = src.get("json_path")
        if jp:
            jurl = _json_url_for(jp)
            attachments += f"<div class='meta'>📄 <a href='{jurl}' target='_blank'>Result JSON</a></div>"

        # Decide display per settings
        show_text = st.session_state["settings"]["output_pref"] in ("text", "both")
        show_audio = st.session_state["settings"]["output_pref"] in ("audio", "both")

        # Unified safe source text resolver
        source_text = (
            src.get("source_text") or        # normal text/doc
            src.get("transcribed_text") or   # audio/mic
            src.get("cleaned") or            # some pipelines give cleaned text
            src.get("text") or               # OCR or fallback raw
            ""
        )

        # Source text
        if show_text and source_text:
            attachments += f"<div class='meta'><b>Source Text:</b><div>{html.escape(source_text)}</div></div>"

        # Translated text (target)
        #if show_text and src.get("translated_text"):
            #attachments += f"<div class='meta'><b>Translated:</b><div>{html.escape(src['translated_text'])}</div></div>"

        # For long documents show summaries if present
        summary_source = src.get("summary_source")
        if show_text and summary_source:
            attachments += f"<div class='meta'><b>Summary (source):</b><div>{html.escape(summary_source)}</div></div>"

        # if show_text and src.get("translated_text") and src.get("summary_source"):  # long-doc case -> translated summary might be in translated_text or specific key
        #     # if long doc translated summary is under translated_text or summary_translated (not used here), show translated_text
        #     attachments += f"<div class='meta'><b>Summary (translated):</b><div>{html.escape(src.get('translated_text'))}</div></div>"

        # Translated text (always show if exists)
        translated = src.get("translated_text")
        if show_text and translated:
            attachments += f"""
            <div class='meta'>
                <b>Translated Text:</b><br>
                <div>{html.escape(translated)}</div>
            </div>
            """

        # Summary (translated) for long docs
        summary_translated = src.get("summary_translated")
        if show_text and summary_translated:
            attachments += f"""
            <div class='meta'>
                <b>Summary (Translated):</b><br>
                <div>{html.escape(summary_translated)}</div>
            </div>
            """

        # Audio players + download links
        def audio_block(key, label):
            path = src.get(key)
            if not path:
                return ""
            url = _audio_url_for(path)
            # audio tag + download anchor
            return f"<div class='meta'><b>{label}:</b><br><audio controls src='{url}'></audio>" \
                   f"<a class='download-link' href='{url}' download>Download</a></div>"

        if show_audio:
            for k, lbl in [
                ("audio_source", "Source audio"),
                ("summary_audio_source", "Source summary audio"),
                ("translated_audio", "Translated audio"),
                ("audio_target", "Translated audio"),
            ]:
                attachments += audio_block(k, lbl)

        # Compose bubble
        bubble_html = (
            "<div class='msg system'>"
            "<div class='bubble'>"
            "<b>System</b><br>"
            f"{main_text_html}"
            f"{attachments}"
            "</div>"
            "</div>"
        )
        st.markdown(bubble_html, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)  # close chat-area

    # ---------- Input bar (sticky look) ----------
    st.markdown("<div style='position:sticky; bottom:0; padding-top:8px; background:#fff;'>", unsafe_allow_html=True)
    st.markdown("<div style='display:flex; gap:8px; align-items:center;'>", unsafe_allow_html=True)

    # Column layout for input elements inside main column area
    c1, c2, c3, c4 = st.columns([0.7, 6, 0.8, 1.2])

    with c1:
        with st.popover("➕", use_container_width=False):
            st.markdown(
                """
                <style>
                    .upload-box label { font-size:13px !important; }
                    .upload-box .stRadio { font-size:13px !important; }
                    .upload-pop { width:260px !important; }
                </style>
                """,
                unsafe_allow_html=True,
            )

            st.markdown("<div class='upload-pop'>", unsafe_allow_html=True)

            upload_type = st.radio(
                "Upload type:",
                ["Any", "Document", "Images / Videos", "Audio"],
                index=0,
                key="upload_type_selector",
            )

            # compact height
            if upload_type == "Document":
                uploaded_file = st.file_uploader(
                    "Choose document:",
                    type=["pdf", "docx", "txt"],
                    key="file_up",
                )
            elif upload_type == "Images / Videos":
                uploaded_file = st.file_uploader(
                    "Choose image/video:",
                    type=["jpg","jpeg","png","mp4","mkv","avi","mov"],
                    key="file_up",
                )
            elif upload_type == "Audio":
                uploaded_file = st.file_uploader(
                    "Choose audio:",
                    type=["mp3","wav","m4a"],
                    key="file_up",
                )
            else:
                uploaded_file = st.file_uploader(
                    "Choose file:",
                    type=["jpg","jpeg","png","mp4","mkv","avi","mov",
                        "mp3","wav","m4a",
                        "pdf","docx","txt"],
                    key="file_up",
                )

            st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.text_input("Type a message…", key="chat_input", label_visibility="collapsed")

    with c3:
        audio_bytes = audio_recorder(text="", icon_size="1.4x", recording_color="#F50612", neutral_color="#9CA3AF")

    with c4:
        # Use on_click to avoid direct calls at module-level
        st.button("⬆ Send", on_click=handle_send_callback, use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # mic status hint
    if audio_bytes and audio_bytes != st.session_state.get("mic_audio_last"):
        st.info("Mic recording captured. Processing...")
    elif not audio_bytes:
        st.caption("Click mic to start / stop recording.")


# ------------------ Process mic outside layout (non-blocking) ------------------
# If audio_bytes captured, process it once
if "audio_bytes" not in st.session_state:
    st.session_state["audio_bytes"] = None

# audio_recorder returns bytes in audio_bytes variable on this run. If present and different from last, call processing.
if audio_bytes and audio_bytes != st.session_state.get("mic_audio_last"):
    # run processing (no rerun inside)
    handle_mic_process(audio_bytes)

# ---------------- Footer ----------------
st.caption("Backend must run at " + BACKEND_BASE)
