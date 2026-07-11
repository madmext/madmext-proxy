"""Manual budgets, daily decisions and human approval workflow."""
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from flask import jsonify, request, session


def _decimal(v):
    try:return Decimal(str(v))
    except (InvalidOperation,ValueError,TypeError):return None


def _init_db(get_db):
    conn=get_db()
    if not conn:return
    try:
        cur=conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS mx_manual_budgets(
          id BIGSERIAL PRIMARY KEY,marketplace_key TEXT NOT NULL,entity_type TEXT NOT NULL,external_id TEXT NOT NULL,
          amount NUMERIC(18,4) NOT NULL CHECK(amount>0),currency TEXT DEFAULT 'TRY',valid_from DATE NOT NULL,valid_to DATE,
          reason TEXT,created_by TEXT,created_at TIMESTAMPTZ DEFAULT NOW(),is_active BOOLEAN DEFAULT TRUE)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS mx_budget_history(
          id BIGSERIAL PRIMARY KEY,budget_id BIGINT,marketplace_key TEXT,entity_type TEXT,external_id TEXT,
          old_amount NUMERIC(18,4),new_amount NUMERIC(18,4),change_percent NUMERIC(10,4),reason TEXT,
          changed_by TEXT,changed_at TIMESTAMPTZ DEFAULT NOW())""")
        cur.execute("""CREATE TABLE IF NOT EXISTS mx_decisions(
          id BIGSERIAL PRIMARY KEY,decision_date DATE NOT NULL,marketplace_key TEXT NOT NULL,entity_type TEXT NOT NULL,
          external_id TEXT NOT NULL,entity_name TEXT,current_budget NUMERIC(18,4),recommended_budget NUMERIC(18,4),
          recommended_change_percent NUMERIC(10,4),decision_type TEXT NOT NULL,reason TEXT NOT NULL,priority TEXT,
          risk_level TEXT,data_snapshot_id UUID,status TEXT DEFAULT 'proposed',created_at TIMESTAMPTZ DEFAULT NOW(),
          created_by TEXT DEFAULT 'decision_engine',reviewed_by TEXT,reviewed_at TIMESTAMPTZ,rejection_reason TEXT,
          approved_budget NUMERIC(18,4),application_status TEXT,applied_at TIMESTAMPTZ,
          UNIQUE(decision_date,marketplace_key,entity_type,external_id))""")
        cur.execute("""CREATE TABLE IF NOT EXISTS mx_decision_events(
          id BIGSERIAL PRIMARY KEY,decision_id BIGINT REFERENCES mx_decisions(id) ON DELETE CASCADE,event_type TEXT NOT NULL,
          actor_email TEXT,old_status TEXT,new_status TEXT,details JSONB DEFAULT '{}'::jsonb,created_at TIMESTAMPTZ DEFAULT NOW())""")
        cur.execute('CREATE INDEX IF NOT EXISTS mx_budget_active_idx ON mx_manual_budgets(marketplace_key,entity_type,external_id,valid_from DESC)')
        cur.execute('CREATE INDEX IF NOT EXISTS mx_decision_queue_idx ON mx_decisions(status,decision_date DESC,risk_level)')
        conn.commit();cur.close()
    finally:conn.close()


def install(app,get_db):
    _init_db(get_db)

    @app.route('/marketplace/budgets',methods=['GET','POST'])
    def budgets():
        conn=get_db()
        if not conn:return jsonify({'error':'Veritabanı bağlantısı yok'}),503
        try:
            cur=conn.cursor()
            if request.method=='GET':
                marketplace=request.args.get('marketplace');params=[];where='WHERE is_active=TRUE'
                if marketplace:where+=' AND marketplace_key=%s';params.append(marketplace)
                cur.execute('SELECT id,marketplace_key,entity_type,external_id,amount,currency,valid_from,valid_to,reason,created_by,created_at FROM mx_manual_budgets '+where+' ORDER BY created_at DESC LIMIT 1000',params)
                rows=[{'id':r[0],'marketplace':r[1],'entity_type':r[2],'external_id':r[3],'amount':float(r[4]),'currency':r[5],'valid_from':r[6].isoformat(),'valid_to':r[7].isoformat() if r[7] else None,'reason':r[8],'created_by':r[9],'created_at':r[10].isoformat()} for r in cur.fetchall()];cur.close();return jsonify(rows)
            d=request.get_json(silent=True) or {};amount=_decimal(d.get('amount'));marketplace=str(d.get('marketplace') or '').lower();entity_type=str(d.get('entity_type') or '').lower();external_id=str(d.get('external_id') or '').strip();valid_from=d.get('valid_from') or date.today().isoformat()
            if not marketplace or not entity_type or not external_id or amount is None or amount<=0:return jsonify({'error':'Pazaryeri, kayıt, pozitif bütçe ve tarih zorunlu'}),400
            cur.execute("""SELECT id,amount FROM mx_manual_budgets WHERE marketplace_key=%s AND entity_type=%s AND external_id=%s AND is_active=TRUE AND valid_from<=%s AND (valid_to IS NULL OR valid_to>=%s) ORDER BY valid_from DESC LIMIT 1""",(marketplace,entity_type,external_id,valid_from,valid_from));old=cur.fetchone()
            if old:cur.execute('UPDATE mx_manual_budgets SET is_active=FALSE,valid_to=(%s::date-1) WHERE id=%s',(valid_from,old[0]))
            cur.execute("""INSERT INTO mx_manual_budgets(marketplace_key,entity_type,external_id,amount,currency,valid_from,valid_to,reason,created_by) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",(marketplace,entity_type,external_id,amount,d.get('currency','TRY'),valid_from,d.get('valid_to'),d.get('reason'),session.get('user_email')));budget_id=cur.fetchone()[0]
            old_amount=old[1] if old else None;pct=((amount-old_amount)/old_amount*100) if old_amount else None
            cur.execute('INSERT INTO mx_budget_history(budget_id,marketplace_key,entity_type,external_id,old_amount,new_amount,change_percent,reason,changed_by) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',(budget_id,marketplace,entity_type,external_id,old_amount,amount,pct,d.get('reason'),session.get('user_email')));conn.commit();cur.close()
            audit=app.extensions.get('mx_audit');
            if audit:audit('budget.manual_set',resource_type=entity_type,resource_id=external_id,old_value={'amount':float(old_amount)} if old_amount else None,new_value={'amount':float(amount),'valid_from':valid_from},reason=d.get('reason'),result='success',status_code=201)
            return jsonify({'ok':True,'budget_id':budget_id,'old_amount':float(old_amount) if old_amount else None,'new_amount':float(amount),'change_percent':float(pct) if pct is not None else None}),201
        finally:conn.close()

    @app.post('/marketplace/decisions/generate')
    def generate_decisions():
        d=request.get_json(silent=True) or {};marketplace=d.get('marketplace');target_roas=_decimal(d.get('target_roas') or 3);minimum_spend=_decimal(d.get('minimum_spend') or 100);today=date.today();conn=get_db()
        if not conn:return jsonify({'error':'Veritabanı bağlantısı yok'}),503
        try:
            cur=conn.cursor();params=[];market_filter=''
            if marketplace:market_filter='AND m.marketplace_key=%s';params.append(marketplace)
            cur.execute("""SELECT DISTINCT ON(m.marketplace_key,m.entity_type,m.external_id)
              m.marketplace_key,m.entity_type,m.external_id,m.name,m.spend,m.revenue,m.orders,m.clicks,m.roas,m.captured_at,m.snapshot_id,
              b.amount FROM mx_normalized_metrics m JOIN mx_snapshots s ON s.id=m.snapshot_id
              LEFT JOIN LATERAL(SELECT amount FROM mx_manual_budgets b WHERE b.marketplace_key=m.marketplace_key AND b.entity_type=m.entity_type AND b.external_id=m.external_id AND b.is_active=TRUE AND b.valid_from<=CURRENT_DATE AND(b.valid_to IS NULL OR b.valid_to>=CURRENT_DATE) ORDER BY b.valid_from DESC LIMIT 1)b ON TRUE
              WHERE s.quality_status IN('success','warning') """+market_filter+" ORDER BY m.marketplace_key,m.entity_type,m.external_id,m.captured_at DESC",params)
            created=[]
            for r in cur.fetchall():
                market,etype,eid,name,spend,revenue,orders,clicks,roas,captured,snapshot,budget=r;decision='keep';reason='Performans hedef aralığında';risk='low';priority='normal';recommended=budget;pct=Decimal('0')
                if budget is None:decision='define_budget';reason='Aktif manuel günlük bütçe bulunamadı';risk='high';priority='high';recommended=None
                elif spend<minimum_spend:decision='insufficient_data';reason='Karar için minimum harcama eşiği oluşmadı';risk='low'
                elif orders==0 and spend>=minimum_spend:decision='decrease';pct=Decimal('-5');recommended=budget*Decimal('.95');reason='Harcama var ancak sipariş yok';risk='critical';priority='critical'
                elif roas>=target_roas and spend/budget>=Decimal('.80'):decision='increase';pct=Decimal('5');recommended=budget*Decimal('1.05');reason='ROAS hedef üstünde ve bütçe kullanımı yüksek';risk='low';priority='high'
                elif roas<target_roas:decision='decrease';pct=Decimal('-5');recommended=budget*Decimal('.95');reason='ROAS hedefin altında';risk='high';priority='high'
                cur.execute("""INSERT INTO mx_decisions(decision_date,marketplace_key,entity_type,external_id,entity_name,current_budget,recommended_budget,recommended_change_percent,decision_type,reason,priority,risk_level,data_snapshot_id,created_by)
                  VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'decision_engine') ON CONFLICT(decision_date,marketplace_key,entity_type,external_id) DO UPDATE SET current_budget=EXCLUDED.current_budget,recommended_budget=EXCLUDED.recommended_budget,recommended_change_percent=EXCLUDED.recommended_change_percent,decision_type=EXCLUDED.decision_type,reason=EXCLUDED.reason,priority=EXCLUDED.priority,risk_level=EXCLUDED.risk_level,data_snapshot_id=EXCLUDED.data_snapshot_id RETURNING id""",(today,market,etype,eid,name,budget,recommended,pct,decision,reason,priority,risk,snapshot));created.append(cur.fetchone()[0])
            conn.commit();cur.close();return jsonify({'ok':True,'decision_date':today.isoformat(),'count':len(created),'decision_ids':created})
        finally:conn.close()

    @app.route('/marketplace/decisions',methods=['GET'])
    def list_decisions():
        conn=get_db();cur=conn.cursor();cur.execute('SELECT id,decision_date,marketplace_key,entity_type,external_id,entity_name,current_budget,recommended_budget,recommended_change_percent,decision_type,reason,priority,risk_level,status,reviewed_by,approved_budget,application_status FROM mx_decisions ORDER BY decision_date DESC,CASE risk_level WHEN \'critical\' THEN 1 WHEN \'high\' THEN 2 ELSE 3 END,id DESC LIMIT 1000');cols=['id','date','marketplace','entity_type','external_id','name','current_budget','recommended_budget','change_percent','decision','reason','priority','risk','status','reviewed_by','approved_budget','application_status'];rows=[]
        for r in cur.fetchall():
            x=dict(zip(cols,r));x['date']=x['date'].isoformat()
            for k in ('current_budget','recommended_budget','change_percent','approved_budget'):
                if x[k] is not None:x[k]=float(x[k])
            rows.append(x)
        cur.close();conn.close();return jsonify(rows)

    @app.post('/marketplace/decisions/<int:decision_id>/review')
    def review_decision(decision_id):
        d=request.get_json(silent=True) or {};action=d.get('action');conn=get_db();cur=conn.cursor();cur.execute('SELECT status,current_budget,recommended_budget FROM mx_decisions WHERE id=%s FOR UPDATE',(decision_id,));row=cur.fetchone()
        if not row:cur.close();conn.close();return jsonify({'error':'Karar bulunamadı'}),404
        if row[0] not in ('proposed','deferred'):cur.close();conn.close();return jsonify({'error':'Karar daha önce işlendi'}),409
        if action not in ('approve','reject','defer','manual_review'):cur.close();conn.close();return jsonify({'error':'Geçersiz işlem'}),400
        approved=_decimal(d.get('approved_budget')) if d.get('approved_budget') is not None else row[2]
        if action=='approve' and row[1] and approved:
            pct=abs((approved-row[1])/row[1]*100)
            if pct>Decimal('5.0001'):cur.close();conn.close();return jsonify({'error':'Günlük bütçe değişimi yüzde 5 sınırını aşamaz','calculated_percent':float(pct)}),422
        new_status={'approve':'approved','reject':'rejected','defer':'deferred','manual_review':'manual_review'}[action]
        if action=='reject' and not d.get('reason'):cur.close();conn.close();return jsonify({'error':'Reddetme nedeni zorunlu'}),400
        cur.execute('UPDATE mx_decisions SET status=%s,reviewed_by=%s,reviewed_at=NOW(),rejection_reason=%s,approved_budget=%s,application_status=%s WHERE id=%s',(new_status,session.get('user_email'),d.get('reason'),approved,'queued' if action=='approve' else None,decision_id));cur.execute('INSERT INTO mx_decision_events(decision_id,event_type,actor_email,old_status,new_status,details) VALUES(%s,%s,%s,%s,%s,%s::jsonb)',(decision_id,'review',session.get('user_email'),row[0],new_status,json.dumps({'reason':d.get('reason'),'approved_budget':float(approved) if approved else None})));conn.commit();cur.close();conn.close();return jsonify({'ok':True,'status':new_status,'application_status':'queued' if action=='approve' else None})
