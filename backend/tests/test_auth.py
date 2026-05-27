"""Unit tests for verify_token dependency in auth.py."""
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from unittest.mock import patch, MagicMock
import pytest
import firebase_admin

import auth as auth_module
import config


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


# ── Demo bypass ───────────────────────────────────────────────────────────────

def test_verify_token_demo_bypass_returns_demo_uid():
    result = auth_module.verify_token(_creds(config.DEMO_TOKEN))
    assert result["uid"] == config.DEMO_UID
    assert result["email"] == "demo@example.com"


# ── Invalid / missing token → 401 ────────────────────────────────────────────

@pytest.mark.parametrize("bad_token", ["undefined", "null", ""])
def test_verify_token_bad_token_raises_401(bad_token):
    with pytest.raises(HTTPException) as exc_info:
        auth_module.verify_token(_creds(bad_token))
    assert exc_info.value.status_code == 401


# ── Valid Firebase token ──────────────────────────────────────────────────────

def test_verify_token_valid_firebase_token_returns_decoded():
    fake_decoded = {"uid": "real_user_123", "email": "user@test.com"}
    # Patch _apps on the real firebase_admin module and verify_id_token on the
    # firebase_admin.auth submodule (which auth.py imported as `auth`)
    with patch.object(firebase_admin, "_apps", {"default": MagicMock()}), \
         patch.object(auth_module.auth, "verify_id_token", return_value=fake_decoded):
        result = auth_module.verify_token(_creds("valid-firebase-token"))
    assert result["uid"] == "real_user_123"


# ── Firebase rejects token → 401 ─────────────────────────────────────────────

def test_verify_token_invalid_firebase_token_raises_401():
    # Exception message must NOT contain "initialize_app()" or "firebase_admin"
    # to reach the 401 raise path (other errors fall back to mock UID)
    with patch.object(firebase_admin, "_apps", {"default": MagicMock()}), \
         patch.object(auth_module.auth, "verify_id_token", side_effect=Exception("token expired")):
        with pytest.raises(HTTPException) as exc_info:
            auth_module.verify_token(_creds("bad-token"))
    assert exc_info.value.status_code == 401
