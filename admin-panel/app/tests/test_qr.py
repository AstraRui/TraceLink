"""Tests for local QR-code generation."""

import base64

from app.services.qr import generate_qr_data_uri

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_qr_data_uri_is_a_png() -> None:
    uri = generate_qr_data_uri("http://localhost:8080/abc1234")
    assert uri.startswith("data:image/png;base64,")
    raw = base64.b64decode(uri.split(",", 1)[1])
    assert raw[:8] == _PNG_MAGIC


def test_qr_differs_for_different_input() -> None:
    a = generate_qr_data_uri("http://localhost:8080/aaaaaaa")
    b = generate_qr_data_uri("http://localhost:8080/bbbbbbb")
    assert a != b
