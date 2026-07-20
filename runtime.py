"""Unified Railway runtime for Madmext Ads.

All feature modules are installed on the same Flask app before Gunicorn
starts serving requests. This prevents frontend/backend route drift.
"""

import os

import psycopg2.extras
from flask import Response, jsonify, request, send_from_directory, session

from server import app
from app import gads_campaign_rows, get_db, get_ga4_token, get_users, hash_pw, read_logs, require_admin, save_users, verify_pw, write_logs

import clarity_flow
import meta_sync_flow
import onesignal_flow
import telegram_flow
import telegram_ai_engine
import tiktok_oauth
import security_core
import rbac_core
import marketplace_core
import decision_core
import operations_core

rbac_core.install(app, get_db=get_db)
security_core.install(app, get_db=get_db)
operations_core.install(app)
marketplace_core.install(app, get_db=get_db)
decision_core.install(app, get_db=get_db)
clarity_flow.install(app, get_db=get_db, require_admin=require_admin)
tiktok_oauth.install(app, get_db=get_db, require_admin=require_admin)


meta_sync_flow.install(
    app,
    get_db=get_db,
    read_logs=read_logs,
    write_logs=write_logs,
    require_admin=require_admin,
)

onesignal_flow.install(
    app,
    get_db=get_db,
    require_admin=require_admin,
)

telegram_engine = telegram_ai_engine.TelegramAIEngine(
    app, get_db, ga4_token_getter=get_ga4_token, gads_campaign_fetcher=gads_campaign_rows
)

telegram_flow.install(
    app,
    get_db=get_db,
    get_users=get_users,
    hash_pw=hash_pw,
    verify_pw=verify_pw,
    save_users=save_users,
    ai_engine=telegram_engine,
)


@app.before_request
def mx_onesignal_dashboard_override():
    """Serve the OneSignal dashboard with PostgreSQL-safe aliases."""
    if request.path.rstrip('/') != '/onesignal/dashboard' or request.method != 'GET':
        return None
    conn = get_db()
    if not conn:
        return jsonify({'error': 'Veritabanı bağlantısı yok. DATABASE_URL kontrol edin.'}), 503
    try:
        days = max(1, min(int(request.args.get('days', 36500)), 36500))
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT
                COUNT(*) AS messages,
                COALESCE(SUM(successful), 0) AS sent,
                COALESCE(SUM(received), 0) AS received,
                COALESCE(SUM(converted), 0) AS clicks,
                COALESCE(SUM(failed), 0) AS failed,
                COALESCE(SUM(errored), 0) AS errored
            FROM onesignal_messages
            WHERE COALESCE(queued_at, synced_at) >= NOW() - (%s * INTERVAL '1 day')
            """,
            (days,),
        )
        summary = dict(cur.fetchone())
        sent = int(summary.get('sent') or 0)
        received = int(summary.get('received') or 0)
        clicks = int(summary.get('clicks') or 0)
        summary['ctr'] = round(clicks / sent * 100, 2) if sent else 0
        summary['delivery_rate'] = round(received / sent * 100, 2) if sent else 0

        cur.execute(
            """
            SELECT
                TO_CHAR(DATE_TRUNC('day', COALESCE(queued_at, synced_at)), 'YYYY-MM-DD') AS trend_date,
                COUNT(*) AS messages,
                COALESCE(SUM(successful), 0) AS sent,
                COALESCE(SUM(received), 0) AS received,
                COALESCE(SUM(converted), 0) AS clicks
            FROM onesignal_messages
            WHERE COALESCE(queued_at, synced_at) >= NOW() - (%s * INTERVAL '1 day')
            GROUP BY DATE_TRUNC('day', COALESCE(queued_at, synced_at))
            ORDER BY DATE_TRUNC('day', COALESCE(queued_at, synced_at))
            """,
            (days,),
        )
        trend = []
        for row in cur.fetchall():
            item = dict(row)
            item['day'] = item.pop('trend_date', None)
            trend.append(item)

        cur.execute('SELECT MAX(synced_at) AS last_sync_at FROM onesignal_messages')
        last_sync = cur.fetchone().get('last_sync_at')
        cur.close()
        return jsonify({
            'summary': summary,
            'trend': trend,
            'days': days,
            'last_sync_at': last_sync.isoformat() if last_sync else None,
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500
    finally:
        conn.close()


@app.before_request
def mx_meta_module_response():
    """Serve the Meta module with the runtime synchronization hooks injected."""
    if request.path.rstrip('/') != '/modules/meta-ads.html':
        return None
    module_path = os.path.join('.', 'modules', 'meta-ads.html')
    if not os.path.isfile(module_path):
        return None
    with open(module_path, 'r', encoding='utf-8') as module_file:
        html = module_file.read()
    try:
        html = meta_sync_flow._inject_meta_module(html)
    except Exception as exc:
        print('mx meta module:', exc)
    return Response(html, mimetype='text/html; charset=utf-8')


_RESERVED_PREFIXES = (
    'api', 'auth', 'admin', 'ga4', 'gads', 'logs', 'psi', 'claude',
    'proxy-xml', 'trendyol', 'tiktok', 'onesignal', 'marketplace', 'telegram', 'runtime',
)


@app.route('/<path:path>')
def spa_fallback(path):
    """Serve existing files or the authenticated panel for frontend routes."""
    clean_path = (path or '').strip('/')
    first_part = clean_path.split('/', 1)[0]
    if first_part in _RESERVED_PREFIXES:
        return jsonify({'error': 'Endpoint bulunamadı'}), 404
    if clean_path:
        root_file = os.path.join('.', clean_path)
        if os.path.isfile(root_file):
            directory = os.path.dirname(clean_path) or '.'
            return send_from_directory(directory, os.path.basename(clean_path))
    if not session.get('user_email'):
        fallback = 'login.html' if os.path.exists('login.html') else 'index.html'
        return send_from_directory('.', fallback)
    return send_from_directory('.', 'index.html')


@app.get('/runtime/health')
def runtime_health():
    return {
        'ok': True,
        'runtime': 'runtime.py',
        'onesignal_routes': True,
        'onesignal_dashboard_override': True,
        'clarity_routes': True,
        'tiktok_oauth_routes': True,
        'clarity_navigation': True,
        'clarity_navigation_version': '2026.3-native',
    }
