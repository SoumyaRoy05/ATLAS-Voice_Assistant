import logging
import os
import socket
from pathlib import Path

from dotenv import load_dotenv
from pydantic import SecretStr

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama

load_dotenv(Path(__file__).resolve().parent / ".env")


class _AfcWarningFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "Direct use of automatic function calling" not in record.getMessage()


logging.getLogger("google_genai.models").addFilter(_AfcWarningFilter())

def is_online(host: str = "8.8.8.8", port: int = 53, timeout: float = 1.0) -> bool:
    """Checks DNS connectivity to skip cloud timeouts when offline."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
        return True
    except OSError:
        return False


gemini_key = os.getenv("GEMINI_API_KEY")
groq_key = os.getenv("GROQ_API_KEY")
request_timeout = float(os.getenv("ATLAS_LLM_TIMEOUT", "8"))


def _secret(value: str | None) -> SecretStr | None:
    return SecretStr(value) if value else None


def _build_groq(model: str) -> ChatGroq:
    return ChatGroq(
        model=model,
        temperature=0.7,
        max_tokens=512,
        reasoning_effort="low",
        reasoning_format="hidden",
        timeout=request_timeout,
        max_retries=0,
        api_key=_secret(groq_key),
    )


def _build_gemini(model: str) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=model,
        temperature=0.7,
        max_tokens=128,
        timeout=request_timeout,
        max_retries=0,
        thinking_level="low",
        google_api_key=_secret(gemini_key),
    )


# Groq is first because both models were verified successfully. Gemini remains
# useful when Groq is unavailable, and Ollama is the final offline fallback.
t1a = _build_groq("openai/gpt-oss-120b") if groq_key else None
t1b = _build_groq("openai/gpt-oss-20b") if groq_key else None
t2a = _build_gemini("gemini-3.8-flash") if gemini_key else None
t2b = _build_gemini("gemini-3.7-flash") if gemini_key else None
t3 = ChatOllama(model="qwen2.5:3b", temperature=0.7, num_predict=128)


def _available_cloud_models():
    return [provider for provider in (t1a, t1b, t2a, t2b) if provider is not None]


def _make_waterfall(online: bool):
    candidates = _available_cloud_models() + [t3] if online else [t3]
    primary, *fallbacks = candidates
    return primary.with_fallbacks(fallbacks, exceptions_to_handle=(Exception,))


def get_llm():
    """Return a fast cloud-first chain, or local Ollama when offline."""
    return _make_waterfall(is_online())

llm_waterfall = _make_waterfall(is_online())