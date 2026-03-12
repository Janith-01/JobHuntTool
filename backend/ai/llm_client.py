"""
LLM Client — Centralized wrapper for Google Gemini via LangChain.
Provides a shared, configurable LLM instance for all AI modules.
"""

import logging
from functools import lru_cache

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from backend.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_llm(
    model: str = "gemini-2.0-flash",
    temperature: float = 0.4,
    max_output_tokens: int = 8192,
) -> ChatGoogleGenerativeAI:
    """
    Get a cached LLM instance.
    
    Uses gemini-2.0-flash for the best balance of speed, quality, and cost.
    Temperature 0.4 gives creative but controlled output — ideal for
    resume writing that needs to sound natural while staying factual.
    """
    if not settings.GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY not set. Add it to your .env file.\n"
            "Get a free key at: https://aistudio.google.com/apikey"
        )

    llm = ChatGoogleGenerativeAI(
        model=model,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        convert_system_message_to_human=True,
    )
    logger.info(f"🤖 LLM initialized: {model} (temp={temperature})")
    return llm


def invoke_llm(
    system_prompt: str,
    user_prompt: str,
    model: str = "gemini-2.0-flash",
    temperature: float = 0.4,
    max_tokens: int = 8192,
) -> str:
    """
    Convenience function to invoke the LLM with system + user messages.
    Returns the text content of the response.
    """
    llm = get_llm(model=model, temperature=temperature, max_output_tokens=max_tokens)

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    try:
        response = llm.invoke(messages)
        return response.content.strip()
    except Exception as e:
        logger.error(f"LLM invocation failed: {e}")
        raise


def invoke_llm_structured(
    system_prompt: str,
    user_prompt: str,
    output_schema: type,
    model: str = "gemini-2.0-flash",
    temperature: float = 0.2,
) -> dict:
    """
    Invoke the LLM and parse the response into a structured Pydantic model.
    Uses LangChain's with_structured_output for reliable JSON extraction.
    """
    llm = get_llm(model=model, temperature=temperature)
    structured_llm = llm.with_structured_output(output_schema)

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    try:
        result = structured_llm.invoke(messages)
        return result
    except Exception as e:
        logger.error(f"Structured LLM invocation failed: {e}")
        raise
