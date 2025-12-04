from dotenv import load_dotenv
import os
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "translation_db")

# File size limits (WhatsApp-like 16 MB)
MAX_UPLOAD_MB = 16
AUDIO_EXTS = ['.mp3', '.wav', '.m4a']
VIDEO_EXTS = ['.mp4', '.mkv', '.mov', '.avi']
DOC_EXTS = ['.pdf', '.docx', '.txt']
ALLOWED_EXTS = AUDIO_EXTS + VIDEO_EXTS + DOC_EXTS

# Enable or disable Demucs voice enhancement
USE_DEMUCS = False  #True   # set True to enable, False to disable