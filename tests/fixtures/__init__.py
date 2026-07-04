from pathlib import Path

_FIXTURES_DIR = Path(__file__).resolve().parent


def load_dev_rsa_public_key() -> str:
    return _FIXTURES_DIR.joinpath("dev_rsa_public.pem").read_text()


def load_dev_rsa_private_key() -> str:
    return _FIXTURES_DIR.joinpath("dev_rsa_private.pem").read_text()
