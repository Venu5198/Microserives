import uuid
from datetime import timedelta

import pytest
from ecommerce_common.security import (
    create_jwt_token,
    decode_jwt_token,
    hash_password,
    verify_password,
)
from fastapi import HTTPException
from models import (
    AddressCreate,
    UserRegisterRequest,
)
from pydantic import ValidationError

SECRET_KEY = "test-secret-key-at-least-32-chars-long-for-testing"


def test_argon2id_password_hashing():
    raw_password = "SuperSecurePassword123!"
    hashed = hash_password(raw_password)
    assert hashed != raw_password
    assert hashed.startswith("$argon2id$")
    assert verify_password(raw_password, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False


def test_jwt_token_creation_and_claims():
    user_id = str(uuid.uuid4())
    email = "engineer@ecommerce.local"
    role = "CUSTOMER"

    token = create_jwt_token(
        payload={"sub": user_id, "email": email, "role": role},
        secret_key=SECRET_KEY,
        expires_delta=timedelta(minutes=15),
    )

    claims = decode_jwt_token(token, secret_key=SECRET_KEY)
    assert claims["sub"] == user_id
    assert claims["email"] == email
    assert claims["role"] == role
    assert "exp" in claims


def test_jwt_token_tampering_rejection():
    token = create_jwt_token(
        payload={"sub": "user-1", "role": "CUSTOMER"},
        secret_key=SECRET_KEY,
        expires_delta=timedelta(minutes=15),
    )
    tampered = token[:-4] + "fake"
    with pytest.raises(HTTPException):
        decode_jwt_token(tampered, secret_key=SECRET_KEY)


def test_jwt_token_expiration_rejection():
    expired_token = create_jwt_token(
        payload={"sub": "user-expired", "role": "CUSTOMER"},
        secret_key=SECRET_KEY,
        expires_delta=timedelta(seconds=-10),  # expired in past
    )
    with pytest.raises(HTTPException):
        decode_jwt_token(expired_token, secret_key=SECRET_KEY)


def test_models_validation():
    req = UserRegisterRequest(
        email="test@example.com",
        password="ValidPassword8+",
        first_name="Jane",
        last_name="Doe",
    )
    assert req.email == "test@example.com"
    assert req.role == "CUSTOMER"

    addr = AddressCreate(
        street="123 Tech Blvd",
        city="San Jose",
        state="CA",
        postal_code="95110",
    )
    assert addr.title == "Home"
    assert addr.is_default is False

    with pytest.raises(ValidationError):
        # Password too short (< 8 chars)
        UserRegisterRequest(
            email="test@example.com",
            password="short",
            first_name="Jane",
            last_name="Doe",
        )
