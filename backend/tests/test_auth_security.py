"""Unit tests for password hashing and JWT issuance (app/auth/security.py)."""

import pytest

from app.auth.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password


def test_password_hash_roundtrip():
    hashed = hash_password("DemoPass123!")
    assert hashed != "DemoPass123!"
    assert verify_password("DemoPass123!", hashed)


def test_password_hash_rejects_wrong_password():
    hashed = hash_password("DemoPass123!")
    assert not verify_password("WrongPassword", hashed)


def test_access_token_roundtrip():
    token = create_access_token(subject="42", roles=["admin"])
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["roles"] == ["admin"]
    assert payload["type"] == "access"


def test_refresh_token_has_refresh_type():
    token = create_refresh_token(subject="42")
    payload = decode_token(token)
    assert payload["type"] == "refresh"


def test_decode_rejects_garbage_token():
    with pytest.raises(ValueError):
        decode_token("not.a.real.token")


def test_decode_rejects_tampered_token():
    token = create_access_token(subject="1", roles=["viewer"])
    tampered = token[:-4] + "abcd"
    with pytest.raises(ValueError):
        decode_token(tampered)
