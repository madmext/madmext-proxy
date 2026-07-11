import csv
import io
import json
import os
from datetime import datetime, timezone

import psycopg2.extras
import requests
from flask import jsonify, request, Response


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _ts(value):
    if value in (None, '', 0):
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _pick_locale(value):
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ''
    return value.get('tr') or value.get('en') or next(iter(value.values()), '')


def install(app, get_db, require_admin=None):
    app_id = os.environ.get('ONESIGNAL_APP_ID', '').strip()
    api_key = os.environ.get('ONESIGNAL_REST_API_KEY', '').strip()
    base_url = os.environ.get('ONESIGNAL_API_BASE', 'https://api.onesignal.com').rstrip('/')

    def configured():
        return bool(app_id and api_key)

    def auth_headers():
        return {'Authorization': 'Key ' + api_key, 'Accept': 'application/json'}

    def ensure_schema(conn):
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS onesignal_messages (
                message_id TEXT PRIMARY KEY,
                app_id TEXT NOT NULL,
                name TEXT,
                heading TEXT,
                content TEXT,
                url TEXT,
                included_segments JSONB DEFAULT '[]'::jsonb,
                excluded_segments JSONB DEFAULT '[]'::jsonb,
                queued_at TIMESTAMPTZ,
                send_after TIMESTAMPTZ,
                completed_at TIMESTAMPTZ,
                successful INTEGER DEFAULT 0,
                received INTEGER DEFAULT 0,
                converted INTEGER DEFAULT 0,
                failed INTEGER DEFAULT 0,
                errored INTEGER DEFAULT 0,
                remaining INTEGER DEFAULT 0,
                canceled BOOLEAN DEFAULT FALSE,
                platform_delivery_stats JSONB DEFAULT '{}'::jsonb,
                outcomes JSONB DEFAULT '{}'::jsonb,
                raw_payload JSONB NOT NULL,
                synced_at TIMESTAMPTZ DEFAULT NOW()
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_onesignal_messages_queued_at ON onesignal_messages(queued_at DESC)')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS onesignal_sync_runs (
                id BIGSERIAL PRIMARY KEY,
                started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                finished_at TIMESTAMPTZ,
                status TEXT NOT NULL DEFAULT 'running',
                fetched_count INTEGER DEFAULT 0,
                upserted_count INTEGER DEFAULT 0,
                error_text TEXT,
                triggered_by TEXT
            )
        ''')
        conn.commit()
        cur.close()

    def db_or_error():
        conn = get_db()
        if not conn:
            return None, (jsonify({'error': 'Veritabanı bağlantısı yok. DATABASE_URL kontrol edin.'}), 503)
        ensure_schema(conn)
        return conn, None

    def onesignal_get(path, params=None):
        if not configured():
            raise RuntimeError('ONESIGNAL_APP_ID ve ONESIGNAL_REST_API_KEY tanımlı değil.')
        response = requests.get(base_url + path, params=params or {}, headers=auth_headers(), timeout=30)
        if not response.ok:
            try:
                detail = response.json()
            except Exception:
                detail = response.text[:500]
            raise RuntimeError('OneSignal API HTTP %s: %s' % (response.status_code, detail))
        return response.json()

    def upsert_messages(conn, notifications):
        sql = '''
            INSERT INTO onesignal_messages (
                message_id, app_id, name, heading, content, url,
                included_segments, excluded_segments, queued_at, send_after, completed_at,
                successful, received, converted, failed, errored, remaining, canceled,
                platform_delivery_stats, outcomes, raw_payload, synced_at
            ) VALUES (
                %s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,NOW()
            )
            ON CONFLICT (message_id) DO UPDATE SET
                name=EXCLUDED.name, heading=EXCLUDED.heading, content=EXCLUDED.content,
                url=EXCLUDED.url, included_segments=EXCLUDED.included_segments,
                excluded_segments=EXCLUDED.excluded_segments, queued_at=EXCLUDED.queued_at,
                send_after=EXCLUDED.send_after, completed_at=EXCLUDED.completed_at,
                successful=EXCLUDED.successful, received=EXCLUDED.received,
                converted=EXCLUDED.converted, failed=EXCLUDED.failed,
                errored=EXCLUDED.errored, remaining=EXCLUDED.remaining,
                canceled=EXCLUDED.canceled,
                platform_delivery_stats=EXCLUDED.platform_delivery_stats,
                outcomes=EXCLUDED.outcomes, raw_payload=EXCLUDED.raw_payload, synced_at=NOW()
        '''
        rows = []
        for n in notifications:
            rows.append((
                n.get('id'), n.get('app_id') or app_id, n.get('name') or '',
                _pick_locale(n.get('headings')), _pick_locale(n.get('contents')),
                n.get('url') or n.get('web_url') or n.get('app_url') or '',
                json.dumps(n.get('included_segments') or []),
                json.dumps(n.get('excluded_segments') or []),
                _ts(n.get('queued_at')), _ts(n.get('send_after')), _ts(n.get('completed_at')),
                int(n.get('successful') or 0), int(n.get('received') or 0),
                int(n.get('converted') or 0), int(n.get('failed') or 0),
                int(n.get('errored') or 0), int(n.get('remaining') or 0),
                bool(n.get('canceled')), json.dumps(n.get('platform_delivery_stats') or {}),
                json.dumps(n.get('outcomes') or {}), json.dumps(n)
            ))
        if rows:
            cur = conn.cursor()
            cur.executemany(sql, rows)
            conn.commit()
            cur.close()
        return len(rows)

    @app.route('/onesignal/status', methods=['GET'])
    def onesignal_status():
        conn = get_db()
        db_ok = bool(conn)
        count = 0
        last_sync = None
        if conn:
            try:
                ensure_schema(conn)
                cur = conn.cursor()
                cur.execute('SELECT COUNT(*), MAX(synced_at) FROM onesignal_messages')
                count, last_sync = cur.fetchone()
                cur.close()
            finally:
                conn.close()
        return jsonify({
            'configured': configured(), 'app_id_set': bool(app_id), 'api_key_set': bool(api_key),
            'database_ok': db_ok, 'message_count': count or 0,
            'last_sync_at': last_sync.isoformat() if last_sync else None
        })

    @app.route('/onesignal/sync', methods=['POST'])
    def onesignal_sync():
        if require_admin:
            denied = require_admin()
            if denied:
                return denied
        conn, error = db_or_error()
        if error:
            return error
        run_id = None
        try:
            cur = conn.cursor()
            cur.execute('INSERT INTO onesignal_sync_runs(triggered_by) VALUES(%s) RETURNING id',
                        (request.environ.get('REMOTE_USER') or 'panel',))
            run_id = cur.fetchone()[0]
            conn.commit(); cur.close()
            payload = onesignal_get('/notifications', {'app_id': app_id, 'limit': 50, 'offset': 0})
            notifications = payload.get('notifications') or []
            count = upsert_messages(conn, notifications)
            cur = conn.cursor()
            cur.execute('UPDATE onesignal_sync_runs SET finished_at=NOW(),status=%s,fetched_count=%s,upserted_count=%s WHERE id=%s',
                        ('success', len(notifications), count, run_id))
            conn.commit(); cur.close()
            return jsonify({'ok': True, 'fetched': len(notifications), 'upserted': count,
                            'total_count': payload.get('total_count'), 'synced_at': _now_iso()})
        except Exception as exc:
            if run_id:
                try:
                    cur = conn.cursor()
                    cur.execute('UPDATE onesignal_sync_runs SET finished_at=NOW(),status=%s,error_text=%s WHERE id=%s',
                                ('error', str(exc)[:2000], run_id))
                    conn.commit(); cur.close()
                except Exception:
                    conn.rollback()
            return jsonify({'error': str(exc)}), 502
        finally:
            conn.close()

    @app.route('/onesignal/dashboard', methods=['GET'])
    def onesignal_dashboard():
        conn, error = db_or_error()
        if error:
            return error
        days = max(1, min(int(request.args.get('days', 30)), 3650))
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute('''
                SELECT COUNT(*) AS messages,
                       COALESCE(SUM(successful),0) AS sent,
                       COALESCE(SUM(received),0) AS received,
                       COALESCE(SUM(converted),0) AS clicks,
                       COALESCE(SUM(failed),0) AS failed,
                       COALESCE(SUM(errored),0) AS errored
                FROM onesignal_messages
                WHERE COALESCE(queued_at, synced_at) >= NOW() - (%s || ' days')::interval
            ''', (days,))
            summary = dict(cur.fetchone())
            sent = int(summary.get('sent') or 0)
            received = int(summary.get('received') or 0)
            clicks = int(summary.get('clicks') or 0)
            summary['ctr'] = round((clicks / sent * 100), 2) if sent else 0
            summary['delivery_rate'] = round((received / sent * 100), 2) if sent else 0
            cur.execute('''
                SELECT TO_CHAR(DATE_TRUNC('day', COALESCE(queued_at,synced_at)), 'YYYY-MM-DD') AS day,
                       COUNT(*) AS messages, COALESCE(SUM(successful),0) AS sent,
                       COALESCE(SUM(received),0) AS received, COALESCE(SUM(converted),0) AS clicks
                FROM onesignal_messages
                WHERE COALESCE(queued_at, synced_at) >= NOW() - (%s || ' days')::interval
                GROUP BY 1 ORDER BY 1
            ''', (days,))
            trend = [dict(r) for r in cur.fetchall()]
            cur.execute('SELECT MAX(synced_at) AS last_sync_at FROM onesignal_messages')
            last_sync = cur.fetchone()['last_sync_at']
            cur.close()
            return jsonify({'summary': summary, 'trend': trend, 'days': days,
                            'last_sync_at': last_sync.isoformat() if last_sync else None})
        finally:
            conn.close()

    @app.route('/onesignal/messages', methods=['GET'])
    def onesignal_messages():
        conn, error = db_or_error()
        if error:
            return error
        days = max(1, min(int(request.args.get('days', 30)), 3650))
        limit = max(1, min(int(request.args.get('limit', 100)), 1000))
        search = (request.args.get('q') or '').strip()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            where = "COALESCE(queued_at,synced_at) >= NOW() - (%s || ' days')::interval"
            params = [days]
            if search:
                where += " AND (COALESCE(name,'') ILIKE %s OR COALESCE(heading,'') ILIKE %s OR COALESCE(content,'') ILIKE %s)"
                token = '%' + search + '%'
                params.extend([token, token, token])
            params.append(limit)
            cur.execute('''
                SELECT message_id,name,heading,content,url,included_segments,queued_at,completed_at,
                       successful,received,converted,failed,errored,remaining,canceled
                FROM onesignal_messages WHERE ''' + where + '''
                ORDER BY COALESCE(queued_at,synced_at) DESC LIMIT %s
            ''', params)
            rows = []
            for row in cur.fetchall():
                item = dict(row)
                for key in ('queued_at', 'completed_at'):
                    if item.get(key): item[key] = item[key].isoformat()
                sent = int(item.get('successful') or 0)
                item['ctr'] = round(int(item.get('converted') or 0) / sent * 100, 2) if sent else 0
                rows.append(item)
            cur.close()
            return jsonify({'messages': rows, 'count': len(rows)})
        finally:
            conn.close()

    @app.route('/onesignal/export.csv', methods=['GET'])
    def onesignal_export():
        conn, error = db_or_error()
        if error:
            return error
        try:
            cur = conn.cursor()
            cur.execute('''SELECT message_id,name,heading,content,queued_at,successful,received,converted,failed,errored
                           FROM onesignal_messages ORDER BY COALESCE(queued_at,synced_at) DESC''')
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['message_id','name','heading','content','queued_at','successful','received','converted','failed','errored'])
            for row in cur.fetchall():
                writer.writerow(row)
            cur.close()
            csv_text = '\ufeff' + output.getvalue()
            return Response(csv_text, mimetype='text/csv; charset=utf-8',
                            headers={'Content-Disposition': 'attachment; filename=onesignal-bildirimler.csv'})
        finally:
            conn.close()
