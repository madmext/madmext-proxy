"""Read-only TikTok Ads campaign reporting.

Only TikTok GET endpoints are used. This module deliberately exposes no campaign
status, budget, pause, delete, or other mutation operation.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import psycopg2.extras
import requests
from flask import jsonify, request

import tiktok_oauth


HTTP_TIMEOUT_SECONDS = 30
MAX_DATE_RANGE_DAYS = 365
PAGE_SIZE = 1000
REPORT_PATH = "/report/integrated/get/"
CAMPAIGN_PATH = "/campaign/get/"

WEB_COMMERCE_METRICS = (
    "spend",
    "impressions",
    "clicks",
    "complete_payment",
    "total_complete_payment_rate",
    "complete_payment_roas",
)
APP_COMMERCE_METRICS = (
    "spend",
    "impressions",
    "clicks",
    "purchase",
    "total_purchase_value",
    "total_active_pay_roas",
)


class TikTokReportingError(RuntimeError):
    pass


class TikTokNotConnectedError(TikTokReportingError):
    pass


def _api_base_url() -> str:
    return (
        os.environ.get("TIKTOK_API_BASE_URL")
        or tiktok_oauth.DEFAULT_API_BASE_URL
    ).strip().rstrip("/")


def _endpoint(path: str) -> str:
    return _api_base_url() + "/" + path.lstrip("/")


def _parse_date(value: str | None, field_name: str, default: date) -> date:
    if not value:
        return default
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{field_name} YYYY-MM-DD formatında olmalı") from exc


def _date_range(args) -> tuple[date, date]:
    today = date.today()
    end_date = _parse_date(args.get("end_date"), "end_date", today)
    start_date = _parse_date(
        args.get("start_date"),
        "start_date",
        end_date - timedelta(days=29),
    )
    if start_date > end_date:
        raise ValueError("start_date, end_date değerinden sonra olamaz")
    if (end_date - start_date).days + 1 > MAX_DATE_RANGE_DAYS:
        raise ValueError(f"Tarih aralığı en fazla {MAX_DATE_RANGE_DAYS} gün olabilir")
    return start_date, end_date


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _number(value: Any, *, integer: bool = False):
    number = _decimal(value)
    return int(number) if integer else float(number.quantize(Decimal("0.01")))


def _response_data(response: requests.Response) -> dict:
    try:
        payload = response.json()
    except ValueError as exc:
        raise TikTokReportingError(
            f"TikTok Reporting API JSON döndürmedi (HTTP {response.status_code})"
        ) from exc
    if not response.ok or payload.get("code") not in (None, 0):
        message = payload.get("message") or "Bilinmeyen TikTok Reporting API hatası"
        request_id = payload.get("request_id")
        suffix = f" (request_id={request_id})" if request_id else ""
        raise TikTokReportingError(f"{message}{suffix}")
    data = payload.get("data")
    return data if isinstance(data, dict) else {}


def _active_accounts(get_db) -> list[dict]:
    conn = get_db()
    if not conn:
        raise TikTokReportingError("Veritabanı bağlantısı yok")
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT advertiser_id, access_token_encrypted
            FROM tiktok_ad_accounts
            WHERE status='active' AND access_token_encrypted IS NOT NULL
            ORDER BY updated_at DESC
            """
        )
        rows = [dict(row) for row in cur.fetchall()]
        cur.close()
    finally:
        conn.close()
    if not rows:
        raise TikTokNotConnectedError("TikTok Ads hesabı bağlı değil")
    for row in rows:
        row["access_token"] = tiktok_oauth._decrypt(
            row.pop("access_token_encrypted")
        )
    return rows


