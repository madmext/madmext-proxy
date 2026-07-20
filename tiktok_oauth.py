"""TikTok Marketing API OAuth integration (read-only application surface).

The module stores OAuth credentials encrypted at rest in PostgreSQL.  It exposes
only connection-management endpoints; campaign mutation APIs are intentionally
out of scope.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import psycopg2.extras
import requests
from cryptography.fernet import Fernet, InvalidToken
from flask import jsonify, redirect, request, session


DEFAULT_API_BASE_URL = "https://business-api.tiktok.com/open_api/v1.3"
DEFAULT_AUTH_URL = "https://ads.tiktok.com/marketing_api/auth"
STATE_TTL_SECONDS = 600
HTTP_TIMEOUT_SECONDS = 20


class TikTokConfigurationError(RuntimeError):
    pass


class TikTokAPIError(RuntimeError):
    pass


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _config() -> dict[str, str]:
    config = {
        "client_key": _env("TIKTOK_CLIENT_KEY"),
        "client_secret": _env("TIKTOK_CLIENT_SECRET"),
        "redirect_uri": _env("TIKTOK_REDIRECT_URI"),
        "api_base_url": _env("TIKTOK_API_BASE_URL") or DEFAULT_API_BASE_URL,
        "auth_url": _env("TIKTOK_AUTH_URL") or DEFAULT_AUTH_URL,
        "scopes": _env("TIKTOK_SCOPES"),
    }
    missing = [
        env_name
        for env_name, key in (
            ("TIKTOK_CLIENT_KEY", "client_key"),
            ("TIKTOK_CLIENT_SECRET", "client_secret"),
            ("TIKTOK_REDIRECT_URI", "redirect_uri"),
        )
        if not config[key]
    ]
    if missing:
        raise TikTokConfigurationError(
            "Eksik TikTok ortam değişkenleri: " + ", ".join(missing)
        )
    return config


def _endpoint(config: dict[str, str], path: str) -> str:
    return config["api_base_url"].rstrip("/") + "/" + path.lstrip("/")


def _fernet() -> Fernet:
    secret_key = _env("TOKEN_ENCRYPTION_KEY") or _env("SECRET_KEY")
    if not secret_key:
        raise TikTokConfigurationError(
            "TOKEN_ENCRYPTION_KEY veya SECRET_KEY tanımlı olmalı"
        )
    derived = hashlib.sha256(
        ("madmext:tiktok:v1:" + secret_key).encode("utf-8")
    ).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def _encrypt(value: str | None) -> str | None:
    if not value:
        return None
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def _decrypt(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise TikTokConfigurationError(
            "TikTok token şifreleme anahtarı değişmiş veya kayıt bozulmuş"
        ) from exc


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _expires_at(seconds: object) -> datetime | None:
    try:
        value = int(seconds)
    except (TypeError, ValueError):
        return None
    return _utcnow() + timedelta(seconds=value) if value > 0 else None


def _api_payload(response: requests.Response) -> dict:
    try:
        payload = response.json()
    except ValueError as exc:
        raise TikTokAPIError(
            f"TikTok API JSON döndürmedi (HTTP {response.status_code})"
        ) from exc
    if not response.ok or payload.get("code") not in (None, 0):
        message = payload.get("message") or payload.get("error_description") or "Bilinmeyen hata"
        request_id = payload.get("request_id")
        suffix = f" (request_id={request_id})" if request_id else ""
        raise TikTokAPIError(f"TikTok API hatası: {message}{suffix}")
    data = payload.get("data")
    return data if isinstance(data, dict) else payload


def _exchange_authorization_code(config: dict[str, str], auth_code: str) -> dict:
    response = requests.post(
        _endpoint(config, "/oauth2/access_token/"),
        json={
            "app_id": config["client_key"],
            "secret": config["client_secret"],
            "auth_code": auth_code,
        },
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    return _api_payload(response)


def _authorized_advertisers(config: dict[str, str], access_token: str) -> list[str]:
    response = requests.get(
        _endpoint(config, "/oauth2/advertiser/get/"),
        params={
            "app_id": config["client_key"],
            "secret": config["client_secret"],
        },
        headers={"Access-Token": access_token},
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    data = _api_payload(response)
    values = data.get("list") or data.get("advertiser_ids") or []
    advertiser_ids: list[str] = []
    for value in values:
        if isinstance(value, dict):
            value = value.get("advertiser_id") or value.get("id")
        if value is not None:
            advertiser_ids.append(str(value))
    return advertiser_ids


def _refresh_short_term_token(config: dict[str, str], refresh_token: str) -> dict:
    response = requests.post(
        _endpoint(config, "/tt_user/oauth2/refresh_token/"),
        json={
            "client_id": config["client_key"],
            "client_secret": config["client_secret"],
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    return _api_payload(response)


def _init_db(get_db) -> None:
    conn = get_db()
    if not conn:
        return
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS tiktok_ad_accounts (
                advertiser_id TEXT PRIMARY KEY,
                open_id TEXT,
                access_token_encrypted TEXT,
                refresh_token_encrypted TEXT,
                token_expires_at TIMESTAMPTZ,
                refresh_token_expires_at TIMESTAMPTZ,
                scopes TEXT,
                token_type TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                authorized_by TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                disconnected_at TIMESTAMPTZ
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS tiktok_integration_logs (
                id BIGSERIAL PRIMARY KEY,
                event_type TEXT NOT NULL,
                advertiser_id TEXT,
                status TEXT NOT NULL,
                message TEXT,
                actor_email TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if cur:
            cur.close()
        conn.close()


def _log(get_db, event_type: str, status: str, message: str = "",
         advertiser_id: str | None = None) -> None:
    conn = get_db()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO tiktok_integration_logs
                (event_type, advertiser_id, status, message, actor_email)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                event_type,
                advertiser_id,
                status,
                (message or "")[:1000],
                session.get("user_email"),
            ),
        )
        conn.commit()
        cur.close()
    except Exception as exc:
        conn.rollback()
        print("tiktok integration log:", exc)
    finally:
        conn.close()


def _upsert_account(get_db, advertiser_id: str, token_data: dict) -> None:
    conn = get_db()
    if not conn:
        raise RuntimeError("Veritabanı bağlantısı yok")
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO tiktok_ad_accounts (
                advertiser_id, open_id, access_token_encrypted,
                refresh_token_encrypted, token_expires_at,
                refresh_token_expires_at, scopes, token_type, status,
                authorized_by, updated_at, disconnected_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active', %s, NOW(), NULL)
            ON CONFLICT (advertiser_id) DO UPDATE SET
                open_id = EXCLUDED.open_id,
                access_token_encrypted = EXCLUDED.access_token_encrypted,
                refresh_token_encrypted = COALESCE(
                    EXCLUDED.refresh_token_encrypted,
                    tiktok_ad_accounts.refresh_token_encrypted
                ),
                token_expires_at = EXCLUDED.token_expires_at,
                refresh_token_expires_at = COALESCE(
                    EXCLUDED.refresh_token_expires_at,
                    tiktok_ad_accounts.refresh_token_expires_at
                ),
                scopes = EXCLUDED.scopes,
                token_type = EXCLUDED.token_type,
                status = 'active',
                authorized_by = EXCLUDED.authorized_by,
                updated_at = NOW(),
                disconnected_at = NULL
            """,
            (
                advertiser_id,
                token_data.get("open_id"),
                _encrypt(token_data.get("access_token")),
                _encrypt(token_data.get("refresh_token")),
                _expires_at(token_data.get("expires_in")),
                _expires_at(token_data.get("refresh_token_expires_in")),
                token_data.get("scope") or token_data.get("scopes"),
                token_data.get("token_type") or "Bearer",
                session.get("user_email"),
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if cur:
            cur.close()
        conn.close()


def _build_authorization_url(config: dict[str, str], state: str) -> str:
    split = urlsplit(config["auth_url"])
    query = dict(parse_qsl(split.query, keep_blank_values=True))
    query.update(
        {
            "app_id": config["client_key"],
            "state": state,
            "redirect_uri": config["redirect_uri"],
        }
    )
    if config["scopes"]:
        query["scope"] = config["scopes"]
    return urlunsplit(
        (split.scheme, split.netloc, split.path, urlencode(query), split.fragment)
    )


def _load_accounts(get_db) -> list[dict]:
    conn = get_db()
    if not conn:
        raise RuntimeError("Veritabanı bağlantısı yok")
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT advertiser_id, open_id, token_expires_at,
                   refresh_token_expires_at, scopes, token_type, status,
                   authorized_by, created_at, updated_at, disconnected_at,
                   refresh_token_encrypted IS NOT NULL AS refresh_available
            FROM tiktok_ad_accounts
            ORDER BY updated_at DESC
            """
        )
        rows = [dict(row) for row in cur.fetchall()]
        cur.close()
        for row in rows:
            for key, value in list(row.items()):
                if hasattr(value, "isoformat"):
                    row[key] = value.isoformat()
        return rows
    finally:
        conn.close()


def install(app, *, get_db, require_admin) -> None:
    _init_db(get_db)

    @app.get("/api/integrations/tiktok/connect")
    def tiktok_connect():
        denied = require_admin()
        if denied:
            return denied
        try:
            config = _config()
            state = secrets.token_urlsafe(32)
            session["tiktok_oauth_state"] = state
            session["tiktok_oauth_state_created_at"] = int(_utcnow().timestamp())
            session.modified = True
            return redirect(_build_authorization_url(config, state), code=302)
        except TikTokConfigurationError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 503

    @app.get("/api/integrations/tiktok/callback")
    def tiktok_callback():
        denied = require_admin()
        if denied:
            return denied
        expected_state = session.pop("tiktok_oauth_state", "")
        created_at = session.pop("tiktok_oauth_state_created_at", 0)
        received_state = (request.args.get("state") or "").strip()
        now = int(_utcnow().timestamp())
        if (
            not expected_state
            or not received_state
            or not hmac.compare_digest(expected_state, received_state)
            or not created_at
            or now - int(created_at) > STATE_TTL_SECONDS
        ):
            _log(get_db, "oauth_callback", "failed", "Geçersiz veya süresi dolmuş state")
            return jsonify({"ok": False, "error": "Geçersiz veya süresi dolmuş OAuth state"}), 400

        provider_error = request.args.get("error") or request.args.get("error_description")
        if provider_error:
            _log(get_db, "oauth_callback", "failed", str(provider_error))
            return jsonify({"ok": False, "error": "TikTok yetkilendirmesi reddedildi"}), 400

        auth_code = (
            request.args.get("auth_code")
            or request.args.get("code")
            or ""
        ).strip()
        if not auth_code:
            return jsonify({"ok": False, "error": "auth_code bulunamadı"}), 400

        try:
            config = _config()
            token_data = _exchange_authorization_code(config, auth_code)
            access_token = token_data.get("access_token")
            if not access_token:
                raise TikTokAPIError("TikTok access_token döndürmedi")

            advertisers = token_data.get("advertiser_ids") or []
            advertisers = [str(item) for item in advertisers]
            if not advertisers:
                advertisers = _authorized_advertisers(config, access_token)
            if not advertisers:
                raise TikTokAPIError("Yetkilendirilmiş reklam hesabı bulunamadı")

            for advertiser_id in advertisers:
                _upsert_account(get_db, advertiser_id, token_data)
                _log(get_db, "oauth_callback", "success", "Hesap bağlandı", advertiser_id)

            return jsonify(
                {
                    "ok": True,
                    "connected": True,
                    "advertiser_ids": advertisers,
                    "message": "TikTok Ads hesabı başarıyla bağlandı",
                }
            )
        except (TikTokConfigurationError, TikTokAPIError) as exc:
            _log(get_db, "oauth_callback", "failed", str(exc))
            return jsonify({"ok": False, "error": str(exc)}), 502
        except RuntimeError as exc:
            _log(get_db, "oauth_callback", "failed", str(exc))
            return jsonify({"ok": False, "error": str(exc)}), 503
        except Exception:
            _log(get_db, "oauth_callback", "failed", "Beklenmeyen sunucu hatası")
            return jsonify({"ok": False, "error": "TikTok bağlantısı tamamlanamadı"}), 500

    @app.get("/api/integrations/tiktok/status")
    def tiktok_status():
        denied = require_admin()
        if denied:
            return denied
        try:
            configured = True
            configuration_error = None
            try:
                _config()
            except TikTokConfigurationError as exc:
                configured = False
                configuration_error = str(exc)
            accounts = _load_accounts(get_db)
            active = [row for row in accounts if row.get("status") == "active"]
            return jsonify(
                {
                    "ok": True,
                    "configured": configured,
                    "configuration_error": configuration_error,
                    "connected": bool(active),
                    "accounts": accounts,
                }
            )
        except RuntimeError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 503

    @app.post("/api/integrations/tiktok/refresh")
    def tiktok_refresh():
        denied = require_admin()
        if denied:
            return denied
        advertiser_id = str((request.get_json(silent=True) or {}).get("advertiser_id") or "").strip()
        if not advertiser_id:
            return jsonify({"ok": False, "error": "advertiser_id zorunlu"}), 400
        conn = get_db()
        if not conn:
            return jsonify({"ok": False, "error": "Veritabanı bağlantısı yok"}), 503
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                """
                SELECT refresh_token_encrypted
                FROM tiktok_ad_accounts
                WHERE advertiser_id=%s AND status='active'
                """,
                (advertiser_id,),
            )
            row = cur.fetchone()
            cur.close()
        finally:
            conn.close()
        if not row or not row.get("refresh_token_encrypted"):
            return jsonify(
                {
                    "ok": False,
                    "error": (
                        "Bu Marketing API bağlantısı long-term token kullanıyor; "
                        "refresh token yoksa yeniden yetkilendirme gerekir"
                    ),
                }
            ), 409
        try:
            token_data = _refresh_short_term_token(
                _config(), _decrypt(row["refresh_token_encrypted"])
            )
            _upsert_account(get_db, advertiser_id, token_data)
            _log(get_db, "token_refresh", "success", "Token yenilendi", advertiser_id)
            return jsonify({"ok": True, "advertiser_id": advertiser_id})
        except (TikTokConfigurationError, TikTokAPIError) as exc:
            _log(get_db, "token_refresh", "failed", str(exc), advertiser_id)
            return jsonify({"ok": False, "error": str(exc)}), 502

    @app.post("/api/integrations/tiktok/disconnect")
    def tiktok_disconnect():
        denied = require_admin()
        if denied:
            return denied
        advertiser_id = str((request.get_json(silent=True) or {}).get("advertiser_id") or "").strip()
        if not advertiser_id:
            return jsonify({"ok": False, "error": "advertiser_id zorunlu"}), 400
        conn = get_db()
        if not conn:
            return jsonify({"ok": False, "error": "Veritabanı bağlantısı yok"}), 503
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE tiktok_ad_accounts
                SET status='disconnected',
                    access_token_encrypted=NULL,
                    refresh_token_encrypted=NULL,
                    token_expires_at=NULL,
                    refresh_token_expires_at=NULL,
                    disconnected_at=NOW(),
                    updated_at=NOW()
                WHERE advertiser_id=%s
                """,
                (advertiser_id,),
            )
            changed = cur.rowcount
            conn.commit()
            cur.close()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        if not changed:
            return jsonify({"ok": False, "error": "TikTok hesabı bulunamadı"}), 404
        _log(get_db, "disconnect", "success", "Hesap pasifleştirildi", advertiser_id)
        return jsonify({"ok": True, "advertiser_id": advertiser_id})
