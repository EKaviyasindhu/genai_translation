import os

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
OPENAI_KEY = os.getenv('OPENAI_API_KEY', '')
client = OpenAI(api_key=OPENAI_KEY) if OPENAI_KEY else None

def transcribe_with_openai(file_path: str):
    
    """
    Uses OpenAI speech with improved accuracy for Tamil / English / Hindi.
    Automatically detects language.
    """
     
    if client is None:
        return '', 'no-client'
    
    try:
        with open(file_path, "rb") as f:
            res = client.audio.transcriptions.create(
                model="whisper-1",  #gpt-4o-mini-transcribe
                file=f,
                #language="auto",               
                temperature=0,
            )
        return res.text.strip(), "openai"
    
    except Exception as e:
        print('OpenAI transcription failed:', e)
        return '', 'error'

#punctuation fix
from deepmultilingualpunctuation import PunctuationModel
punct_model = PunctuationModel()

def restore_punctuation(text: str) -> str:
    try:
        return punct_model.restore_punctuation(text)
    except:
        return text