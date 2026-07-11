"""Marketplace ingestion pipeline: source -> normalize -> snapshot -> quality."""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from flask import jsonify, request, session


MARKETPLACES = ('trendyol','hepsiburada','n11','amazon','lcw','flo')
REQUIRED = ('entity_type','external_id','name')
NUMERIC = ('spend','revenue','impressions','clicks','orders','daily_budget')


def _iso(value):
    if not value:
        return datetime.now(timezone.utc)
    text = str(value).strip().replace('Z', '+00:00')
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _number(value, field, issues):
    try:
        n = Decimal(str(value or 0))
        if n < 0:
            issues.append({'code':'negative_value','field':field,'severity':'error','message':field+' negatif olamaz'})
        return n
    except (InvalidOperation, ValueError):
        issues.append({'code':'invalid_number','field':field,'severity':'error','message':field+' sayısal değil'})
        return Decimal('0')


def normalize_record(marketplace, raw):
    issues = []
    for field in REQUIRED:
        if not str(raw.get(field) or '').strip():
            issues.append({'code':'missing_field','field':field,'severity':'error','message':field+' zorunlu'})
    data = {
        'marketplace': marketplace,
        'entity_type': str(raw.get('entity_type') or '').strip().lower(),
        'external_id': str(raw.get('external_id') or '').strip(),
        'parent_external_id': str(raw.get('parent_external_id') or '').strip() or None,
        'name': str(raw.get('name') or '').strip(),
        'status': str(raw.get('status') or 'unknown').strip().lower(),
        'currency': str(raw.get('currency') or 'TRY').strip().upper(),
        'product_code': str(raw.get('product_code') or '').strip() or None,
    }
    if data['currency'] not in ('TRY','USD','EUR'):
        issues.append({'code':'invalid_currency','field':'currency','severity':'error','message':'Para birimi desteklenmiyor'})
    for field in NUMERIC:
        data[field] = _number(raw.get(field), field, issues)
    data['roas'] = (data['revenue'] / data['spend']) if data['spend'] > 0 else Decimal('0')
    data['conversion_rate'] = (data['orders'] / data['clicks'] * 100) if data['clicks'] > 0 else Decimal('0')
    if data['revenue'] > 0 and data['orders'] == 0:
        issues.append({'code':'revenue_without_orders','field':'orders','severity':'warning','message':'Ciro var fakat sipariş yok'})
    return data, issues


