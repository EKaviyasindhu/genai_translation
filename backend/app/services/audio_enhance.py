import subprocess, tempfile, uuid, os
from ..config.settings import USE_DEMUCS

def enhance_voice(input_audio: str) -> str:
    
    """
    When USE_DEMUCS = True → run Demucs vocal separation
    When USE_DEMUCS = False → return raw audio (no enhancement)
    """
    if not USE_DEMUCS:     # Config switch
        return input_audio
    
    try:
        out_dir = os.path.join(tempfile.gettempdir(), f"demucs_{uuid.uuid4().hex}")
        subprocess.run(["demucs", "--two-stems", "vocals", "-o", out_dir, input_audio], check=True)

        base = os.path.splitext(os.path.basename(input_audio))[0]
        enhanced = os.path.join(out_dir, "htdemucs", base, "vocals.wav")

        return enhanced if os.path.exists(enhanced) else input_audio

    except Exception as e:
        print("Demucs enhancement failed:", e)
        return input_audio
