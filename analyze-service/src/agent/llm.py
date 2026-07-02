from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from src.config import LLMProvider, settings

load_dotenv()


class LLMFactory:
    @staticmethod
    def _provider_temperature(provider: LLMProvider) -> float:
        match provider:
            case LLMProvider.OPENAI:
                return settings.openai_llm.temperature
            case LLMProvider.OPENROUTER:
                return settings.openrouter_llm.temperature
            case LLMProvider.GOOGLE:
                return settings.google_llm.temperature

    @staticmethod
    def create_llm() -> BaseChatModel:
        provider = settings.llm_provider
        temperature = settings.analyze_llm_temperature or LLMFactory._provider_temperature(provider)

        match provider:
            case LLMProvider.OPENAI:
                if not settings.openai_api_key:
                    raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
                return ChatOpenAI(
                    api_key=settings.openai_api_key,
                    model=settings.openai_llm.model,
                    temperature=temperature,
                )
            case LLMProvider.OPENROUTER:
                if not settings.openrouter_api_key:
                    raise ValueError("OPENROUTER_API_KEY is required when LLM_PROVIDER=openrouter")
                return ChatOpenAI(
                    openai_api_base=settings.openrouter_llm.api_base,
                    openai_api_key=settings.openrouter_api_key,
                    model=settings.openrouter_llm.model,
                    temperature=temperature,
                )
            case LLMProvider.GOOGLE:
                if not settings.google_api_key:
                    raise ValueError("GOOGLE_API_KEY is required when LLM_PROVIDER=google")
                from langchain_google_genai import ChatGoogleGenerativeAI

                return ChatGoogleGenerativeAI(
                    model=settings.google_llm.model,
                    temperature=temperature,
                )
            case _:
                valid = ", ".join(p.value for p in LLMProvider)
                raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}. Valid values: {valid}")


llm = LLMFactory.create_llm()
