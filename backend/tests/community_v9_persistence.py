"""Verify V9 community records survive a backend container restart."""
from __future__ import annotations
import json, os, subprocess, sys, time, uuid
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE=os.getenv("OPENRESEARCH_URL","http://127.0.0.1:8000").rstrip("/")
ROOT=__import__('pathlib').Path(__file__).resolve().parents[2]
def api(path,method="GET",payload=None,token=None):
    body=json.dumps(payload).encode() if payload is not None else None; headers={"Content-Type":"application/json"} if payload is not None else {}
    if token: headers["Authorization"]="Bearer "+token
    try:
        with urlopen(Request(BASE+path,data=body,headers=headers,method=method),timeout=25) as r: return r.status,json.loads(r.read().decode() or "{}")
    except HTTPError as e: return e.code,json.loads(e.read().decode() or "{}")
def expect(actual,expected,body): assert actual==expected,(actual,body)
def wait_ready():
    until=time.monotonic()+45
    while time.monotonic()<until:
        try:
            c,b=api('/api/health')
            if c==200 and b.get('status')=='ok': return
        except Exception: pass
        time.sleep(1)
    raise RuntimeError('backend did not recover')
def run():
    suffix=uuid.uuid4().hex[:8]; pw='OpenResearch-V9!'; names=[f'v9persist{x}_{suffix}' for x in 'ab']; tokens=[]; rid=did=iid=None
    try:
        for name in names:
            c,b=api('/api/auth/register','POST',{"username":name,"display_name":name,"email":name+'@openresearchhub.com',"password":pw,"confirm_password":pw}); expect(c,201,b)
            c,b=api('/api/auth/login','POST',{"identifier":name,"password":pw}); expect(c,200,b); tokens.append(b['access_token'])
        ta,tb=tokens
        c,admin_login=api('/api/auth/login','POST',{'identifier':'kai-shen','password':'openresearch'});expect(c,200,admin_login);admin_token=admin_login['access_token']
        c,b=api('/api/resources','POST',{"title":"V9 Persistence "+suffix,"type":"PROJECT","description":"Restart check"},ta); expect(c,201,b); rid=b['id']
        c,approved=api(f'/api/admin/resources/{rid}/status','PATCH',{'status':'PUBLISHED'},admin_token);expect(c,200,approved)
        c,b=api(f'/api/resources/{rid}/discussions','POST',{"title":"Persistence discussion","content":"This must survive restart."},tb); expect(c,201,b); did=b['id']
        c,b=api(f'/api/resources/{rid}/issues','POST',{"title":"Persistence issue","description":"This must survive restart.","issue_type":"OTHER"},tb); expect(c,201,b); iid=b['id']
        c,b=api(f'/api/users/{names[0]}/follow','POST',{},tb); expect(c,200,b)
        c,b=api('/api/notifications',token=ta); expect(c,200,b); assert b['unread_count']>=1
        subprocess.run(['docker','compose','restart','backend'],cwd=ROOT,check=True,timeout=60); wait_ready()
        c,b=api(f'/api/discussions/{did}'); expect(c,200,b); assert b['title']=='Persistence discussion'
        c,b=api(f'/api/issues/{iid}'); expect(c,200,b); assert b['title']=='Persistence issue'
        c,b=api(f'/api/users/{names[0]}/followers'); expect(c,200,b); assert b['total']==1
        c,b=api('/api/notifications',token=ta); expect(c,200,b); assert b['unread_count']>=1
        print('V9 Docker restart persistence check passed.')
    finally:
        if rid and tokens: api('/api/resources/'+str(rid),'DELETE',token=tokens[0])
if __name__=='__main__':
    try: run()
    except Exception as exc: print('V9 persistence check failed:',exc,file=sys.stderr); raise
