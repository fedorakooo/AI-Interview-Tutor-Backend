from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from src.config import settings

load_dotenv()


class LLMFactory:
    @staticmethod
    def create_google_llm():
        return ChatGoogleGenerativeAI(
            model=settings.google_llm.model,
            temperature=settings.google_llm.temperature,
        )

    @staticmethod
    def create_custom_llm():
        return ChatOpenAI(
            openai_api_base=settings.custom_llm.api_base,
            openai_api_key=settings.custom_llm.api_key,
            model=settings.custom_llm.model,
            temperature=settings.custom_llm.temperature,
        )


llm = LLMFactory.create_google_llm()
