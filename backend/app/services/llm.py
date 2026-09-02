from typing import Optional
import logging
from langchain_core.language_models.chat_models import BaseChatModel
from app.core.config import settings

logger = logging.getLogger("llm_service")

SUPPORTED_PROVIDERS = [
    {
        "id": "gemini",
        "name": "Google Gemini",
        "models": [
            "gemini-3.1-flash-lite",
            "gemini-2.5-flash",
            "gemini-2.5-pro",
        ],
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "models": [
            "gpt-4o-mini",
            "gpt-4o",
            "o1-mini",
        ],
    },
    {
        "id": "anthropic",
        "name": "Anthropic Claude",
        "models": [
            "claude-3-5-sonnet-latest",
            "claude-3-5-haiku-latest",
        ],
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "models": [
            "google/gemini-2.5-flash",
            "anthropic/claude-3.5-sonnet",
            "meta-llama/llama-3.3-70b-instruct",
        ],
    },
]

def is_provider_configured(provider_id: str) -> bool:
    pid = provider_id.lower().strip()
    if pid == "gemini":
        return bool(settings.GEMINI_API_KEY and not settings.GEMINI_API_KEY.startswith("your_"))
    elif pid == "openai":
        return bool(settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith("your_"))
    elif pid == "anthropic":
        return bool(settings.ANTHROPIC_API_KEY and not settings.ANTHROPIC_API_KEY.startswith("your_"))
    elif pid == "openrouter":
        return bool(settings.OPENROUTER_API_KEY and not settings.OPENROUTER_API_KEY.startswith("your_"))
    return False

def get_available_models_info() -> dict:
    """
    Returns system default provider, system default model, and available providers/models
    with their configured status.
    """
    default_provider = settings.DEFAULT_PROVIDER
    default_model = get_default_model_name(default_provider)
    
    providers_info = []
    for prov in SUPPORTED_PROVIDERS:
        pid = prov["id"]
        prov_default = get_default_model_name(pid)
        models = list(prov["models"])
        if prov_default and prov_default not in models:
            models.insert(0, prov_default)
            
        providers_info.append({
            "id": pid,
            "name": prov["name"],
            "configured": is_provider_configured(pid),
            "default_model": prov_default,
            "models": models,
        })
        
    return {
        "default_provider": default_provider,
        "default_model": default_model,
        "providers": providers_info,
    }

def get_default_model_name(provider: Optional[str] = None) -> str:
    """
    Returns the configured default model name for a given provider (or the global default provider).
    """
    prov = (provider or settings.DEFAULT_PROVIDER).lower().strip()
    if prov == "gemini":
        return settings.DEFAULT_GEMINI_MODEL
    elif prov == "openai":
        return settings.DEFAULT_OPENAI_MODEL
    elif prov == "anthropic":
        return settings.DEFAULT_ANTHROPIC_MODEL
    elif prov == "openrouter":
        return settings.DEFAULT_OPENROUTER_MODEL
    return "unknown"

def get_llm_model(provider: Optional[str] = None, model_name: Optional[str] = None) -> BaseChatModel:
    """
    Factory function to initialize and return the correct Langchain chat model.
    """
    provider_clean = (provider or settings.DEFAULT_PROVIDER).lower().strip()
    
    if provider_clean == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise ValueError("Gemini API key is not configured. Please add gemini_api_key to your .env file.")
            
        model = model_name or settings.DEFAULT_GEMINI_MODEL
        logger.info(f"Initializing Gemini model: {model}")
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=0.7,
        )

    elif provider_clean == "openai":
        from langchain_openai import ChatOpenAI
        
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OpenAI API key is not configured. Please add OPENAI_API_KEY to your .env file.")
            
        model = model_name or settings.DEFAULT_OPENAI_MODEL
        logger.info(f"Initializing OpenAI model: {model}")
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            temperature=0.7,
        )

    elif provider_clean == "anthropic":
        from langchain_anthropic import ChatAnthropic
        
        api_key = settings.ANTHROPIC_API_KEY
        if not api_key:
            raise ValueError("Anthropic API key is not configured. Please add ANTHROPIC_API_KEY to your .env file.")
            
        model = model_name or settings.DEFAULT_ANTHROPIC_MODEL
        logger.info(f"Initializing Anthropic model: {model}")
        return ChatAnthropic(
            model=model,
            api_key=api_key,
            temperature=0.7,
        )

    elif provider_clean == "openrouter":
        from langchain_openai import ChatOpenAI
        
        api_key = settings.OPENROUTER_API_KEY
        if not api_key:
            raise ValueError("OpenRouter API key is not configured. Please add OPENROUTER_API_KEY to your .env file.")
            
        model = model_name or settings.DEFAULT_OPENROUTER_MODEL
        logger.info(f"Initializing OpenRouter model: {model}")
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            temperature=0.7,
        )

    else:
        raise ValueError(
            f"Unsupported provider: '{provider}'. "
            f"Available options are: gemini, openai, anthropic, openrouter."
        )
