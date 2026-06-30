"""Unit tests for short-code generation and collision handling."""

import pytest

from app.services.shortener import (
    ALPHABET,
    MAX_LENGTH,
    MIN_LENGTH,
    ShortCodeCollisionError,
    find_unique_code,
    generate_code,
)


def test_generate_code_default_length() -> None:
    code = generate_code()
    assert len(code) == 7
    assert all(ch in ALPHABET for ch in code)


@pytest.mark.parametrize("length", [MIN_LENGTH, 7, MAX_LENGTH])
def test_generate_code_respects_length(length: int) -> None:
    assert len(generate_code(length)) == length


@pytest.mark.parametrize("length", [5, 9, 0, -1])
def test_generate_code_rejects_out_of_range(length: int) -> None:
    with pytest.raises(ValueError):
        generate_code(length)


def test_generate_many_codes_are_unique() -> None:
    """Several thousand draws from 62^7 should not collide in practice."""
    n = 5000
    codes = {generate_code(7) for _ in range(n)}
    assert len(codes) == n


def test_generate_code_choice_is_injectable() -> None:
    code = generate_code(6, choice=lambda alphabet: "A")
    assert code == "AAAAAA"


async def test_find_unique_code_retries_past_collisions() -> None:
    taken = {"AAAAAA", "BBBBBB"}
    candidates = iter(["AAAAAA", "BBBBBB", "CCCCCC"])

    async def exists(code: str) -> bool:
        return code in taken

    code = await find_unique_code(exists, length=6, make_code=lambda _length: next(candidates))
    assert code == "CCCCCC"


async def test_find_unique_code_gives_up_after_max_attempts() -> None:
    async def always_taken(code: str) -> bool:
        return True

    with pytest.raises(ShortCodeCollisionError):
        await find_unique_code(always_taken, length=6, max_attempts=3)
