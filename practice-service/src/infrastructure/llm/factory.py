from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from src.config import LLMProvider, settings


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
            case _:
                raise ValueError(f"Unsupported LLM provider: {provider!r}")

    @staticmethod
    def create_llm(*, temperature: float | None = None) -> BaseChatModel:
        provider = settings.llm_provider
        resolved_temperature = temperature if temperature is not None else settings.practice_settings.llm_temperature

        match provider:
            case LLMProvider.OPENAI:
                if not settings.openai_api_key:
                    raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
                return ChatOpenAI(
                    api_key=settings.openai_api_key,
                    model=settings.openai_llm.model,
                    temperature=resolved_temperature,
                    timeout=settings.practice_settings.llm_timeout_seconds,
                )
            case LLMProvider.OPENROUTER:
                if not settings.openrouter_api_key:
                    raise ValueError("OPENROUTER_API_KEY is required when LLM_PROVIDER=openrouter")
                return ChatOpenAI(
                    openai_api_base=settings.openrouter_llm.api_base,
                    openai_api_key=settings.openrouter_api_key,
                    model=settings.openrouter_llm.model,
                    temperature=resolved_temperature,
                    timeout=settings.practice_settings.llm_timeout_seconds,
                )
            case LLMProvider.GOOGLE:
                if not settings.google_api_key:
                    raise ValueError("GOOGLE_API_KEY is required when LLM_PROVIDER=google")
                from langchain_google_genai import ChatGoogleGenerativeAI

                return ChatGoogleGenerativeAI(
                    model=settings.google_llm.model,
                    temperature=resolved_temperature,
                    timeout=settings.practice_settings.llm_timeout_seconds,
                )
            case _:
                valid = ", ".join(provider.value for provider in LLMProvider)
                raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}. Valid values: {valid}")

    @staticmethod
    def create_grader_llm() -> BaseChatModel:
        return LLMFactory.create_llm(temperature=settings.practice_settings.grading_temperature)
