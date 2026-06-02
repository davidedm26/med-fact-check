import os
from typing import Iterable, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from utils.config import config


def _get_env(name: str, fallback: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    return value if value else fallback


def _require(value: Optional[str], name: str) -> str:
    if value:
        return value
    raise ValueError(f"{name} environment variable is required")


def _provider_api_key(provider: str) -> Optional[str]:
    if provider == "nvidia":
        return _get_env("NVIDIA_API_KEY")
    if provider == "google":
        return _get_env("GOOGLE_API_KEY")
    if provider == "groq":
        return _get_env("GROQ_API_KEY")
    return None


def get_llm_with_tools(
    tools: Iterable[object], 
    *, # The asterisk here forces all following parameters to be passed as keyword arguments
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    allow_tools: Optional[bool] = None,
) -> BaseChatModel:
    """
    Initialize an LLM based on the provider and bind tools to it.
    The rest of the code should treat this as a provider-agnostic LLM.
    """
    resolved_provider = (provider or config.get("llm.provider", "ollama")).lower()
    resolved_temperature = temperature
    if resolved_temperature is None:
        resolved_temperature = float(_get_env("LLM_TEMPERATURE", "0"))

    resolved_timeout = config.get("llm.timeout", 30)
    resolved_retries = config.get("llm.retries", 5)

    provider_settings = config.get(f"llm.providers.{resolved_provider}", {})

    if resolved_provider == "groq":
        try:
            from langchain_groq import ChatGroq
        except ImportError as exc:
            raise ImportError("Missing dependency: langchain-groq") from exc

        resolved_model = model_name or provider_settings.get("model_name", _get_env("GROQ_MODEL_NAME", "llama3-70b-8192"))
        resolved_key = api_key or _provider_api_key(resolved_provider)
        llm = ChatGroq(
            model_name=resolved_model,
            temperature=resolved_temperature,
            api_key=_require(resolved_key, "GROQ_API_KEY"),
            timeout=resolved_timeout,
            max_retries=resolved_retries,
        )

    elif resolved_provider == "nvidia":
        from langchain_openai import ChatOpenAI

        resolved_model = model_name or provider_settings.get("model_name", _get_env("NVIDIA_MODEL_NAME", "meta/llama3-70b-instruct"))
        resolved_key = api_key or _provider_api_key(resolved_provider)
        resolved_base_url = base_url or provider_settings.get("base_url", _get_env("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"))
        llm = ChatOpenAI(
            model=resolved_model,
            temperature=resolved_temperature,
            api_key=_require(resolved_key, "NVIDIA_API_KEY"),
            base_url=resolved_base_url,
            timeout=resolved_timeout,
            max_retries=resolved_retries,
        )

    elif resolved_provider == "google":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:
            raise ImportError("Missing dependency: langchain-google-genai") from exc

        resolved_model = model_name or provider_settings.get("model_name", _get_env("GOOGLE_MODEL_NAME", "gemini-1.5-pro-002"))
        resolved_key = api_key or _provider_api_key(resolved_provider)
        llm = ChatGoogleGenerativeAI(
            model=resolved_model,
            temperature=resolved_temperature,
            google_api_key=_require(resolved_key, "GOOGLE_API_KEY"),
            timeout=resolved_timeout,
            max_retries=resolved_retries,
        )

    elif resolved_provider == "ollama":
        try:
            from langchain_ollama import ChatOllama
        except ImportError as exc:
            raise ImportError("Missing dependency: langchain-ollama") from exc

        resolved_model = model_name or provider_settings.get("model_name", _get_env("OLLAMA_MODEL_NAME", "llama3:8b"))
        resolved_base_url = base_url or provider_settings.get("base_url", _get_env("OLLAMA_PROVIDER_BASE_URL", "http://localhost:11434"))
        llm = ChatOllama(
            model=resolved_model,
            temperature=resolved_temperature,
            base_url=resolved_base_url,
            timeout=resolved_timeout,
            max_retries=resolved_retries,
        )

    else:
        raise ValueError(f"Unsupported provider: {resolved_provider}")

    if allow_tools is False: # If allow_tools is explicitly set to False, we bind an empty list of tools to disable tool usage, even if tools are provided.
        return llm.bind_tools([], tool_choice="none")
    
    tool_list = list(tools)
    if not tool_list:
        return llm

    return llm.bind_tools(tool_list)
