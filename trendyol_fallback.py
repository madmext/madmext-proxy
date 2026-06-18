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
def _slug(v):
    s=_safe(v).lower().replace('ı','i').replace('ğ','g').replace('ü','u').replace('ş','s').replace('ö','o').replace('ç','c')
    return ' '.join(s.split())
def _norm(v): return _slug(v)
def _day(v): return _safe(v)[:10]
def _num(v):
    try:
        s=_safe(v).replace('₺','').replace('+ KDV','').replace('KDV','').strip()
        return float(s.replace('.','').replace(',','.'))
    except Exception:return 0

def _score(r):
    return _num(r.get('harcama'))+_num(r.get('toplam_ciro') or r.get('ciro'))+_num(r.get('toplam_satis') or r.get('satis'))+_num(r.get('tiklanma'))+_num(r.get('ziyaret'))+_num(r.get('goruntulenme'))+_num(r.get('roas'))

def _key(t,r):
    if t=='urun_detay': return _norm(r.get('kampanya'))+'|'+_norm(r.get('content_id') or r.get('model') or r.get('urun_adi'))
    return _norm(r.get('ad'))+'|'+_day(r.get('baslangic'))

def _dedupe(t,rows):
    m={}
    for r in rows or []:
        k=_key(t,r)
        if not k or k=='|': continue
        old=m.get(k)
        if old is None:m[k]=r
        elif _score(r)>=_score(old):
            n=dict(old); n.update(r); m[k]=n
    return list(m.values())

def _headers(ws):
    return [_safe(c.value) for c in ws[1]]
def _hset(ws):
    return set(_slug(x) for x in _headers(ws))
def _idx(headers, names):
    sl=[_slug(h) for h in headers]
    for n in names:
        if _slug(n) in sl:return sl.index(_slug(n))
    return -1

