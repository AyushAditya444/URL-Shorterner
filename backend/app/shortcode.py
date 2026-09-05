import secrets
import string

CODE_ALPHABET = string.ascii_letters + string.digits


def generate_code(length: int = 7) -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))
