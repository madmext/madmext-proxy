"""Microsoft Clarity Data Export integration for Madmext Ads.

The Clarity export API is limited to 10 calls per project/day, a 1-3 day
rolling window, 3 dimensions per request and 1,000 response rows.  This
module deliberately uses one summary request plus one request for every
published dimension, preserving the complete JSON response for future
normalisation instead of discarding fields that Microsoft may add later.
"""

from __future__ import annotations

import csv
import hashlib
import io as _io
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Callable

import psycopg2
import requests
from flask import Response, jsonify, request, session


DEFAULT_ENDPOINT = "https://www.clarity.ms/export-data/api/v1/project-live-insights"
PUBLISHED_DIMENSIONS = (
    "Browser",
    "Device",
    "Country/Region",
    "OS",
    "Source",
    "Medium",
    "Campaign",
    "Channel",
    "URL",
)
DAILY_REQUEST_LIMIT = 10


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _enabled() -> bool:
    return os.environ.get("CLARITY_SYNC_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }


def _token() -> str:
    return os.environ.get("CLARITY_API_TOKEN", "").strip()


def _endpoint() -> str:
    return os.environ.get("CLARITY_API_BASE_URL", DEFAULT_ENDPOINT).strip() or DEFAULT_ENDPOINT


def _close(conn, cur=None) -> None:
    try:
        if cur is not None:
            cur.close()
    finally:
        conn.close()


def _init_db(get_db: Callable[[], Any]) -> None:
    conn = get_db()
    if not conn:
        return
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS clarity_sync_runs (
                id BIGSERIAL PRIMARY KEY,
                run_key TEXT NOT NULL,
                request_date DATE NOT NULL,
                num_days SMALLINT NOT NULL,
                dimension1 TEXT,
                dimension2 TEXT,
                dimension3 TEXT,
                status TEXT NOT NULL,
                http_status INTEGER,
                row_count INTEGER DEFAULT 0,
                response_hash TEXT,
                error_message TEXT,
                started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                completed_at TIMESTAMPTZ
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS clarity_sync_runs_request_date_idx
            ON clarity_sync_runs(request_date, status)
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS clarity_raw_exports (
                id BIGSERIAL PRIMARY KEY,
                sync_run_id BIGINT REFERENCES clarity_sync_runs(id) ON DELETE CASCADE,
                request_date DATE NOT NULL,
                num_days SMALLINT NOT NULL,
                dimension1 TEXT,
                dimension2 TEXT,
                dimension3 TEXT,
                metric_name TEXT NOT NULL,
                information JSONB NOT NULL,
                payload_hash TEXT NOT NULL,
                imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(request_date, num_days, dimension1, dimension2, dimension3, metric_name, payload_hash)
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS clarity_raw_exports_metric_idx
            ON clarity_raw_exports(metric_name, request_date DESC)
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS clarity_export_rows (
                id BIGSERIAL PRIMARY KEY,
                sync_run_id BIGINT REFERENCES clarity_sync_runs(id) ON DELETE CASCADE,
                request_date DATE NOT NULL,
                num_days SMALLINT NOT NULL,
                metric_name TEXT NOT NULL,
                dimension1 TEXT,
                dimension2 TEXT,
                dimension3 TEXT,
                dimension_values JSONB NOT NULL DEFAULT '{}'::jsonb,
                metrics JSONB NOT NULL,
                row_hash TEXT NOT NULL,
                imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(request_date, num_days, metric_name, dimension1, dimension2, dimension3, row_hash)
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS clarity_export_rows_lookup_idx
            ON clarity_export_rows(request_date DESC, metric_name, dimension1)
            """
        )
        cur.execute(
            "ALTER TABLE clarity_export_rows ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'api'"
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS clarity_uploads (
                id BIGSERIAL PRIMARY KEY,
                upload_type TEXT NOT NULL,
                filename TEXT NOT NULL,
                mime_type TEXT,
                date_from DATE,
                date_to DATE,
                file_data BYTEA,
                file_size INTEGER DEFAULT 0,
                row_count INTEGER DEFAULT 0,
                out_of_range_rows INTEGER DEFAULT 0,
                notes TEXT,
                uploaded_by TEXT,
                uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS clarity_uploads_uploaded_at_idx
            ON clarity_uploads(uploaded_at DESC)
            """
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _close(conn, cur)


def _daily_usage(get_db: Callable[[], Any]) -> int:
    conn = get_db()
    if not conn:
        return 0
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*)
            FROM clarity_sync_runs
            WHERE request_date = (NOW() AT TIME ZONE 'UTC')::date
              AND status IN ('running', 'success', 'http_error')
            """
        )
        return int(cur.fetchone()[0])
    finally:
        _close(conn, cur)


def _begin_run(get_db, run_key: str, num_days: int, dimensions: tuple[str, ...]) -> int:
    padded = list(dimensions) + [None, None, None]
    conn = get_db()
    if not conn:
        raise RuntimeError("DATABASE_URL bağlantısı kurulamadı")
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO clarity_sync_runs
                (run_key, request_date, num_days, dimension1, dimension2, dimension3, status)
            VALUES (%s, (NOW() AT TIME ZONE 'UTC')::date, %s, %s, %s, %s, 'running')
            RETURNING id
            """,
            (run_key, num_days, padded[0], padded[1], padded[2]),
        )
        run_id = int(cur.fetchone()[0])
        conn.commit()
        return run_id
    finally:
        _close(conn, cur)


def _finish_run(get_db, run_id: int, status: str, http_status: int | None,
                row_count: int, response_hash: str | None, error: str | None) -> None:
    conn = get_db()
    if not conn:
        return
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE clarity_sync_runs
            SET status=%s, http_status=%s, row_count=%s, response_hash=%s,
                error_message=%s, completed_at=NOW()
            WHERE id=%s
            """,
            (status, http_status, row_count, response_hash, error, run_id),
        )
        conn.commit()
    finally:
        _close(conn, cur)


def _split_row(row: dict[str, Any], dimensions: tuple[str, ...]) -> tuple[dict, dict]:
    dimension_values = {name: row.get(name) for name in dimensions if name in row}
    metrics = {key: value for key, value in row.items() if key not in dimension_values}
    return dimension_values, metrics


def _persist_payload(get_db, run_id: int, num_days: int,
                     dimensions: tuple[str, ...], payload: list[dict[str, Any]]) -> int:
    padded = list(dimensions) + [None, None, None]
    conn = get_db()
    if not conn:
        raise RuntimeError("DATABASE_URL bağlantısı kurulamadı")
    cur = None
    inserted_rows = 0
    try:
        cur = conn.cursor()
        for metric in payload:
            metric_name = str(metric.get("metricName") or "Unknown")
            information = metric.get("information") or []
            raw_json = json.dumps(information, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            raw_hash = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
            cur.execute(
                """
                INSERT INTO clarity_raw_exports
                    (sync_run_id, request_date, num_days, dimension1, dimension2, dimension3,
                     metric_name, information, payload_hash)
                VALUES (%s, (NOW() AT TIME ZONE 'UTC')::date, %s, %s, %s, %s, %s, %s::jsonb, %s)
                ON CONFLICT DO NOTHING
                """,
                (run_id, num_days, padded[0], padded[1], padded[2], metric_name, raw_json, raw_hash),
            )
            for row in information if isinstance(information, list) else []:
                if not isinstance(row, dict):
                    continue
                dimension_values, metrics = _split_row(row, dimensions)
                canonical = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                row_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                cur.execute(
                    """
                    INSERT INTO clarity_export_rows
                        (sync_run_id, request_date, num_days, metric_name,
                         dimension1, dimension2, dimension3, dimension_values, metrics, row_hash)
                    VALUES (%s, (NOW() AT TIME ZONE 'UTC')::date, %s, %s, %s, %s, %s,
                            %s::jsonb, %s::jsonb, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        run_id, num_days, metric_name, padded[0], padded[1], padded[2],
                        json.dumps(dimension_values, ensure_ascii=False),
                        json.dumps(metrics, ensure_ascii=False), row_hash,
                    ),
                )
                inserted_rows += cur.rowcount
        conn.commit()
        return inserted_rows
    except Exception:
        conn.rollback()
        raise
    finally:
        _close(conn, cur)


def _try_parse_date(value: str):
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _detect_dimension_column(headers: list[str]):
    lowered = {h.lower(): h for h in headers}
    for dim in PUBLISHED_DIMENSIONS:
        if dim.lower() in lowered:
            return lowered[dim.lower()]
    return None


def _detect_date_column(headers: list[str]):
    for h in headers:
        hl = h.lower().strip()
        if hl in ("date", "day", "tarih") or "date" in hl:
            return h
    return None


def _parse_csv_sections(raw_text: str) -> list[dict[str, Any]]:
    """Clarity'nin dashboard/widget CSV çıktısını savunmacı biçimde bölümlere ayırır.

    Gerçek Clarity export dosyası birden fazla widget'ı, aralarında boş satır
    bırakarak ve bazen bir başlık satırıyla birlikte içerebilir. Bu ayrıştırıcı
    tek düz tabloyu da, çok bölümlü bir dashboard özetini de kabul eder. Format
    beklenenden farklıysa satırlar yine de 'CSV Yükleme' başlığı altında tek
    bölüm olarak saklanır; hiçbir veri sessizce atlanmaz.
    """
    reader = csv.reader(_io.StringIO(raw_text))
    all_rows = [[cell.strip() for cell in row] for row in reader]
    sections: list[dict[str, Any]] = []
    current_title = None
    current_header = None
    current_rows: list[list[str]] = []

    def flush():
        if current_header and current_rows:
            sections.append({
                "title": current_title or "CSV Yükleme",
                "header": current_header,
                "rows": [r[:] for r in current_rows],
            })

    i = 0
    n = len(all_rows)
    while i < n:
        row = all_rows[i]
        non_empty = [c for c in row if c]
        if not non_empty:
            flush()
            current_title, current_header, current_rows = None, None, []
            i += 1
            continue
        if current_header is None:
            next_non_empty = [c for c in all_rows[i + 1] if c] if i + 1 < n else []
            if len(non_empty) == 1 and len(next_non_empty) > 1:
                current_title = non_empty[0]
                i += 1
                continue
            current_header = row
            i += 1
            continue
        current_rows.append(row)
        i += 1
    flush()
    return sections


def _persist_csv_rows(get_db, sections: list[dict[str, Any]], date_from, date_to) -> dict[str, int]:
    conn = get_db()
    if not conn:
        raise RuntimeError("DATABASE_URL bağlantısı kurulamadı")
    cur = None
    total = 0
    inserted = 0
    out_of_range = 0
    try:
        cur = conn.cursor()
        for section in sections:
            header = section["header"]
            metric_name = section["title"]
            date_col = _detect_date_column(header)
            dim_col = _detect_dimension_column(header)
            for raw_row in section["rows"]:
                total += 1
                row_dict = {
                    header[idx]: (raw_row[idx] if idx < len(raw_row) else "")
                    for idx in range(len(header))
                }
                row_date = _try_parse_date(row_dict.get(date_col, "")) if date_col else None
                if row_date and date_from and date_to and (row_date < date_from or row_date > date_to):
                    out_of_range += 1
                dimension_values = {dim_col: row_dict.get(dim_col)} if dim_col else {}
                metrics = {k: v for k, v in row_dict.items() if k != dim_col}
                canonical = json.dumps(row_dict, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                row_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                effective_date = row_date or date_to or date_from or _utc_now().date()
                cur.execute(
                    """
                    INSERT INTO clarity_export_rows
                        (sync_run_id, request_date, num_days, metric_name,
                         dimension1, dimension2, dimension3, dimension_values, metrics, row_hash, source)
                    VALUES (NULL, %s, 0, %s, %s, NULL, NULL, %s::jsonb, %s::jsonb, %s, 'manual_upload')
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        effective_date, metric_name, dim_col,
                        json.dumps(dimension_values, ensure_ascii=False),
                        json.dumps(metrics, ensure_ascii=False), row_hash,
                    ),
                )
                inserted += cur.rowcount
        conn.commit()
        return {"total_rows": total, "inserted_rows": inserted, "out_of_range_rows": out_of_range}
    except Exception:
        conn.rollback()
        raise
    finally:
        _close(conn, cur)


def _request_export(num_days: int, dimensions: tuple[str, ...]) -> tuple[int, list[dict[str, Any]], str]:
    params: dict[str, Any] = {"numOfDays": str(num_days)}
    for index, dimension in enumerate(dimensions, start=1):
        params[f"dimension{index}"] = dimension
    response = requests.get(
        _endpoint(),
        params=params,
        headers={
            "Authorization": f"Bearer {_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("Clarity API beklenmeyen yanıt biçimi döndürdü")
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return response.status_code, payload, hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _sync_all(get_db: Callable[[], Any], num_days: int = 3) -> dict[str, Any]:
    if not _enabled():
        raise RuntimeError("CLARITY_SYNC_ENABLED aktif değil")
    if not _token():
        raise RuntimeError("CLARITY_API_TOKEN eksik")
    if num_days not in (1, 2, 3):
        raise ValueError("num_days yalnızca 1, 2 veya 3 olabilir")

    _init_db(get_db)
    usage = _daily_usage(get_db)
    remaining = max(0, DAILY_REQUEST_LIMIT - usage)
    plans: list[tuple[str, ...]] = [tuple()] + [(dimension,) for dimension in PUBLISHED_DIMENSIONS]
    if remaining < len(plans):
        raise RuntimeError(
            f"Bugünkü Clarity kotası yetersiz: {remaining} çağrı kaldı, tam senkronizasyon 10 çağrı ister"
        )

    batch_key = _utc_now().strftime("clarity-full-%Y%m%dT%H%M%SZ")
    results = []
    for dimensions in plans:
        run_id = _begin_run(get_db, batch_key, num_days, dimensions)
        try:
            status_code, payload, response_hash = _request_export(num_days, dimensions)
            inserted = _persist_payload(get_db, run_id, num_days, dimensions, payload)
            total_rows = sum(
                len(item.get("information") or [])
                for item in payload if isinstance(item, dict) and isinstance(item.get("information") or [], list)
            )
            _finish_run(get_db, run_id, "success", status_code, total_rows, response_hash, None)
            results.append({
                "dimensions": list(dimensions),
                "metrics": len(payload),
                "rows": total_rows,
                "inserted_rows": inserted,
                "response_hash": response_hash,
            })
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            body = (exc.response.text[:1000] if exc.response is not None else str(exc))
            _finish_run(get_db, run_id, "http_error", status, 0, None, body)
            raise RuntimeError(f"Clarity API HTTP {status}: {body}") from exc
        except Exception as exc:
            _finish_run(get_db, run_id, "failed", None, 0, None, str(exc)[:1000])
            raise

    return {
        "ok": True,
        "batch_key": batch_key,
        "num_days": num_days,
        "requests_used": len(plans),
        "dimensions_exported": list(PUBLISHED_DIMENSIONS),
        "results": results,
        "note": "API'nin döndürdüğü tüm metrik alanları ham JSON ve satır bazında saklandı.",
    }


def install(app, *, get_db: Callable[[], Any], require_admin: Callable[[], Any]) -> None:
    _init_db(get_db)

    @app.get("/api/clarity/status")
    def clarity_status():
        denied = require_admin()
        if denied:
            return denied
        try:
            usage = _daily_usage(get_db)
            conn = get_db()
            last = None
            if conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT request_date, status, completed_at, row_count, dimension1
                    FROM clarity_sync_runs ORDER BY id DESC LIMIT 1
                    """
                )
                row = cur.fetchone()
                if row:
                    last = {
                        "request_date": str(row[0]), "status": row[1],
                        "completed_at": row[2].isoformat() if row[2] else None,
                        "row_count": row[3], "dimension": row[4],
                    }
                _close(conn, cur)
            return jsonify({
                "ok": True,
                "enabled": _enabled(),
                "configured": bool(_token()),
                "endpoint": _endpoint(),
                "timezone": "UTC",
                "daily_limit": DAILY_REQUEST_LIMIT,
                "used_today": usage,
                "remaining_today": max(0, DAILY_REQUEST_LIMIT - usage),
                "published_dimensions": list(PUBLISHED_DIMENSIONS),
                "last_run": last,
            })
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

    @app.post("/api/clarity/sync")
    def clarity_sync():
        denied = require_admin()
        if denied:
            return denied
        body = request.get_json(silent=True) or {}
        try:
            num_days = int(body.get("num_days", 3))
            return jsonify(_sync_all(get_db, num_days=num_days))
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except RuntimeError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 409
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

    @app.get("/api/clarity/metrics")
    def clarity_metrics():
        denied = require_admin()
        if denied:
            return denied
        metric_name = (request.args.get("metric") or "").strip()
        dimension = (request.args.get("dimension") or "").strip()
        source = (request.args.get("source") or "").strip()
        try:
            limit = min(max(int(request.args.get("limit", "500")), 1), 2000)
        except ValueError:
            return jsonify({"ok": False, "error": "limit geçersiz"}), 400
        conn = get_db()
        if not conn:
            return jsonify({"ok": False, "error": "Veritabanı bağlantısı yok"}), 503
        cur = None
        try:
            import psycopg2.extras
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            conditions = []
            params: list[Any] = []
            if metric_name:
                conditions.append("metric_name = %s")
                params.append(metric_name)
            if dimension:
                conditions.append("dimension1 = %s")
                params.append(dimension)
            if source:
                conditions.append("source = %s")
                params.append(source)
            where = " WHERE " + " AND ".join(conditions) if conditions else ""
            params.append(limit)
            cur.execute(
                """
                SELECT request_date, num_days, metric_name, dimension1, dimension2, dimension3,
                       dimension_values, metrics, imported_at, source
                FROM clarity_export_rows
                """ + where + " ORDER BY imported_at DESC, id DESC LIMIT %s",
                params,
            )
            rows = [dict(row) for row in cur.fetchall()]
            for row in rows:
                row["request_date"] = str(row["request_date"])
                row["imported_at"] = row["imported_at"].isoformat()
            return jsonify({"ok": True, "count": len(rows), "rows": rows})
        finally:
            _close(conn, cur)

    @app.post("/api/clarity/upload")
    def clarity_upload():
        """Clarity panelinden manuel indirilen CSV/PNG/PDF dosyasını kabul eder.

        CSV içeriği ayrıştırılıp clarity_export_rows tablosuna 'manual_upload'
        kaynağıyla yazılır (API senkronizasyonuyla aynı tabloyu paylaşır, böylece
        /api/clarity/metrics ikisini birden döndürür). PNG ve PDF dosyaları
        ayrıştırılmadan, ileride görüntülenmek/incelenmek üzere veritabanında
        ham dosya olarak saklanır — bu ilk sürümde metin/tablo çıkarımı yapılmaz.
        """
        denied = require_admin()
        if denied:
            return denied
        file = request.files.get("file")
        if not file or not file.filename:
            return jsonify({"ok": False, "error": "Dosya bulunamadı"}), 400

        filename = file.filename
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        upload_type = (request.form.get("upload_type") or "").strip().lower()
        if not upload_type:
            if ext == "csv":
                upload_type = "csv"
            elif ext in ("png", "jpg", "jpeg"):
                upload_type = "png"
            elif ext == "pdf":
                upload_type = "pdf"
            else:
                return jsonify({"ok": False, "error": "Desteklenmeyen dosya türü. CSV, PNG veya PDF yükleyin."}), 400

        date_from_raw = (request.form.get("date_from") or "").strip()
        date_to_raw = (request.form.get("date_to") or "").strip()
        date_from = _try_parse_date(date_from_raw) if date_from_raw else None
        date_to = _try_parse_date(date_to_raw) if date_to_raw else None
        if date_from_raw and not date_from:
            return jsonify({"ok": False, "error": "date_from formatı YYYY-MM-DD olmalı"}), 400
        if date_to_raw and not date_to:
            return jsonify({"ok": False, "error": "date_to formatı YYYY-MM-DD olmalı"}), 400
        if date_from and date_to and date_from > date_to:
            return jsonify({"ok": False, "error": "date_from, date_to değerinden sonra olamaz"}), 400

        raw_bytes = file.read()
        if not raw_bytes:
            return jsonify({"ok": False, "error": "Dosya boş"}), 400

        conn = get_db()
        if not conn:
            return jsonify({"ok": False, "error": "Veritabanı bağlantısı yok"}), 503

        row_count = 0
        out_of_range = 0
        notes = None

        try:
            if upload_type == "csv":
                try:
                    text = raw_bytes.decode("utf-8-sig")
                except UnicodeDecodeError:
                    text = raw_bytes.decode("latin-1")
                sections = _parse_csv_sections(text)
                if not sections:
                    notes = "CSV içinde okunabilir bir tablo bulunamadı; dosya yalnızca arşivlendi."
                else:
                    result = _persist_csv_rows(get_db, sections, date_from, date_to)
                    row_count = result["inserted_rows"]
                    out_of_range = result["out_of_range_rows"]
                    if out_of_range:
                        notes = f"{out_of_range} satır seçilen tarih aralığının dışında görünüyor."

            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO clarity_uploads
                    (upload_type, filename, mime_type, date_from, date_to, file_data,
                     file_size, row_count, out_of_range_rows, notes, uploaded_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    upload_type, filename, file.mimetype, date_from, date_to,
                    psycopg2.Binary(raw_bytes), len(raw_bytes), row_count, out_of_range, notes,
                    session.get("user_email"),
                ),
            )
            upload_id = cur.fetchone()[0]
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({
                "ok": True,
                "upload_id": upload_id,
                "upload_type": upload_type,
                "row_count": row_count,
                "out_of_range_rows": out_of_range,
                "notes": notes,
            })
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            conn.close()
            return jsonify({"ok": False, "error": str(exc)}), 500

    @app.get("/api/clarity/uploads")
    def clarity_uploads_list():
        denied = require_admin()
        if denied:
            return denied
        conn = get_db()
        if not conn:
            return jsonify({"ok": False, "error": "Veritabanı bağlantısı yok"}), 503
        cur = None
        try:
            import psycopg2.extras
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                """
                SELECT id, upload_type, filename, mime_type, date_from, date_to,
                       file_size, row_count, out_of_range_rows, notes, uploaded_by, uploaded_at
                FROM clarity_uploads ORDER BY id DESC LIMIT 200
                """
            )
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                r["date_from"] = str(r["date_from"]) if r["date_from"] else None
                r["date_to"] = str(r["date_to"]) if r["date_to"] else None
                r["uploaded_at"] = r["uploaded_at"].isoformat() if r["uploaded_at"] else None
            return jsonify({"ok": True, "uploads": rows})
        finally:
            _close(conn, cur)

    @app.get("/api/clarity/uploads/<int:upload_id>/file")
    def clarity_upload_file(upload_id):
        denied = require_admin()
        if denied:
            return denied
        conn = get_db()
        if not conn:
            return jsonify({"ok": False, "error": "Veritabanı bağlantısı yok"}), 503
        cur = None
        try:
            cur = conn.cursor()
            cur.execute("SELECT filename, mime_type, file_data FROM clarity_uploads WHERE id=%s", (upload_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"ok": False, "error": "Bulunamadı"}), 404
            filename, mime_type, file_data = row
            return Response(
                bytes(file_data),
                mimetype=mime_type or "application/octet-stream",
                headers={"Content-Disposition": f'inline; filename="{filename}"'},
            )
        finally:
            _close(conn, cur)
