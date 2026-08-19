from typing import Optional
import logging
from langchain_core.language_models.chat_models import BaseChatModel
from app.core.config import settings

logger = logging.getLogger("llm_service")

def get_llm_model(provider: str, model_name: Optional[str] = None) -> BaseChatModel:
    """
    Factory function to initialize and return the correct Langchain chat model.
    """
    provider_clean = provider.lower().strip()
    
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
