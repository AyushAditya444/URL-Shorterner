from app.shortcode import generate_code, CODE_ALPHABET


def test_generate_code_default_length():
    code = generate_code()
    assert len(code) == 7


def test_generate_code_custom_length():
    code = generate_code(length=10)
    assert len(code) == 10


def test_generate_code_uses_only_base62_alphabet():
    code = generate_code()
    assert all(ch in CODE_ALPHABET for ch in code)


def test_generate_code_is_randomized():
    codes = {generate_code() for _ in range(50)}
    assert len(codes) == 50
