from flask import Flask, session
import pytest

import tiktok_oauth


@pytest.mark.parametrize(
    ("expected", "received", "created_at", "now", "is_valid"),
    [
        ("state-123", "state-123", 1_000, 1_300, True),
        ("state-123", "state-123", 1_000, 1_601, False),
        ("state-123", "other-state", 1_000, 1_300, False),
        ("", "state-123", 1_000, 1_300, False),
        ("state-123", "", 1_000, 1_300, False),
    ],
)
def test_validate_oauth_state(expected, received, created_at, now, is_valid):
    assert (
        tiktok_oauth._validate_oauth_state(
            expected,
            received,
            created_at,
            now_timestamp=now,
        )
        is is_valid
    )


def test_encrypt_decrypt_round_trip(monkeypatch):
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "dedicated-test-encryption-key")

    encrypted = tiktok_oauth._encrypt("tiktok-secret-token")

    assert encrypted != "tiktok-secret-token"
    assert tiktok_oauth._decrypt(encrypted) == "tiktok-secret-token"


def test_encrypt_requires_dedicated_key(monkeypatch):
    monkeypatch.delenv("TOKEN_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("SECRET_KEY", "must-not-be-used-for-token-encryption")

    with pytest.raises(
        tiktok_oauth.TikTokConfigurationError,
        match="TOKEN_ENCRYPTION_KEY",
    ):
        tiktok_oauth._encrypt("token")


class FakeCursor:
    def __init__(self, stored_account):
        self.stored_account = stored_account
        self.previous_owner = None
        self.last_upsert_sql = ""

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        if normalized.startswith("SELECT authorized_by"):
            self.previous_owner = self.stored_account.get("authorized_by")
            return

        if "INSERT INTO tiktok_ad_accounts" in normalized:
            self.last_upsert_sql = normalized
            (
                advertiser_id,
                open_id,
                access_token_encrypted,
                refresh_token_encrypted,
                token_expires_at,
                refresh_token_expires_at,
                scopes,
                token_type,
                authorized_by,
            ) = params
            self.stored_account.update(
                {
                    "advertiser_id": advertiser_id,
                    "open_id": open_id,
                    "access_token_encrypted": access_token_encrypted,
                    "token_expires_at": token_expires_at,
                    "scopes": scopes,
                    "token_type": token_type,
                    "authorized_by": authorized_by,
                }
            )
            # Mirrors the SQL COALESCE behavior being asserted below.
            if refresh_token_encrypted is not None:
                self.stored_account["refresh_token_encrypted"] = refresh_token_encrypted
            if refresh_token_expires_at is not None:
                self.stored_account["refresh_token_expires_at"] = refresh_token_expires_at

    def fetchone(self):
        return (self.previous_owner,) if self.previous_owner else None

    def close(self):
        return None


class FakeConnection:
    def __init__(self, stored_account):
        self.cursor_instance = FakeCursor(stored_account)

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


def test_upsert_preserves_existing_refresh_token_when_response_omits_it(monkeypatch):
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "dedicated-test-encryption-key")
    stored_account = {
        "authorized_by": "admin@example.com",
        "refresh_token_encrypted": tiktok_oauth._encrypt("existing-refresh-token"),
    }
    connection = FakeConnection(stored_account)
    flask_app = Flask(__name__)
    flask_app.secret_key = "test-session-key"

    with flask_app.test_request_context("/"):
        session["user_email"] = "admin@example.com"
        previous_owner = tiktok_oauth._upsert_account(
            lambda: connection,
            "advertiser-123",
            {
                "access_token": "new-access-token",
                "scope": "reporting.read",
                # TikTok long-term token responses may omit refresh_token.
            },
        )

    assert previous_owner == "admin@example.com"
    assert (
        tiktok_oauth._decrypt(stored_account["refresh_token_encrypted"])
        == "existing-refresh-token"
    )
    assert (
        "refresh_token_encrypted = COALESCE( EXCLUDED.refresh_token_encrypted,"
        in connection.cursor_instance.last_upsert_sql
    )