def _get_campaign_metadata(advertiser_id: str, access_token: str) -> dict[str, dict]:
    campaigns: dict[str, dict] = {}
    page = 1
    while True:
        response = requests.get(
            _endpoint(CAMPAIGN_PATH),
            params={
                "advertiser_id": advertiser_id,
                "page": page,
                "page_size": 1000,
            },
            headers={"Access-Token": access_token},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        data = _response_data(response)
        for item in data.get("list") or []:
            campaign_id = str(item.get("campaign_id") or "")
            if campaign_id:
                campaigns[campaign_id] = {
                    "campaign_name": item.get("campaign_name") or campaign_id,
                    "status": item.get("secondary_status")
                    or item.get("operation_status")
                    or item.get("status")
                    or "UNKNOWN",
                }
        page_info = data.get("page_info") or {}
        total_page = int(page_info.get("total_page") or page)
        if page >= total_page:
            break
        page += 1
    return campaigns


def _request_report_page(
    advertiser_id: str,
    access_token: str,
    start_date: date,
    end_date: date,
    metrics: tuple[str, ...],
    page: int,
) -> dict:
    response = requests.get(
        _endpoint(REPORT_PATH),
        params={
            "advertiser_id": advertiser_id,
            "service_type": "AUCTION",
            "report_type": "BASIC",
            "data_level": "AUCTION_CAMPAIGN",
            "dimensions": json.dumps(["campaign_id"]),
            "metrics": json.dumps(list(metrics)),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "page": page,
            "page_size": PAGE_SIZE,
            "query_mode": "REGULAR",
        },
        headers={"Access-Token": access_token},
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    return _response_data(response)


def _get_report_rows(
    advertiser_id: str,
    access_token: str,
    start_date: date,
    end_date: date,
) -> tuple[list[dict], tuple[str, ...]]:
    # Web conversion metrics are preferred for Madmext e-commerce. Some TikTok
    # accounts expose only app purchase metrics, so retry once with the official
    # app-purchase metric family when the web metric combination is unavailable.
    last_error = None
    for metric_set in (WEB_COMMERCE_METRICS, APP_COMMERCE_METRICS):
        try:
            rows: list[dict] = []
            page = 1
            while True:
                data = _request_report_page(
                    advertiser_id,
                    access_token,
                    start_date,
                    end_date,
                    metric_set,
                    page,
                )
                rows.extend(data.get("list") or [])
                page_info = data.get("page_info") or {}
                total_page = int(page_info.get("total_page") or page)
                if page >= total_page:
                    return rows, metric_set
                page += 1
        except TikTokReportingError as exc:
            last_error = exc
    raise last_error or TikTokReportingError("TikTok raporu alınamadı")


def _normalize_row(
    advertiser_id: str,
    item: dict,
    metadata: dict[str, dict],
    metric_set: tuple[str, ...],
) -> dict:
    dimensions = item.get("dimensions") or {}
    metrics = item.get("metrics") or {}
    campaign_id = str(dimensions.get("campaign_id") or item.get("campaign_id") or "")
    meta = metadata.get(campaign_id) or {}
    web_metrics = metric_set == WEB_COMMERCE_METRICS

    spend = _decimal(metrics.get("spend"))
    purchases = _decimal(
        metrics.get("complete_payment")
        if web_metrics
        else metrics.get("purchase")
    )
    revenue = _decimal(
        metrics.get("total_complete_payment_rate")
        if web_metrics
        else metrics.get("total_purchase_value")
    )
    api_roas = _decimal(
        metrics.get("complete_payment_roas")
        if web_metrics
        else metrics.get("total_active_pay_roas")
    )
    roas = api_roas if api_roas else (revenue / spend if spend else Decimal("0"))
    impressions = _decimal(metrics.get("impressions"))
    clicks = _decimal(metrics.get("clicks"))

    return {
        "advertiser_id": advertiser_id,
        "campaign_id": campaign_id,
        "campaign_name": meta.get("campaign_name") or campaign_id or "İsimsiz kampanya",
        "status": meta.get("status") or "UNKNOWN",
        "spend": _number(spend),
        "impressions": _number(impressions, integer=True),
        "clicks": _number(clicks, integer=True),
        "purchases": _number(purchases, integer=True),
        "revenue": _number(revenue),
        "roas": _number(roas),
        "ctr": _number(clicks / impressions * 100 if impressions else 0),
        "cpc": _number(spend / clicks if clicks else 0),
    }


def _summary(campaigns: list[dict]) -> dict:
    spend = sum(_decimal(item["spend"]) for item in campaigns)
    revenue = sum(_decimal(item["revenue"]) for item in campaigns)
    impressions = sum(int(item["impressions"]) for item in campaigns)
    clicks = sum(int(item["clicks"]) for item in campaigns)
    purchases = sum(int(item["purchases"]) for item in campaigns)
    return {
        "spend": _number(spend),
        "impressions": impressions,
        "clicks": clicks,
        "purchases": purchases,
        "revenue": _number(revenue),
        "roas": _number(revenue / spend if spend else 0),
        "ctr": _number(Decimal(clicks) / Decimal(impressions) * 100 if impressions else 0),
        "cpc": _number(spend / Decimal(clicks) if clicks else 0),
    }


def get_campaign_report(get_db, start_date: date, end_date: date) -> dict:
    campaigns = []
    advertiser_ids = []
    for account in _active_accounts(get_db):
        advertiser_id = str(account["advertiser_id"])
        access_token = account["access_token"]
        metadata = _get_campaign_metadata(advertiser_id, access_token)
        rows, metric_set = _get_report_rows(
            advertiser_id,
            access_token,
            start_date,
            end_date,
        )
        advertiser_ids.append(advertiser_id)
        campaigns.extend(
            _normalize_row(advertiser_id, row, metadata, metric_set)
            for row in rows
        )
    campaigns.sort(key=lambda item: item["spend"], reverse=True)
    return {
        "ok": True,
        "connected": True,
        "read_only": True,
        "date_range": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        "advertiser_ids": advertiser_ids,
        "summary": _summary(campaigns),
        "campaigns": campaigns,
    }


def install(app, *, get_db, require_admin) -> None:
    @app.get("/api/tiktok/campaigns")
    def tiktok_campaigns():
        denied = require_admin()
        if denied:
            return denied
        try:
            start_date, end_date = _date_range(request.args)
            return jsonify(get_campaign_report(get_db, start_date, end_date))
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except TikTokNotConnectedError as exc:
            return jsonify(
                {
                    "ok": False,
                    "connected": False,
                    "read_only": True,
                    "error": str(exc),
                    "connect_url": "/api/integrations/tiktok/connect",
                }
            ), 409
        except (
            TikTokReportingError,
            tiktok_oauth.TikTokConfigurationError,
        ) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 502
