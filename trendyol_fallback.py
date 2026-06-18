import os, json, io
from datetime import datetime

LOG_FILE='madmext_logs.json'

def _read():
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE,'r',encoding='utf-8') as f:return json.load(f)
    except Exception: pass
    return {}

def _write(d):
    with open(LOG_FILE,'w',encoding='utf-8') as f:json.dump(d,f,ensure_ascii=False,indent=2)

def _safe(v): return '' if v is None else str(v).strip()

def _detect(ws):
    h=set([str(c.value).strip() if c.value else '' for c in ws[1]])
    if 'Content Id' in h or 'Model Kodu' in h:return 'urun_detay'
    if 'Reklam Adi' in h and 'Harcama Getirisi' in h and 'TBM Teklifi' in h:return 'urun'
    if 'Reklam Adi' in h and 'Butce Tipi' in h:return 'influencer'
    if 'Reklam Adi' in h and 'Toplam Butce' in h and 'Reklam Cirosu' in h:return 'meta'
    if 'Reklam Adi' in h and 'Harcanan Butce' in h:return 'magaza'
    if ws.max_column>=20:return 'urun'
    return 'unknown'

def _cols(t):
    return {
      'urun':['ad','statu','baslangic','bitis','urun_adedi','content_ids','toplam_butce','gunluk_butce','kalan_butce','harcama','tbm_teklifi','gerceklesen_tbm','tiklanma','goruntulenme','dogrudan_satis','dolayli_satis','toplam_satis','dogrudan_ciro','dolayli_ciro','toplam_ciro','roas'],
      'urun_detay':['kampanya','urun_adi','content_id','model','harcama','goruntulenme','tiklanma','ctr','dogrudan_satis','dolayli_satis','toplam_satis','dogrudan_ciro','dolayli_ciro','toplam_ciro','roas'],
      'magaza':['ad','statu','baslangic','bitis','harcama','goruntulenme','tiklanma','toplam_satis','toplam_ciro','roas'],
      'influencer':['ad','statu','baslangic','bitis','butce_tipi','odeme','ziyaret','satis','ciro','paylasim'],
      'meta':['ad','statu','baslangic','bitis','toplam_butce','harcama','goruntulenme','tiklanma','satis','ciro','roas']
    }.get(t,[])

def _rows(ws,t):
    cols=_cols(t); out=[]
    for row in ws.iter_rows(min_row=2,values_only=True):
        if not row or not row[0]:continue
        vals=list(row)+['']*30
        if t=='urun_detay':vals=[ws.title]+vals
        out.append(dict(zip(cols,[_safe(v) for v in vals[:len(cols)]])))
    return out

def install(app):
    from flask import request,jsonify
    @app.before_request
    def ty_no_db_fallback():
        if os.environ.get('DATABASE_URL'):return None
        if request.path=='/trendyol/data' and request.method=='GET':
            d=(_read().get('trendyol_fallback') or {})
            return jsonify({k:d.get(k,[]) for k in ['urun','magaza','influencer','meta','urun_detay']})
        if request.path=='/trendyol/stats' and request.method=='GET':
            d=(_read().get('trendyol_fallback') or {})
            return jsonify({k:len(d.get(k,[])) for k in ['urun','magaza','influencer','meta','urun_detay']})
        if request.path=='/trendyol/upload' and request.method=='POST':
            f=request.files.get('file')
            if not f:return jsonify({'error':'Dosya bulunamadi','success':False})
            try:
                import openpyxl
                wb=openpyxl.load_workbook(io.BytesIO(f.read()))
                ws=wb.active; t=_detect(ws)
                if t=='unknown':return jsonify({'error':'Taninmayan Trendyol Excel raporu','success':False})
                rows=_rows(ws,t); logs=_read()
                store=logs.setdefault('trendyol_fallback',{'urun':[],'magaza':[],'influencer':[],'meta':[],'urun_detay':[]})
                store.setdefault(t,[]); store[t].extend(rows); store[t]=store[t][-5000:]
                logs.setdefault('actionLog',[]).insert(0,{'type':'trendyol_upload_fallback','tab':t,'count':len(rows),'file':getattr(f,'filename',''),'serverTime':datetime.utcnow().isoformat()})
                logs['actionLog']=logs.get('actionLog',[])[:500]
                _write(logs)
                return jsonify({'success':True,'count':len(rows),'type':t,'tab':'urun' if t=='urun_detay' else t,'fallback':True})
            except Exception as e:return jsonify({'error':str(e),'success':False})
        return None
