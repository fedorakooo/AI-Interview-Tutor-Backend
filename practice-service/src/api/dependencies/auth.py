from jwt_handler.handlers import JWTTokenHandler
from jwt_handler.interfaces import ITokenHandler
from src.config import settings


def get_token_handler() -> ITokenHandler:
    return JWTTokenHandler(public_key=settings.jwt_settings.public_key)
