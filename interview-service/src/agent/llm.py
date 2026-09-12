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
    def _resolve_model(role: str) -> tuple[str, float | None]:
        routing = settings.model_routing.get(role, {})
        model = routing.get("model")
        temperature = routing.get("temperature")
        provider = settings.llm_provider
        if model:
            return model, temperature
        match provider:
            case LLMProvider.OPENAI:
                return settings.openai_llm.model, temperature
            case LLMProvider.OPENROUTER:
                return settings.openrouter_llm.model, temperature
            case LLMProvider.GOOGLE:
                return settings.google_llm.model, temperature
        return settings.openai_llm.model, temperature

    @staticmethod
    def create_llm(*, role: str = "default", temperature: float | None = None) -> BaseChatModel:
        provider = settings.llm_provider
        model, routed_temperature = LLMFactory._resolve_model(role)
        resolved_temperature = (
            temperature
            if temperature is not None
            else routed_temperature
            if routed_temperature is not None
            else settings.interview_llm_temperature or LLMFactory._provider_temperature(provider)
        )

        match provider:
            case LLMProvider.OPENAI:
                if not settings.openai_api_key:
                    raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
                return ChatOpenAI(
                    api_key=settings.openai_api_key,
                    model=model,
                    temperature=resolved_temperature,
                )
            case LLMProvider.OPENROUTER:
                if not settings.openrouter_api_key:
                    raise ValueError("OPENROUTER_API_KEY is required when LLM_PROVIDER=openrouter")
                return ChatOpenAI(
                    openai_api_base=settings.openrouter_llm.api_base,
                    openai_api_key=settings.openrouter_api_key,
                    model=model,
                    temperature=resolved_temperature,
                )
            case LLMProvider.GOOGLE:
                if not settings.google_api_key:
                    raise ValueError("GOOGLE_API_KEY is required when LLM_PROVIDER=google")
                from langchain_google_genai import ChatGoogleGenerativeAI

                return ChatGoogleGenerativeAI(
                    model=model,
                    temperature=resolved_temperature,
                )
            case _:
                valid = ", ".join(p.value for p in LLMProvider)
                raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}. Valid values: {valid}")


def get_interview_llm(role: str = "default") -> BaseChatModel:
    return LLMFactory.create_llm(role=role)


llm = get_interview_llm("default")
