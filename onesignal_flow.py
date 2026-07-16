import csv
import io
import json
import os
from datetime import datetime, timezone

import psycopg2.extras
import requests
from flask import Response, jsonify, request, session


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _ts(value):
    if value in (None, '', 0):
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        try:
            return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        except (TypeError, ValueError):
            return None


def _locale(value):
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ''
    return value.get('tr') or value.get('en') or next(iter(value.values()), '')


def install(app, get_db, require_admin=None):
    if getattr(app, '_onesignal_flow_installed', False):
        return
    app._onesignal_flow_installed = True

    app_id = os.environ.get('ONESIGNAL_APP_ID', '').strip()
    api_key = os.environ.get('ONESIGNAL_REST_API_KEY', '').strip()
    base_url = os.environ.get('ONESIGNAL_API_BASE', 'https://api.onesignal.com').rstrip('/')

    def configured():
        return bool(app_id and api_key)

    def headers():
        return {'Authorization': 'Key ' + api_key, 'Accept': 'application/json'}

    def api_get(path, params=None):
        if not configured():
            raise RuntimeError('ONESIGNAL_APP_ID ve ONESIGNAL_REST_API_KEY tanımlı değil.')
        response = requests.get(base_url + path, params=params or {}, headers=headers(), timeout=40)
        if not response.ok:
            try:
                detail = response.json()
            except Exception:
                detail = response.text[:800]
            raise RuntimeError('OneSignal API HTTP %s: %s' % (response.status_code, detail))
        return response.json()

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
                total_count INTEGER,
                pages INTEGER DEFAULT 0,
                error_text TEXT,
                triggered_by TEXT
            )
        ''')
        cur.execute('ALTER TABLE onesignal_sync_runs ADD COLUMN IF NOT EXISTS total_count INTEGER')
        cur.execute('ALTER TABLE onesignal_sync_runs ADD COLUMN IF NOT EXISTS pages INTEGER DEFAULT 0')
        conn.commit()
        cur.close()

    def db_or_error():
        conn = get_db()
        if not conn:
            return None, (jsonify({'error': 'Veritabanı bağlantısı yok. DATABASE_URL kontrol edin.'}), 503)
        ensure_schema(conn)
        return conn, None

    def upsert(conn, notifications):
        sql = '''
            INSERT INTO onesignal_messages (
                message_id,app_id,name,heading,content,url,included_segments,excluded_segments,
                queued_at,send_after,completed_at,successful,received,converted,failed,errored,
                remaining,canceled,platform_delivery_stats,outcomes,raw_payload,synced_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,NOW())
            ON CONFLICT (message_id) DO UPDATE SET
                name=EXCLUDED.name,heading=EXCLUDED.heading,content=EXCLUDED.content,url=EXCLUDED.url,
                included_segments=EXCLUDED.included_segments,excluded_segments=EXCLUDED.excluded_segments,
                queued_at=EXCLUDED.queued_at,send_after=EXCLUDED.send_after,completed_at=EXCLUDED.completed_at,
                successful=EXCLUDED.successful,received=EXCLUDED.received,converted=EXCLUDED.converted,
                failed=EXCLUDED.failed,errored=EXCLUDED.errored,remaining=EXCLUDED.remaining,
                canceled=EXCLUDED.canceled,platform_delivery_stats=EXCLUDED.platform_delivery_stats,
                outcomes=EXCLUDED.outcomes,raw_payload=EXCLUDED.raw_payload,synced_at=NOW()
        '''
        rows = []
        for n in notifications:
            message_id = n.get('id')
            if not message_id:
                continue
            rows.append((
                message_id,n.get('app_id') or app_id,n.get('name') or '',_locale(n.get('headings')),
                _locale(n.get('contents')),n.get('url') or n.get('web_url') or n.get('app_url') or '',
                json.dumps(n.get('included_segments') or []),json.dumps(n.get('excluded_segments') or []),
                _ts(n.get('queued_at')),_ts(n.get('send_after')),_ts(n.get('completed_at')),
                int(n.get('successful') or 0),int(n.get('received') or 0),int(n.get('converted') or 0),
                int(n.get('failed') or 0),int(n.get('errored') or 0),int(n.get('remaining') or 0),
                bool(n.get('canceled')),json.dumps(n.get('platform_delivery_stats') or {}),
                json.dumps(n.get('outcomes') or {}),json.dumps(n)
            ))
        if rows:
            cur = conn.cursor()
            cur.executemany(sql, rows)
            conn.commit()
            cur.close()
        return len(rows)

    def fetch_all_messages(max_messages=5000):
        all_rows = []
        offset = 0
        total_count = None
        pages = 0
        while len(all_rows) < max_messages:
            payload = api_get('/notifications', {'app_id': app_id, 'limit': 50, 'offset': offset})
            page = payload.get('notifications') or []
            total_count = int(payload.get('total_count') or len(page))
            pages += 1
            all_rows.extend(page)
            if not page or len(page) < 50 or len(all_rows) >= total_count:
                break
            offset += len(page)
        return all_rows[:max_messages], total_count, pages

    def last_run(conn):
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute('''SELECT id,started_at,finished_at,status,fetched_count,upserted_count,total_count,pages,error_text,triggered_by
                       FROM onesignal_sync_runs ORDER BY id DESC LIMIT 1''')
        row = cur.fetchone()
        cur.close()
        if not row:
            return None
        result = dict(row)
        for key in ('started_at', 'finished_at'):
            if result.get(key):
                result[key] = result[key].isoformat()
        return result

    @app.get('/onesignal/status')
    def onesignal_status():
        conn = get_db()
        db_ok = bool(conn)
        count = 0
        last_sync = None
        run = None
        if conn:
            try:
                ensure_schema(conn)
                cur = conn.cursor()
                cur.execute('SELECT COUNT(*),MAX(synced_at) FROM onesignal_messages')
                count, last_sync = cur.fetchone()
                cur.close()
                run = last_run(conn)
            finally:
                conn.close()
        return jsonify({
            'configured': configured(),'app_id_set': bool(app_id),'api_key_set': bool(api_key),
            'database_ok': db_ok,'message_count': count or 0,
            'last_sync_at': last_sync.isoformat() if last_sync else None,'last_run': run
        })

    @app.get('/onesignal/diagnostics')
    def onesignal_diagnostics():
        result = {'checked_at': _now_iso(),'configured': configured(),'database_ok': False,'api_ok': False}
        conn = get_db()
        if conn:
            try:
                ensure_schema(conn)
                result['database_ok'] = True
                result['last_run'] = last_run(conn)
            finally:
                conn.close()
        if configured():
            try:
                payload = api_get('/notifications', {'app_id': app_id, 'limit': 1, 'offset': 0})
                result['api_ok'] = True
                result['remote_total_count'] = int(payload.get('total_count') or 0)
                result['sample_count'] = len(payload.get('notifications') or [])
            except Exception as exc:
                result['api_error'] = str(exc)
        return jsonify(result), (200 if result['api_ok'] and result['database_ok'] else 503)

    @app.post('/onesignal/sync')
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
                        (session.get('user_email') or 'panel',))
            run_id = cur.fetchone()[0]
            conn.commit(); cur.close()
            requested_max = int((request.get_json(silent=True) or {}).get('max_messages') or 5000)
            max_messages = max(50, min(requested_max, 20000))
            notifications, total_count, pages = fetch_all_messages(max_messages)
            count = upsert(conn, notifications)
            cur = conn.cursor()
            cur.execute('''UPDATE onesignal_sync_runs SET finished_at=NOW(),status='success',fetched_count=%s,
                           upserted_count=%s,total_count=%s,pages=%s WHERE id=%s''',
                        (len(notifications), count, total_count, pages, run_id))
            conn.commit(); cur.close()
            return jsonify({'ok': True,'fetched': len(notifications),'upserted': count,
                            'total_count': total_count,'pages': pages,'synced_at': _now_iso()})
        except Exception as exc:
            if run_id:
                try:
                    cur = conn.cursor()
                    cur.execute("UPDATE onesignal_sync_runs SET finished_at=NOW(),status='error',error_text=%s WHERE id=%s",
                                (str(exc)[:3000], run_id))
                    conn.commit(); cur.close()
                except Exception:
                    conn.rollback()
            return jsonify({'error': str(exc),'run_id': run_id}), 502
        finally:
            conn.close()

    @app.get('/onesignal/dashboard')
    def onesignal_dashboard():
        conn, error = db_or_error()
        if error:
            return error
        days = max(1, min(int(request.args.get('days', 36500)), 36500))
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute('''SELECT COUNT(*) messages,COALESCE(SUM(successful),0) sent,COALESCE(SUM(received),0) received,
                                  COALESCE(SUM(converted),0) clicks,COALESCE(SUM(failed),0) failed,COALESCE(SUM(errored),0) errored
                           FROM onesignal_messages WHERE COALESCE(queued_at,synced_at)>=NOW()-(%s||' days')::interval''',(days,))
            summary = dict(cur.fetchone())
            sent, received, clicks = int(summary['sent'] or 0), int(summary['received'] or 0), int(summary['clicks'] or 0)
            summary['ctr'] = round(clicks / sent * 100, 2) if sent else 0
            summary['delivery_rate'] = round(received / sent * 100, 2) if sent else 0
            cur.execute('''SELECT TO_CHAR(DATE_TRUNC('day',COALESCE(queued_at,synced_at)),'YYYY-MM-DD') day,
                                  COUNT(*) messages,COALESCE(SUM(successful),0) sent,
                                  COALESCE(SUM(received),0) received,COALESCE(SUM(converted),0) clicks
                           FROM onesignal_messages WHERE COALESCE(queued_at,synced_at)>=NOW()-(%s||' days')::interval
                           GROUP BY 1 ORDER BY 1''',(days,))
            trend = [dict(r) for r in cur.fetchall()]
            cur.execute('SELECT MAX(synced_at) last_sync_at FROM onesignal_messages')
            last_sync = cur.fetchone()['last_sync_at']
            cur.close()
            return jsonify({'summary': summary,'trend': trend,'days': days,
                            'last_sync_at': last_sync.isoformat() if last_sync else None})
        finally:
            conn.close()

    @app.get('/onesignal/messages')
    def onesignal_messages():
        conn, error = db_or_error()
        if error:
            return error
        days = max(1, min(int(request.args.get('days', 36500)), 36500))
        limit = max(1, min(int(request.args.get('limit', 500)), 5000))
        search = (request.args.get('q') or '').strip()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            where = "COALESCE(queued_at,synced_at)>=NOW()-(%s||' days')::interval"
            params = [days]
            if search:
                token = '%' + search + '%'
                where += " AND (COALESCE(name,'') ILIKE %s OR COALESCE(heading,'') ILIKE %s OR COALESCE(content,'') ILIKE %s)"
                params += [token, token, token]
            params.append(limit)
            cur.execute('''SELECT message_id,name,heading,content,url,included_segments,excluded_segments,queued_at,
                                  completed_at,successful,received,converted,failed,errored,remaining,canceled,
                                  platform_delivery_stats,outcomes
                           FROM onesignal_messages WHERE '''+where+''' ORDER BY COALESCE(queued_at,synced_at) DESC LIMIT %s''',params)
            rows = []
            for row in cur.fetchall():
                item = dict(row)
                for key in ('queued_at','completed_at'):
                    if item.get(key): item[key] = item[key].isoformat()
                sent = int(item.get('successful') or 0)
                item['ctr'] = round(int(item.get('converted') or 0) / sent * 100, 2) if sent else 0
                rows.append(item)
            cur.close()
            return jsonify({'messages': rows,'count': len(rows)})
        finally:
            conn.close()

    @app.get('/onesignal/sync-runs')
    def onesignal_sync_runs():
        conn, error = db_or_error()
        if error:
            return error
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute('''SELECT id,started_at,finished_at,status,fetched_count,upserted_count,total_count,pages,error_text,triggered_by
                           FROM onesignal_sync_runs ORDER BY id DESC LIMIT 100''')
            rows = []
            for row in cur.fetchall():
                item = dict(row)
                for key in ('started_at','finished_at'):
                    if item.get(key): item[key] = item[key].isoformat()
                rows.append(item)
            cur.close()
            return jsonify({'runs': rows})
        finally:
            conn.close()

    @app.get('/onesignal/export.csv')
    def onesignal_export():
        conn, error = db_or_error()
        if error:
            return error
        try:
            cur = conn.cursor()
            cur.execute('''SELECT message_id,name,heading,content,queued_at,successful,received,converted,failed,errored
                           FROM onesignal_messages ORDER BY COALESCE(queued_at,synced_at) DESC''')
            output = io.StringIO(); writer = csv.writer(output)
            writer.writerow(['message_id','name','heading','content','queued_at','successful','received','converted','failed','errored'])
            writer.writerows(cur.fetchall()); cur.close()
            return Response('\ufeff'+output.getvalue(),mimetype='text/csv; charset=utf-8',
                            headers={'Content-Disposition':'attachment; filename=onesignal-bildirimler.csv'})
        finally:
            conn.close()
