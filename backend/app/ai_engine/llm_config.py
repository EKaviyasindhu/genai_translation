# backend/app/ai_engine/llm_config.py

"""
Reuses the SAME ChatOpenAI LLM you already created in translation_service.py.
No new keys, no new models.
"""

from app.services.translation_service import llm as _translator_llm


def get_router_llm():
    """
    LLM used by the routing agent (for deciding which handler to call).
    Returns None if LLM not configured.
    """
    return _translator_llm
