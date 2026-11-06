import pytest
from datetime import timedelta
from ecommerce_common.security import (
    hash_password,
    verify_password,
    create_jwt_token,
    decode_jwt_token,
)
from fastapi import HTTPException


def test_argon2id_hashing():
    password = "SuperSecurePassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_token_lifecycle():
    secret = "testsecretkeymustbeatleast32byteslongforsecurity"
    payload = {"sub": "user-123", "email": "test@example.com", "role": "CUSTOMER"}

    token = create_jwt_token(payload, secret_key=secret, expires_delta=timedelta(minutes=15))
    decoded = decode_jwt_token(token, secret_key=secret)

    assert decoded["sub"] == "user-123"
    assert decoded["email"] == "test@example.com"
    assert decoded["role"] == "CUSTOMER"


def test_jwt_invalid_token():
    secret = "testsecretkeymustbeatleast32byteslongforsecurity"
    with pytest.raises(HTTPException) as exc_info:
        decode_jwt_token("invalid.token.string", secret_key=secret)
    assert exc_info.value.status_code == 401
