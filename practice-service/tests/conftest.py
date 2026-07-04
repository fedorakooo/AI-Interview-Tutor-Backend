import os
from uuid import uuid4

import pytest
from jwt_handler.handlers import JWTTokenHandler
from jwt_handler.value_objects import AccessTokenPayload, TokenType

PUBLIC_KEY = os.environ.get(
    "PUBLIC_KEY",
    "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAuquv2JAEa9o5FBFw87Xl\nAoCUK7JNh5YPX9aFZibJxDBpBmpO5Ub9+3sSIUf2KLqk68NtajohV4LiMa+dihrS\nNyDXMP9drytEYVawc9jVl9wlIHTFoR5oSUhB8iMMPYAzpheHrVe62OYzqTjU1BOd\nDBU3oJUOzYzvVh59TkUVfScRvThPskx4oURcmO49WwbuTEqTnf4p4NiLi38qgmje\n9TXuXn4CPsdsoeLEPmBrJwRNMpnM3LXSgM6j15VdqYRUhDXp7P1+RDtt+bc6E4OG\nhz69opoPEcHZg8w7n1z3wX/T4n0vo7mk8h4Khm3D+n0SqHwjpYM4lM3lixnMN/8+\nMwIDAQAB\n-----END PUBLIC KEY-----\n",
)
PRIVATE_KEY = os.environ.get(
    "PRIVATE_KEY",
    "-----BEGIN PRIVATE KEY-----\nMIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQC6q6/YkARr2jkU\nEXDzteUCgJQrsk2Hlg9f1oVmJsnEMGkGak7lRv37exIhR/YouqTrw21qOiFXguIx\nr52KGtI3INcw/12vK0RhVrBz2NWX3CUgdMWhHmhJSEHyIww9gDOmF4etV7rY5jOp\nONTUE50MFTeglQ7NjO9WHn1ORRV9JxG9OE+yTHihRFyY7j1bBu5MSpOd/ing2IuL\nfyqCaN71Ne5efgI+x2yh4sQ+YGsnBE0ymczctdKAzqPXlV2phFSENens/X5EO235\ntzoTg4aHPr2img8RwdmDzDufXPfBf9PifS+juaTyHgqGbcP6fRKofCOlgziUzeWL\nGcw3/z4zAgMBAAECggEADziwvhgAREsnHFvPug+6/Nk/O9DuQYAbANWdSxcenMDV\nz5AbntaLH1aJw+z6RZfymsb0xRS4Y0po52RKlFhbi+NBqN0p5n7AtK889DVaNWfe\nHydmdhzkpBUgS35QITOzAngouBnPQqCC1emscR6oT7PrNUzySBCV84/I5/j6J5pE\nOVz057IRpTvMOCHQtW+84tHCIuBxrFJThtKAqb0R4kowx9mbpUHFEKV9auyNLItM\nwHBJmkca+c1oW7EnYAtgtJGwmSanRWY71JoT/Di0HnNwPXoxGBFrUGsk00qHaiAF\nmP+vPZTS5hasBN8NP0Rg881jV0k9krNIpu4f5ubIAQKBgQDrB0TUUhshamU750X1\n/IVhNR4tXsQx0D0iHmigVe+cDYzPH/YgCwNbpOc7+9Q1Cc7xCnjRIrXYzsN697G0\n04GiFRtvyeC3KHNu14aCyfukrsAiGuEfWh/WC2F2WmfUQ3RHyyQ+mcHBRX78A3hg\nRfELTEQNtha46Jpks0OMUKMc4QKBgQDLU8lowfdofkaH+pDce5xEJ1WNHWDXQwCX\nvgtzXBpt25XQM01284Gn3dF4JPHDeYuGhD8pNV3/yKLRD7iXJluSPrOF4Z2GJd1m\nFmkF7nrWAYWRhbCS3dX4pty5FLN54VRf+G+KdpyoIjLiRRxguE0q/gXsUnY64pRN\nACKRrMnJkwKBgCEB4FTBQzYqLxV+oYCuejzwrNBKYttsF2nXQ3JhH0mXTZM5NePC\nKDKSsjbmYyMfwYRwqA8XBNryDtoSN07h9W7B8Bx/CaQvdia29hkgLMswD6O6iqtQ\niPASoRlyEOrqnkYG7YwtI9z02aSjCCDdMcEYcOZMEFzfre8+jdoC6SWBAoGAXLFc\nz4IlvSBcHR+QrMM5cSSRbtymylvESGkeJUAm2FBT0u+gcAsA37tTBDerc9bUUcW2\nWZ33tWUNPMuy9k1JT7l/9BfvzTkz3pd213ppy2g0MSxGXB3/rvS7CTEzxOuBoKLM\njs4WCtxUYCzri/hZTbEymBLbzWp/+z6Fg+3GrDsCgYAVdqAyMZyutnpFxd7jOMI1\n+EblCbb+Z5m7pUg0c0ttC6gieVwkMx+Dj62BMbsp5KMhi+C5Hn4UErylrwy5BDb3\n572NUqkrpH4Db6tCFQxGmQtwdA1YDvIVIsBd0W9HBKbrAvA7MXC/nqL0BVYZ57+i\nnvd5RloS4y/LCgZDNOYCyg==\n-----END PRIVATE KEY-----\n",  # noqa: E501
)


@pytest.fixture
def token_handler() -> JWTTokenHandler:
    return JWTTokenHandler(public_key=PUBLIC_KEY, private_key=PRIVATE_KEY)


@pytest.fixture
def user_id() -> str:
    return str(uuid4())


@pytest.fixture
def other_user_id() -> str:
    return str(uuid4())


@pytest.fixture
def access_token(token_handler: JWTTokenHandler, user_id: str) -> str:
    payload = AccessTokenPayload(
        id=user_id,
        username="testuser",
        role="USER",
        is_blocked=False,
        type=TokenType.ACCESS,
    )
    return token_handler.encode_jwt(payload=payload, expire_minutes=30)


@pytest.fixture
def other_access_token(token_handler: JWTTokenHandler, other_user_id: str) -> str:
    payload = AccessTokenPayload(
        id=other_user_id,
        username="otheruser",
        role="USER",
        is_blocked=False,
        type=TokenType.ACCESS,
    )
    return token_handler.encode_jwt(payload=payload, expire_minutes=30)
