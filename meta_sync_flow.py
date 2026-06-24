import os
import json
from datetime import datetime

import requests
from flask import request, jsonify

try:
    import psycopg2.extras
except Exception:
    psycopg2 = None


META_FIELDS = {
    'campaigns': ','.join([
        'id', 'name', 'status', 'effective_status', 'objective', 'daily_budget',
        'lifetime_budget', 'start_time', 'stop_time', 'updated_time'
    ]),
    'adsets': ','.join([
        'id', 'name', 'campaign_id', 'status', 'effective_status', 'daily_budget',
        'lifetime_budget', 'billing_event', 'optimization_goal', 'targeting',
        'start_time', 'end_time', 'updated_time'
    ]),
    'ads': ','.join([
        'id', 'name', 'campaign_id', 'adset_id', 'status', 'effective_status',
        'creative{id,name,title,body,object_story_spec,asset_feed_spec,thumbnail_url}',
        'updated_time'
    ]),
    'insights': ','.join([
        'campaign_id', 'campaign_name', 'adset_id', 'adset_name', 'ad_id', 'ad_name',
        'spend', 'impressions', 'reach', 'clicks', 'inline_link_clicks', 'ctr', 'cpc', 'cpm',
        'actions', 'action_values', 'purchase_roas', 'date_start', 'date_stop'
    ])
}


def _token():
    return (os.environ.get('META_ACCESS_TOKEN') or os.environ.get('META_TOKEN') or '').strip()


def _version():
    return (os.environ.get('META_GRAPH_VERSION') or 'v19.0').strip()


def _account_id(value):
    value = str(value or '').strip()
    if not value:
        return ''
    return value if value.startswith('act_') else 'act_' + value


def _json_default(value):
    try:
        if hasattr(value, 'isoformat'):
            return value.isoformat()
    except Exception:
        pass
    return str(value)


def _graph_get(path, params=None):
    token = _token()
    if not token:
        raise RuntimeError('META_ACCESS_TOKEN veya META_TOKEN Railway Variables içinde tanımlı değil.')

    params = dict(params or {})
    params['access_token'] = token
    url = 'https://graph.facebook.com/{0}{1}'.format(_version(), path)
    r = requests.get(url, params=params, timeout=60)
    try:
        data = r.json()
    except Exception:
        raise RuntimeError('Meta API JSON dönmedi: ' + r.text[:300])
    if not r.ok or data.get('error'):
        err = data.get('error') or {}
        raise RuntimeError(err.get('message') or 'Meta API hatası: HTTP {0}'.format(r.status_code))
    return data


def _all_pages(path, params=None, max_pages=20):
    rows = []
    data = _graph_get(path, params)
    page_count = 0
    while True:
        rows.extend(data.get('data') or [])
        page_count += 1
        next_url = (data.get('paging') or {}).get('next')
        if not next_url or page_count >= max_pages:
            break
        r = requests.get(next_url, timeout=60)
        data = r.json()
        if not r.ok or data.get('error'):
            err = data.get('error') or {}
            raise RuntimeError(err.get('message') or 'Meta API sayfalama hatası')
    return rows


def _meta_fetch_all(ad_account_id, date_range=None, date_preset='last_7d'):
    account = _account_id(ad_account_id)
    if not account:
        raise RuntimeError('Meta reklam hesabı bulunamadı.')

    campaigns = _all_pages('/{0}/campaigns'.format(account), {
        'fields': META_FIELDS['campaigns'],
        'limit': 500,
    })
    adsets = _all_pages('/{0}/adsets'.format(account), {
        'fields': META_FIELDS['adsets'],
        'limit': 500,
    })
    ads = _all_pages('/{0}/ads'.format(account), {
        'fields': META_FIELDS['ads'],
        'limit': 500,
    })

    insight_params = {
        'fields': META_FIELDS['insights'],
        'level': 'ad',
        'limit': 500,
        'action_attribution_windows': ['7d_click', '1d_view'],
    }
    if date_range and date_range.get('since') and date_range.get('until'):
        insight_params['time_range'] = json.dumps({
            'since': date_range.get('since'),
            'until': date_range.get('until'),
        })
    else:
        insight_params['date_preset'] = date_preset or 'last_7d'

    insights = _all_pages('/{0}/insights'.format(account), insight_params)
    return campaigns, adsets, ads, insights