def _detect(ws):
    h=_hset(ws)
    if ('kullanici ismi' in h or 'kullanıcı ismi' in h) and 'urun' in h and 'tarih' in h:
        return 'influencer_detail'
    if 'reklam adi' in h and ('reklam statusu' in h or 'reklam statüsü' in h) and ('link ziyareti' in h or 'satis adedi' in h):
        return 'influencer'
    if 'content id' in h or 'model kodu' in h:return 'urun_detay'
    if 'reklam adi' in h and 'harcama getirisi' in h and 'tbm teklifi' in h:return 'urun'
    if 'reklam adi' in h and 'butce tipi' in h:return 'influencer'
    if 'reklam adi' in h and 'toplam butce' in h and 'reklam cirosu' in h:return 'meta'
    if 'reklam adi' in h and 'harcanan butce' in h:return 'magaza'
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
    if t=='influencer':
        headers=_headers(ws); out=[]
        ix_ad=_idx(headers,['Reklam Adı','Reklam Adi'])
        ix_st=_idx(headers,['Reklam Statüsü','Reklam Statusu','Reklam Statu'])
        ix_ba=_idx(headers,['Başlangıç Tarihi','Baslangic Tarihi'])
        ix_bi=_idx(headers,['Bitiş Tarihi','Bitis Tarihi'])
        ix_od=_idx(headers,['Ödenecek Tutar','Odenecek Tutar'])
        ix_ko=_idx(headers,['Komisyon'])
        ix_bo=_idx(headers,['Bonus'])
        ix_zi=_idx(headers,['Link Ziyareti'])
        ix_sa=_idx(headers,['Satış Adedi','Satis Adedi'])
        ix_ci=_idx(headers,['Reklam Cirosu','Ciro'])
        ix_pa=_idx(headers,['Paylaşım Sayısı','Paylasim Sayisi'])
        for row in ws.iter_rows(min_row=2,values_only=True):
            if not row or (ix_ad>=0 and not row[ix_ad]):continue
            out.append({
                'ad':_safe(row[ix_ad]) if ix_ad>=0 else '',
                'statu':_safe(row[ix_st]) if ix_st>=0 else '',
                'baslangic':_safe(row[ix_ba]) if ix_ba>=0 else '',
                'bitis':_safe(row[ix_bi]) if ix_bi>=0 else '',
                'butce_tipi':_safe(row[ix_bo]) if ix_bo>=0 else '',
                'odeme':_safe(row[ix_od]) if ix_od>=0 else (_safe(row[ix_ko]) if ix_ko>=0 else ''),
                'ziyaret':_safe(row[ix_zi]) if ix_zi>=0 else '',
                'satis':_safe(row[ix_sa]) if ix_sa>=0 else '',
                'ciro':_safe(row[ix_ci]) if ix_ci>=0 else '',
                'paylasim':_safe(row[ix_pa]) if ix_pa>=0 else ''
            })
        return out
    if t=='influencer_detail':
        headers=_headers(ws); agg={}
        ix_u=_idx(headers,['Kullanıcı İsmi','Kullanici Ismi'])
        ix_t=_idx(headers,['Tarih'])
        ix_c=_idx(headers,['Ciro'])
        ix_s=_idx(headers,['Satış Adedi','Satis Adedi'])
        ix_z=_idx(headers,['Link Ziyareti',"Influencer'ın Tarih'te getirdiği Link Ziyareti"])
        for row in ws.iter_rows(min_row=2,values_only=True):
            if not row or ix_u<0 or ix_t<0 or not row[ix_u]:continue
            ad=_safe(row[ix_u]); tarih=_safe(row[ix_t]); k=_norm(ad)+'|'+_day(tarih)
            cur=agg.setdefault(k,{'ad':ad,'statu':'Urun/Tarih Raporu','baslangic':tarih,'bitis':tarih,'butce_tipi':'Influencer Urun Bazli','odeme':'','ziyaret':'0','satis':'0','ciro':'0','paylasim':''})
            cur['ciro']=str(_num(cur.get('ciro'))+(_num(row[ix_c]) if ix_c>=0 else 0))
            cur['satis']=str(_num(cur.get('satis'))+(_num(row[ix_s]) if ix_s>=0 else 0))
            cur['ziyaret']=str(max(_num(cur.get('ziyaret')),_num(row[ix_z]) if ix_z>=0 else 0))
        return list(agg.values())
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
        keys=['urun','magaza','influencer','meta','urun_detay']
        if request.path=='/trendyol/data' and request.method=='GET':
            logs=_read(); d=(logs.get('trendyol_fallback') or {})
            cleaned={k:_dedupe(k,d.get(k,[])) for k in keys}
            if cleaned!=d:
                logs['trendyol_fallback']=cleaned; _write(logs)
            return jsonify(cleaned)
        if request.path=='/trendyol/stats' and request.method=='GET':
            d=(_read().get('trendyol_fallback') or {})
            return jsonify({k:len(_dedupe(k,d.get(k,[]))) for k in keys})
        if request.path=='/trendyol/upload' and request.method=='POST':
            f=request.files.get('file')
            if not f:return jsonify({'error':'Dosya bulunamadi','success':False})
            try:
                import openpyxl
                wb=openpyxl.load_workbook(io.BytesIO(f.read()))
                ws=wb.active; t=_detect(ws)
                if t=='unknown':return jsonify({'error':'Taninmayan Trendyol Excel raporu','success':False})
                rows=_rows(ws,t)
                store_key='influencer' if t=='influencer_detail' else t
                logs=_read(); store=logs.setdefault('trendyol_fallback',{'urun':[],'magaza':[],'influencer':[],'meta':[],'urun_detay':[]})
                store.setdefault(store_key,[])
                before=len(_dedupe(store_key,store[store_key]))
                store[store_key]=_dedupe(store_key,store[store_key]+rows)[-5000:]
                after=len(store[store_key])
                logs.setdefault('actionLog',[]).insert(0,{'type':'trendyol_upload_fallback','tab':store_key,'detected':t,'incoming':len(rows),'before':before,'after':after,'file':getattr(f,'filename',''),'serverTime':datetime.utcnow().isoformat()})
                logs['actionLog']=logs.get('actionLog',[])[:500]
                _write(logs)
                return jsonify({'success':True,'count':len(rows),'unique_count':after,'before_count':before,'type':'Influencer Reklamlari' if store_key=='influencer' else store_key,'tab':store_key,'fallback':True})
            except Exception as e:return jsonify({'error':str(e),'success':False})
        return None
