"""Database-backed roles and permissions for Madmext Ads."""
import re
from flask import jsonify, request

DEFAULT_PERMISSIONS = {
 'data.read':'Panel ve entegrasyon verilerini okuma','decision.review':'Karar önerilerini inceleme',
 'report.export':'Rapor dışa aktarma',
 'dashboard.view':'Dashboard görüntüleme','ads.view':'Reklam verilerini görüntüleme',
 'ads.write':'Reklam ve bütçe değiştirme','reports.view':'Rapor görüntüleme',
 'reports.export':'Rapor dışa aktarma','marketplace.view':'Pazaryeri görüntüleme',
 'marketplace.write':'Pazaryeri verisi yükleme','design.write':'Tasarım oluşturma',
 'marketing.write':'Kampanya ve pazarlama işlemleri','ai.use':'AI araçlarını kullanma',
 'ai.manage':'AI ajanlarını yönetme','users.manage':'Kullanıcı yönetimi',
 'roles.manage':'Rol ve yetki yönetimi','logs.view':'Log merkezini görüntüleme',
 'integrations.manage':'API ve entegrasyon yönetimi','settings.manage':'Sistem ayarları yönetimi'
}
DEFAULT_ROLES = {
 'super_admin':('Ana Admin',True,list(DEFAULT_PERMISSIONS)),
 'admin':('Admin',True,list(DEFAULT_PERMISSIONS)),
 'editor':('Editör',True,['data.read','decision.review','report.export','dashboard.view','ads.view','ads.write','reports.view','reports.export','marketplace.view','marketplace.write','design.write','marketing.write','ai.use']),
 'viewer':('Görüntüleyici',True,['data.read','dashboard.view','ads.view','reports.view','marketplace.view'])
}

def install(app,get_db):
 def init():
  conn=get_db()
  if not conn:return
  try:
   cur=conn.cursor()
   cur.execute('CREATE TABLE IF NOT EXISTS mx_roles (role_key TEXT PRIMARY KEY,name TEXT NOT NULL,description TEXT,is_system BOOLEAN DEFAULT FALSE,is_active BOOLEAN DEFAULT TRUE,created_at TIMESTAMPTZ DEFAULT NOW())')
   cur.execute('CREATE TABLE IF NOT EXISTS mx_permissions (permission_key TEXT PRIMARY KEY,name TEXT NOT NULL,description TEXT)')
   cur.execute('CREATE TABLE IF NOT EXISTS mx_role_permissions (role_key TEXT REFERENCES mx_roles(role_key) ON DELETE CASCADE,permission_key TEXT REFERENCES mx_permissions(permission_key) ON DELETE CASCADE,PRIMARY KEY(role_key,permission_key))')
   for k,n in DEFAULT_PERMISSIONS.items():cur.execute('INSERT INTO mx_permissions(permission_key,name) VALUES(%s,%s) ON CONFLICT(permission_key) DO UPDATE SET name=EXCLUDED.name',(k,n))
   for k,(n,system,perms) in DEFAULT_ROLES.items():
    cur.execute('INSERT INTO mx_roles(role_key,name,is_system) VALUES(%s,%s,%s) ON CONFLICT(role_key) DO UPDATE SET name=EXCLUDED.name',(k,n,system))
    for p in perms:cur.execute('INSERT INTO mx_role_permissions(role_key,permission_key) VALUES(%s,%s) ON CONFLICT DO NOTHING',(k,p))
   conn.commit();cur.close()
  finally:conn.close()
 init()
 def has_permission(role,permission):
  if role in ('admin','super_admin'):return True
  conn=get_db()
  if not conn:return False
  try:
   cur=conn.cursor();cur.execute('SELECT 1 FROM mx_role_permissions rp JOIN mx_roles r ON r.role_key=rp.role_key WHERE rp.role_key=%s AND rp.permission_key=%s AND r.is_active=TRUE',(role,permission));ok=cur.fetchone() is not None;cur.close();return ok
  finally:conn.close()
 app.extensions['mx_has_permission']=has_permission
 @app.get('/admin/permissions')
 def permissions():
  conn=get_db();cur=conn.cursor();cur.execute('SELECT permission_key,name,description FROM mx_permissions ORDER BY permission_key');rows=[{'key':r[0],'name':r[1],'description':r[2]} for r in cur.fetchall()];cur.close();conn.close();return jsonify(rows)
 @app.route('/admin/roles',methods=['GET','POST'])
 def roles():
  conn=get_db()
  if request.method=='POST':
   d=request.get_json(silent=True) or {};key=(d.get('key') or '').strip().lower();name=(d.get('name') or '').strip()
   if not re.fullmatch(r'[a-z][a-z0-9_-]{1,39}',key) or not name:return jsonify({'error':'Geçerli rol anahtarı ve adı gerekli'}),400
   cur=conn.cursor();cur.execute('INSERT INTO mx_roles(role_key,name,description) VALUES(%s,%s,%s)',(key,name,d.get('description')));conn.commit();cur.close();conn.close();return jsonify({'ok':True}),201
  cur=conn.cursor();cur.execute('SELECT r.role_key,r.name,r.description,r.is_system,r.is_active,COALESCE(array_agg(rp.permission_key) FILTER (WHERE rp.permission_key IS NOT NULL),ARRAY[]::TEXT[]) FROM mx_roles r LEFT JOIN mx_role_permissions rp ON rp.role_key=r.role_key GROUP BY r.role_key ORDER BY r.is_system DESC,r.name');rows=[{'key':x[0],'name':x[1],'description':x[2],'system':x[3],'active':x[4],'permissions':x[5]} for x in cur.fetchall()];cur.close();conn.close();return jsonify(rows)
 @app.put('/admin/roles/<role_key>/permissions')
 def role_permissions(role_key):
  d=request.get_json(silent=True) or {};perms=d.get('permissions') or [];conn=get_db();cur=conn.cursor();cur.execute('DELETE FROM mx_role_permissions WHERE role_key=%s',(role_key,))
  for p in perms:cur.execute('INSERT INTO mx_role_permissions(role_key,permission_key) VALUES(%s,%s) ON CONFLICT DO NOTHING',(role_key,p))
  conn.commit();cur.close();conn.close();return jsonify({'ok':True})
