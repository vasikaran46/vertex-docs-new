"""Focused Supabase access-token and legacy-account linking tests."""

from __future__ import annotations

import base64
import os
import time
import uuid
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt
from tests.support import ApiTestCase
from app import security
from app.database import SessionLocal, engine
from app.models import ActivityLog, User


PROJECT_URL = "https://vertex-auth.example.test"
ISSUER = f"{PROJECT_URL}/auth/v1"
KID = "test-signing-key"


def _base64url_integer(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


class SupabaseAuthTests(ApiTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_numbers = cls.private_key.public_key().public_numbers()
        cls.jwks = {"keys": [{
            "kty": "RSA", "kid": KID, "use": "sig", "alg": "RS256",
            "n": _base64url_integer(public_numbers.n),
            "e": _base64url_integer(public_numbers.e),
        }]}
        ActivityLog.__table__.create(bind=engine, checkfirst=True)

    def setUp(self):
        super().setUp()
        self.env_patch = patch.dict(os.environ, {
            "SUPABASE_URL": PROJECT_URL,
            "SUPABASE_PUBLISHABLE_KEY": "test-publishable-key",
        })
        self.env_patch.start()
        self.jwks_patch = patch.object(security, "_get_supabase_jwks", return_value=self.jwks)
        self.jwks_patch.start()

    def tearDown(self):
        self.jwks_patch.stop()
        self.env_patch.stop()

    def supabase_token(self, email: str, subject: str | None = None, key=None) -> tuple[str, str]:
        user_id = subject or str(uuid.uuid4())
        private_key = key or self.private_key
        private_pem = private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        token = jwt.encode({
            "iss": ISSUER,
            "aud": "authenticated",
            "sub": user_id,
            "email": email,
            "exp": int(time.time()) + 600,
        }, private_pem, algorithm="RS256", headers={"kid": KID})
        return token, user_id

    def test_verified_supabase_subject_maps_to_existing_integer_user(self):
        email = f"{uuid.uuid4().hex}@example.com"
        token, subject = self.supabase_token(email)
        response = self.client.post(
            "/api/auth/profile",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Supabase User", "user_id": 99999, "email": "forged@example.com"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        profile = response.json()
        self.assertIsInstance(profile["id"], int)
        self.assertEqual(profile["email"], email)
        with SessionLocal() as db:
            user = db.get(User, profile["id"])
            self.assertEqual(user.supabase_auth_id, subject)
            self.assertFalse(user.is_admin)
        me = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me.status_code, 200, me.text)
        self.assertEqual(me.json()["id"], profile["id"])

    def test_invalid_supabase_signature_is_rejected(self):
        email = f"{uuid.uuid4().hex}@example.com"
        another_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token, _ = self.supabase_token(email, key=another_key)
        response = self.client.post(
            "/api/auth/profile",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Invalid Signature"},
        )
        self.assertEqual(response.status_code, 401)

    def test_supabase_admin_access_uses_persisted_is_admin(self):
        email = f"{uuid.uuid4().hex}@example.com"
        token, _ = self.supabase_token(email)
        headers = {"Authorization": f"Bearer {token}"}
        profile = self.client.post("/api/auth/profile", headers=headers, json={"name": "Regular"})
        self.assertEqual(profile.status_code, 200, profile.text)
        denied = self.client.get("/api/admin/stats", headers=headers)
        self.assertEqual(denied.status_code, 403)
        with SessionLocal() as db:
            user = db.get(User, profile.json()["id"])
            user.is_admin = True
            db.commit()
        allowed = self.client.get("/api/admin/stats", headers=headers)
        self.assertEqual(allowed.status_code, 200, allowed.text)

    def test_account_link_requires_both_verified_supabase_and_legacy_sessions(self):
        email, legacy_token = self.create_account()
        token, subject = self.supabase_token(email)
        response = self.client.post(
            "/api/auth/link-supabase",
            headers={"Authorization": f"Bearer {token}", "X-Legacy-Token": legacy_token},
        )
        self.assertEqual(response.status_code, 200, response.text)
        with SessionLocal() as db:
            user = db.get(User, response.json()["id"])
            self.assertEqual(user.supabase_auth_id, subject)
        me = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me.status_code, 200)

    def test_email_collision_alone_does_not_link_an_existing_user(self):
        email, _ = self.create_account()
        token, subject = self.supabase_token(email)
        response = self.client.post(
            "/api/auth/profile",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Not Linked"},
        )
        self.assertEqual(response.status_code, 409)
        with SessionLocal() as db:
            self.assertIsNone(db.query(User).filter_by(supabase_auth_id=subject).first())


if __name__ == "__main__":
    import unittest

    unittest.main()