def _init_tables(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS meta_campaigns (
            id SERIAL PRIMARY KEY,
            meta_account_id TEXT NOT NULL,
            meta_campaign_id TEXT NOT NULL UNIQUE,
            name TEXT,
            status TEXT,
            effective_status TEXT,
            objective TEXT,
            daily_budget NUMERIC,
            lifetime_budget NUMERIC,
            start_time TEXT,
            stop_time TEXT,
            meta_updated_time TEXT,
            last_synced_at TIMESTAMP DEFAULT NOW(),
            sync_status TEXT DEFAULT 'synced',
            raw_data JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS meta_adsets (
            id SERIAL PRIMARY KEY,
            meta_account_id TEXT NOT NULL,
            meta_adset_id TEXT NOT NULL UNIQUE,
            meta_campaign_id TEXT,
            name TEXT,
            status TEXT,
            effective_status TEXT,
            daily_budget NUMERIC,
            lifetime_budget NUMERIC,
            billing_event TEXT,
            optimization_goal TEXT,
            targeting JSONB DEFAULT '{}'::jsonb,
            start_time TEXT,
            end_time TEXT,
            meta_updated_time TEXT,
            last_synced_at TIMESTAMP DEFAULT NOW(),
            sync_status TEXT DEFAULT 'synced',
            raw_data JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS meta_ads (
            id SERIAL PRIMARY KEY,
            meta_account_id TEXT NOT NULL,
            meta_ad_id TEXT NOT NULL UNIQUE,
            meta_campaign_id TEXT,
            meta_adset_id TEXT,
            name TEXT,
            status TEXT,
            effective_status TEXT,
            creative JSONB DEFAULT '{}'::jsonb,
            meta_updated_time TEXT,
            last_synced_at TIMESTAMP DEFAULT NOW(),
            sync_status TEXT DEFAULT 'synced',
            raw_data JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS meta_ad_insights (
            id SERIAL PRIMARY KEY,
            meta_account_id TEXT NOT NULL,
            meta_campaign_id TEXT,
            meta_adset_id TEXT,
            meta_ad_id TEXT NOT NULL,
            date_start DATE NOT NULL,
            date_stop DATE NOT NULL,
            spend NUMERIC DEFAULT 0,
            impressions NUMERIC DEFAULT 0,
            reach NUMERIC DEFAULT 0,
            clicks NUMERIC DEFAULT 0,
            link_clicks NUMERIC DEFAULT 0,
            ctr NUMERIC DEFAULT 0,
            cpc NUMERIC DEFAULT 0,
            cpm NUMERIC DEFAULT 0,
            purchases NUMERIC DEFAULT 0,
            add_to_cart NUMERIC DEFAULT 0,
            initiate_checkout NUMERIC DEFAULT 0,
            purchase_value NUMERIC DEFAULT 0,
            roas NUMERIC DEFAULT 0,
            raw_data JSONB DEFAULT '{}'::jsonb,
            last_synced_at TIMESTAMP DEFAULT NOW(),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(meta_ad_id, date_start, date_stop)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS meta_sync_logs (
            id SERIAL PRIMARY KEY,
            meta_account_id TEXT NOT NULL,
            sync_type TEXT DEFAULT 'manual_latest_changes',
            status TEXT DEFAULT 'running',
            campaigns_count INTEGER DEFAULT 0,
            adsets_count INTEGER DEFAULT 0,
            ads_count INTEGER DEFAULT 0,
            insights_count INTEGER DEFAULT 0,
            error_message TEXT,
            started_at TIMESTAMP DEFAULT NOW(),
            finished_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()


def _j(value):
    if psycopg2 and hasattr(psycopg2, 'extras'):
        return psycopg2.extras.Json(value or {}, dumps=lambda v: json.dumps(v, ensure_ascii=False, default=_json_default))
    return json.dumps(value or {}, ensure_ascii=False, default=_json_default)


def _num(value):
    try:
        return float(value or 0)
    except Exception:
        return 0


def _action_value(rows, key):
    for item in rows or []:
        if item.get('action_type') == key:
            return _num(item.get('value'))
    return 0


def _roas(rows):
    rows = rows or []
    pick = next((r for r in rows if r.get('action_type') in ('omni_purchase', 'purchase')), None) or (rows[0] if rows else None)
    return _num((pick or {}).get('value'))


def _upsert_db(conn, account, campaigns, adsets, ads, insights):
    _init_tables(conn)
    cur = conn.cursor()

    log_id = None
    cur.execute("INSERT INTO meta_sync_logs(meta_account_id,status) VALUES(%s,'running') RETURNING id", (account,))
    log_id = cur.fetchone()[0]

    for c in campaigns:
        cur.execute("""
            INSERT INTO meta_campaigns(meta_account_id,meta_campaign_id,name,status,effective_status,objective,daily_budget,lifetime_budget,start_time,stop_time,meta_updated_time,last_synced_at,sync_status,raw_data)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),'synced',%s)
            ON CONFLICT(meta_campaign_id) DO UPDATE SET
                name=EXCLUDED.name,status=EXCLUDED.status,effective_status=EXCLUDED.effective_status,objective=EXCLUDED.objective,
                daily_budget=EXCLUDED.daily_budget,lifetime_budget=EXCLUDED.lifetime_budget,start_time=EXCLUDED.start_time,stop_time=EXCLUDED.stop_time,
                meta_updated_time=EXCLUDED.meta_updated_time,last_synced_at=NOW(),sync_status='synced',raw_data=EXCLUDED.raw_data,updated_at=NOW()
        """, (account, c.get('id'), c.get('name'), c.get('status'), c.get('effective_status'), c.get('objective'), _num(c.get('daily_budget')), _num(c.get('lifetime_budget')), c.get('start_time'), c.get('stop_time'), c.get('updated_time'), _j(c)))

    for a in adsets:
        cur.execute("""
            INSERT INTO meta_adsets(meta_account_id,meta_adset_id,meta_campaign_id,name,status,effective_status,daily_budget,lifetime_budget,billing_event,optimization_goal,targeting,start_time,end_time,meta_updated_time,last_synced_at,sync_status,raw_data)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),'synced',%s)
            ON CONFLICT(meta_adset_id) DO UPDATE SET
                meta_campaign_id=EXCLUDED.meta_campaign_id,name=EXCLUDED.name,status=EXCLUDED.status,effective_status=EXCLUDED.effective_status,
                daily_budget=EXCLUDED.daily_budget,lifetime_budget=EXCLUDED.lifetime_budget,billing_event=EXCLUDED.billing_event,optimization_goal=EXCLUDED.optimization_goal,
                targeting=EXCLUDED.targeting,start_time=EXCLUDED.start_time,end_time=EXCLUDED.end_time,meta_updated_time=EXCLUDED.meta_updated_time,
                last_synced_at=NOW(),sync_status='synced',raw_data=EXCLUDED.raw_data,updated_at=NOW()
        """, (account, a.get('id'), a.get('campaign_id'), a.get('name'), a.get('status'), a.get('effective_status'), _num(a.get('daily_budget')), _num(a.get('lifetime_budget')), a.get('billing_event'), a.get('optimization_goal'), _j(a.get('targeting') or {}), a.get('start_time'), a.get('end_time'), a.get('updated_time'), _j(a)))

    for ad in ads:
        cur.execute("""
            INSERT INTO meta_ads(meta_account_id,meta_ad_id,meta_campaign_id,meta_adset_id,name,status,effective_status,creative,meta_updated_time,last_synced_at,sync_status,raw_data)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),'synced',%s)
            ON CONFLICT(meta_ad_id) DO UPDATE SET
                meta_campaign_id=EXCLUDED.meta_campaign_id,meta_adset_id=EXCLUDED.meta_adset_id,name=EXCLUDED.name,status=EXCLUDED.status,
                effective_status=EXCLUDED.effective_status,creative=EXCLUDED.creative,meta_updated_time=EXCLUDED.meta_updated_time,
                last_synced_at=NOW(),sync_status='synced',raw_data=EXCLUDED.raw_data,updated_at=NOW()
        """, (account, ad.get('id'), ad.get('campaign_id'), ad.get('adset_id'), ad.get('name'), ad.get('status'), ad.get('effective_status'), _j(ad.get('creative') or {}), ad.get('updated_time'), _j(ad)))

    for i in insights:
        if not i.get('ad_id') or not i.get('date_start') or not i.get('date_stop'):
            continue
        purchases = _action_value(i.get('actions'), 'purchase') or _action_value(i.get('actions'), 'omni_purchase')
        add_to_cart = _action_value(i.get('actions'), 'add_to_cart') or _action_value(i.get('actions'), 'omni_add_to_cart')
        checkout = _action_value(i.get('actions'), 'initiate_checkout') or _action_value(i.get('actions'), 'omni_initiated_checkout')
        purchase_value = _action_value(i.get('action_values'), 'purchase') or _action_value(i.get('action_values'), 'omni_purchase')
        cur.execute("""
            INSERT INTO meta_ad_insights(meta_account_id,meta_campaign_id,meta_adset_id,meta_ad_id,date_start,date_stop,spend,impressions,reach,clicks,link_clicks,ctr,cpc,cpm,purchases,add_to_cart,initiate_checkout,purchase_value,roas,raw_data,last_synced_at)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
            ON CONFLICT(meta_ad_id,date_start,date_stop) DO UPDATE SET
                spend=EXCLUDED.spend,impressions=EXCLUDED.impressions,reach=EXCLUDED.reach,clicks=EXCLUDED.clicks,link_clicks=EXCLUDED.link_clicks,
                ctr=EXCLUDED.ctr,cpc=EXCLUDED.cpc,cpm=EXCLUDED.cpm,purchases=EXCLUDED.purchases,add_to_cart=EXCLUDED.add_to_cart,
                initiate_checkout=EXCLUDED.initiate_checkout,purchase_value=EXCLUDED.purchase_value,roas=EXCLUDED.roas,raw_data=EXCLUDED.raw_data,last_synced_at=NOW(),updated_at=NOW()
        """, (account, i.get('campaign_id'), i.get('adset_id'), i.get('ad_id'), i.get('date_start'), i.get('date_stop'), _num(i.get('spend')), _num(i.get('impressions')), _num(i.get('reach')), _num(i.get('clicks')), _num(i.get('inline_link_clicks')), _num(i.get('ctr')), _num(i.get('cpc')), _num(i.get('cpm')), purchases, add_to_cart, checkout, purchase_value, _roas(i.get('purchase_roas')), _j(i)))

    campaign_ids = [x.get('id') for x in campaigns if x.get('id')]
    adset_ids = [x.get('id') for x in adsets if x.get('id')]
    ad_ids = [x.get('id') for x in ads if x.get('id')]
    if campaign_ids:
        cur.execute("UPDATE meta_campaigns SET sync_status='archived',updated_at=NOW() WHERE meta_account_id=%s AND NOT(meta_campaign_id = ANY(%s))", (account, campaign_ids))
    if adset_ids:
        cur.execute("UPDATE meta_adsets SET sync_status='archived',updated_at=NOW() WHERE meta_account_id=%s AND NOT(meta_adset_id = ANY(%s))", (account, adset_ids))
    if ad_ids:
        cur.execute("UPDATE meta_ads SET sync_status='archived',updated_at=NOW() WHERE meta_account_id=%s AND NOT(meta_ad_id = ANY(%s))", (account, ad_ids))

    cur.execute("""
        UPDATE meta_sync_logs SET status='success',campaigns_count=%s,adsets_count=%s,ads_count=%s,insights_count=%s,finished_at=NOW(),updated_at=NOW()
        WHERE id=%s
    """, (len(campaigns), len(adsets), len(ads), len(insights), log_id))
    conn.commit()
    cur.close()


def _fallback_log(read_logs, write_logs, account, campaigns, adsets, ads, insights):
    data = read_logs()
    data['metaLatestSync'] = {
        'account': account,
        'updatedAt': datetime.utcnow().isoformat(),
        'campaigns': len(campaigns),
        'adsets': len(adsets),
        'ads': len(ads),
        'insights': len(insights),
    }
    data.setdefault('actionLog', []).insert(0, {
        'type': 'meta_latest_sync',
        'detail': 'Meta son değişiklikleri çekildi',
        'serverTime': datetime.utcnow().isoformat(),
        'summary': data['metaLatestSync'],
    })
    data['actionLog'] = data['actionLog'][:500]
    write_logs(data)


def _inject_meta_module(html):
    if 'id="mxMetaSyncBtn"' in html:
        return html

    css = """
.mx-sync-wrap{display:inline-flex;align-items:center;gap:8px;flex-wrap:wrap}
.mx-sync-last{font-size:11px;color:var(--m);font-family:'DM Mono',monospace}
.mx-sync-btn{display:inline-flex;align-items:center;gap:6px;background:var(--s2);border:1px solid var(--b2);color:var(--t);padding:5px 10px;font-family:'DM Mono',monospace;font-size:11px;border-radius:5px;cursor:pointer;transition:all .15s}
.mx-sync-btn:hover{border-color:var(--a);color:#fff;background:#202d44}.mx-sync-btn:disabled{opacity:.55;cursor:not-allowed}.mx-sync-spin{display:inline-block;transition:transform .2s}.mx-sync-btn.loading .mx-sync-spin{animation:mxSpin 1s linear infinite}@keyframes mxSpin{to{transform:rotate(360deg)}}
"""
    if '</style>' in html:
        html = html.replace('</style>', css + '\n</style>', 1)

    button = """
  <div class="ma-sep"></div>
  <div class="mx-sync-wrap">
    <span class="mx-sync-last" id="mxMetaSyncLast">Güncelleme: henüz yapılmadı</span>
    <button class="mx-sync-btn" id="mxMetaSyncBtn" onclick="mxMetaSyncLatestChanges()"><span class="mx-sync-spin">↻</span><span>Meta’daki Son Değişiklikleri Al</span></button>
  </div>
"""
    if '<span id="mStatus"' in html:
        html = html.replace('<span id="mStatus"', button + '  <span id="mStatus"', 1)
    elif '</div>\n\n<!-- Hidden inputs' in html:
        html = html.replace('</div>\n\n<!-- Hidden inputs', button + '</div>\n\n<!-- Hidden inputs', 1)

    script = r"""
<script>
(function(){
  function metaDatePayload(){
    var preset=(document.getElementById('mPreset')||{}).value||'last_7d';
    var from=(document.getElementById('mFrom')||{}).value||'';
    var to=(document.getElementById('mTo')||{}).value||'';
    var payload={adAccountId:(typeof AID!=='undefined'?AID:''),datePreset:preset};
    if(preset==='custom'&&from&&to){payload.dateRange={since:from,until:to};}
    return payload;
  }
  function setMsg(txt){var el=document.getElementById('mxMetaSyncLast');if(el)el.textContent=txt;}
  window.mxMetaSyncLatestChanges=async function(){
    var btn=document.getElementById('mxMetaSyncBtn');
    if(btn&&btn.disabled)return;
    try{
      if(btn){btn.disabled=true;btn.classList.add('loading');}
      setMsg('Güncelleme: Meta verileri alınıyor...');
      var base=(typeof px==='function'?px():'');
      var r=await fetch(base+'/api/meta/sync-latest',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify(metaDatePayload())});
      var d=await r.json();
      if(!r.ok||!d.success)throw new Error((d&&d.message)||'Meta güncelleme başarısız');
      var s=d.summary||{};
      setMsg('Güncelleme: az önce — '+(s.campaignsUpdated||0)+' kampanya, '+(s.adsetsUpdated||0)+' set, '+(s.adsUpdated||0)+' reklam');
      if(typeof toast==='function')toast('Meta’daki son değişiklikler Madmext Ads’e uygulandı');
      if(typeof mLoad==='function')setTimeout(mLoad,250);
    }catch(e){
      setMsg('Güncelleme başarısız');
      if(typeof toast==='function')toast('Meta güncelleme hatası: '+e.message);
    }finally{
      if(btn){setTimeout(function(){btn.disabled=false;btn.classList.remove('loading');},1500);}
    }
  };
})();
</script>
"""
    if '</script>' in html:
        html = html + '\n' + script
    return html


def install(app, get_db=None, read_logs=None, write_logs=None):
    @app.route('/api/meta/sync-latest', methods=['POST'])
    def meta_sync_latest():
        try:
            payload = request.get_json(silent=True) or {}
            account = _account_id(payload.get('adAccountId'))
            if not account:
                return jsonify({'success': False, 'message': 'Meta reklam hesabı seçilmedi.'}), 400

            campaigns, adsets, ads, insights = _meta_fetch_all(
                account,
                date_range=payload.get('dateRange'),
                date_preset=payload.get('datePreset') or 'last_7d'
            )

            conn = get_db() if callable(get_db) else None
            if conn:
                try:
                    _upsert_db(conn, account, campaigns, adsets, ads, insights)
                    conn.close()
                except Exception:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    raise
            elif callable(read_logs) and callable(write_logs):
                _fallback_log(read_logs, write_logs, account, campaigns, adsets, ads, insights)

            return jsonify({
                'success': True,
                'message': 'Meta’daki son değişiklikler Madmext Ads’e uygulandı.',
                'updatedAt': datetime.utcnow().isoformat(),
                'summary': {
                    'campaignsUpdated': len(campaigns),
                    'adsetsUpdated': len(adsets),
                    'adsUpdated': len(ads),
                    'insightsUpdated': len(insights),
                }
            })
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.after_request
    def meta_sync_injector(response):
        try:
            if request.path.rstrip('/') != '/modules/meta-ads.html':
                return response
            ctype = response.headers.get('Content-Type', '')
            if 'text/html' not in ctype and 'text/plain' not in ctype:
                return response
            response.direct_passthrough = False
            html = response.get_data(as_text=True)
            new_html = _inject_meta_module(html)
            if new_html != html:
                response.set_data(new_html)
                response.headers['Content-Length'] = str(len(new_html.encode(response.charset or 'utf-8')))
        except Exception as e:
            print('meta sync injector:', e)
        return response
