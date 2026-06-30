"""Unit tests for password hashing and JWT helpers."""

from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("s3cret-pw")
    assert hashed != "s3cret-pw"
    assert verify_password("s3cret-pw", hashed)
    assert not verify_password("wrong-pw", hashed)


def test_token_roundtrip() -> None:
    token = create_access_token("alice")
    assert decode_token(token) == "alice"


def test_decode_garbage_returns_none() -> None:
    assert decode_token("not.a.jwt") is None


def test_expired_token_returns_none() -> None:
    token = create_access_token("bob", expires_minutes=-1)
    assert decode_token(token) is None