def _init_db(get_db):
    conn=get_db()
    if not conn:return
    try:
        cur=conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS mx_marketplaces(
          marketplace_key TEXT PRIMARY KEY,name TEXT NOT NULL,is_active BOOLEAN DEFAULT TRUE,created_at TIMESTAMPTZ DEFAULT NOW())""")
        cur.execute("""CREATE TABLE IF NOT EXISTS mx_data_sources(
          id BIGSERIAL PRIMARY KEY,marketplace_key TEXT REFERENCES mx_marketplaces,source_type TEXT NOT NULL,
          name TEXT NOT NULL,config JSONB DEFAULT '{}'::jsonb,is_active BOOLEAN DEFAULT TRUE,last_sync_at TIMESTAMPTZ,
          UNIQUE(marketplace_key,source_type,name))""")
        cur.execute("""CREATE TABLE IF NOT EXISTS mx_import_jobs(
          id UUID PRIMARY KEY,marketplace_key TEXT,source_type TEXT,status TEXT NOT NULL,started_at TIMESTAMPTZ,
          finished_at TIMESTAMPTZ,actor_email TEXT,record_count INTEGER DEFAULT 0,accepted_count INTEGER DEFAULT 0,
          rejected_count INTEGER DEFAULT 0,error_message TEXT,metadata JSONB DEFAULT '{}'::jsonb)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS mx_snapshots(
          id UUID PRIMARY KEY,job_id UUID REFERENCES mx_import_jobs(id),marketplace_key TEXT NOT NULL,source_type TEXT NOT NULL,
          captured_at TIMESTAMPTZ NOT NULL,content_hash TEXT UNIQUE NOT NULL,record_count INTEGER NOT NULL,
          quality_status TEXT NOT NULL,raw_metadata JSONB DEFAULT '{}'::jsonb,created_at TIMESTAMPTZ DEFAULT NOW())""")
        cur.execute("""CREATE TABLE IF NOT EXISTS mx_normalized_metrics(
          id BIGSERIAL PRIMARY KEY,snapshot_id UUID REFERENCES mx_snapshots(id) ON DELETE CASCADE,marketplace_key TEXT NOT NULL,
          entity_type TEXT NOT NULL,external_id TEXT NOT NULL,parent_external_id TEXT,name TEXT,status TEXT,currency TEXT,
          product_code TEXT,spend NUMERIC(18,4),revenue NUMERIC(18,4),impressions NUMERIC(18,4),clicks NUMERIC(18,4),
          orders NUMERIC(18,4),daily_budget NUMERIC(18,4),roas NUMERIC(18,6),conversion_rate NUMERIC(18,6),captured_at TIMESTAMPTZ NOT NULL,
          UNIQUE(snapshot_id,entity_type,external_id))""")
        cur.execute("""CREATE TABLE IF NOT EXISTS mx_data_quality_issues(
          id BIGSERIAL PRIMARY KEY,job_id UUID,snapshot_id UUID,record_external_id TEXT,code TEXT,field TEXT,severity TEXT,
          message TEXT,raw_record JSONB,created_at TIMESTAMPTZ DEFAULT NOW(),resolved_at TIMESTAMPTZ,resolved_by TEXT)""")
        cur.execute('CREATE INDEX IF NOT EXISTS mx_metrics_entity_idx ON mx_normalized_metrics(marketplace_key,entity_type,external_id,captured_at DESC)')
        for key in MARKETPLACES:
            cur.execute('INSERT INTO mx_marketplaces(marketplace_key,name) VALUES(%s,%s) ON CONFLICT DO NOTHING',(key,key.title()))
        conn.commit();cur.close()
    finally:conn.close()


def install(app,get_db):
    _init_db(get_db)

    @app.post('/marketplace/ingest')
    def ingest():
        payload=request.get_json(silent=True) or {};marketplace=str(payload.get('marketplace') or '').lower();source=str(payload.get('source_type') or 'api').lower();records=payload.get('records') or []
        if marketplace not in MARKETPLACES:return jsonify({'error':'Desteklenmeyen pazaryeri'}),400
        if source not in ('api','xml','excel','csv','manual'):return jsonify({'error':'Desteklenmeyen kaynak tipi'}),400
        if not isinstance(records,list) or not records:return jsonify({'error':'records listesi zorunlu'}),400
        try:captured=_iso(payload.get('captured_at'))
        except ValueError:return jsonify({'error':'captured_at ISO-8601 olmalı'}),400
        canonical=json.dumps({'marketplace':marketplace,'source':source,'captured_at':captured.isoformat(),'records':records},sort_keys=True,ensure_ascii=False,separators=(',',':'))
        digest=hashlib.sha256(canonical.encode()).hexdigest();job_id=str(uuid.uuid4());snapshot_id=str(uuid.uuid4());conn=get_db()
        if not conn:return jsonify({'error':'Veritabanı bağlantısı yok'}),503
        try:
            cur=conn.cursor();cur.execute('SELECT id FROM mx_snapshots WHERE content_hash=%s',(digest,))
            duplicate=cur.fetchone()
            if duplicate:return jsonify({'error':'Aynı snapshot daha önce işlendi','duplicate':True,'snapshot_id':str(duplicate[0])}),409
            cur.execute('INSERT INTO mx_import_jobs(id,marketplace_key,source_type,status,started_at,actor_email,record_count) VALUES(%s,%s,%s,%s,NOW(),%s,%s)',(job_id,marketplace,source,'processing',session.get('user_email'),len(records)))
            normalized=[];all_issues=[]
            for raw in records:
                row,issues=normalize_record(marketplace,raw);normalized.append(row)
                for issue in issues:all_issues.append((row.get('external_id'),issue,raw))
            errors=sum(1 for _,i,_ in all_issues if i['severity']=='error');quality='rejected' if errors and errors>=len(records) else ('warning' if all_issues else 'success')
            cur.execute('INSERT INTO mx_snapshots(id,job_id,marketplace_key,source_type,captured_at,content_hash,record_count,quality_status,raw_metadata) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)',(snapshot_id,job_id,marketplace,source,captured,digest,len(records),quality,json.dumps(payload.get('metadata') or {})))
            accepted=0
            for row in normalized:
                if any(ext==row['external_id'] and i['severity']=='error' for ext,i,_ in all_issues):continue
                cur.execute("""INSERT INTO mx_normalized_metrics(snapshot_id,marketplace_key,entity_type,external_id,parent_external_id,name,status,currency,product_code,spend,revenue,impressions,clicks,orders,daily_budget,roas,conversion_rate,captured_at)
                 VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",(snapshot_id,marketplace,row['entity_type'],row['external_id'],row['parent_external_id'],row['name'],row['status'],row['currency'],row['product_code'],row['spend'],row['revenue'],row['impressions'],row['clicks'],row['orders'],row['daily_budget'],row['roas'],row['conversion_rate'],captured));accepted+=1
            for ext,issue,raw in all_issues:cur.execute('INSERT INTO mx_data_quality_issues(job_id,snapshot_id,record_external_id,code,field,severity,message,raw_record) VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb)',(job_id,snapshot_id,ext,issue['code'],issue['field'],issue['severity'],issue['message'],json.dumps(raw,ensure_ascii=False)))
            cur.execute('UPDATE mx_import_jobs SET status=%s,finished_at=NOW(),accepted_count=%s,rejected_count=%s WHERE id=%s',(quality,accepted,len(records)-accepted,job_id));conn.commit();cur.close()
            audit=app.extensions.get('mx_audit');
            if audit:audit('marketplace.snapshot_ingested',resource_type='snapshot',resource_id=snapshot_id,new_value={'marketplace':marketplace,'records':len(records),'accepted':accepted,'quality':quality},result='success',status_code=201)
            return jsonify({'ok':True,'job_id':job_id,'snapshot_id':snapshot_id,'quality_status':quality,'record_count':len(records),'accepted_count':accepted,'rejected_count':len(records)-accepted,'issue_count':len(all_issues)}),201
        except Exception as exc:
            conn.rollback();return jsonify({'error':str(exc),'job_id':job_id}),500
        finally:conn.close()

    @app.get('/marketplace/pipeline/status')
    def pipeline_status():
        conn=get_db()
        if not conn:return jsonify({'database':False}),503
        try:
            cur=conn.cursor();cur.execute('SELECT marketplace_key,status,started_at,finished_at,record_count,accepted_count,rejected_count FROM mx_import_jobs ORDER BY started_at DESC LIMIT 20');jobs=[{'marketplace':r[0],'status':r[1],'started_at':r[2].isoformat() if r[2] else None,'finished_at':r[3].isoformat() if r[3] else None,'records':r[4],'accepted':r[5],'rejected':r[6]} for r in cur.fetchall()];cur.close();return jsonify({'database':True,'jobs':jobs})
        finally:conn.close()
