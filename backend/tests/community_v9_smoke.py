"""Live acceptance checks for V9 Community & Collaboration."""
from __future__ import annotations
import json, os, sys, uuid
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE=os.getenv("OPENRESEARCH_URL","http://127.0.0.1:8000").rstrip("/")
def api(path,method="GET",payload=None,token=None):
    body=json.dumps(payload).encode() if payload is not None else None; headers={"Content-Type":"application/json"} if payload is not None else {}
    if token: headers["Authorization"]="Bearer "+token
    try:
        with urlopen(Request(BASE+path,data=body,headers=headers,method=method),timeout=25) as r: return r.status,json.loads(r.read().decode() or "{}")
    except HTTPError as e: return e.code,json.loads(e.read().decode() or "{}")
def ok(actual,expected,body): assert actual==expected,(actual,body)
def register(name,password):
    c,b=api('/api/auth/register','POST',{"username":name,"display_name":name,"email":name+'@openresearchhub.com',"password":password,"confirm_password":password});ok(c,201,b)
    c,b=api('/api/auth/login','POST',{"identifier":name,"password":password});ok(c,200,b);return b['access_token']
def run():
    x=uuid.uuid4().hex[:7]; pw='OpenResearch-V9!'; a,b,c=[f'v9{z}_{x}' for z in 'abc']; ta,tb,tc=map(lambda n:register(n,pw),(a,b,c)); rid=None
    code, admin_login = api('/api/auth/login','POST',{'identifier':'kai-shen','password':'openresearch'});ok(code,200,admin_login);admin_token=admin_login['access_token']
    try:
        code,res=api('/api/resources','POST',{"title":"V9 Community Test "+x,"type":"PROJECT","description":"V9 test resource"},ta);ok(code,201,res);rid=res['id']
        code,approved=api(f'/api/admin/resources/{rid}/status','PATCH',{'status':'PUBLISHED'},admin_token);ok(code,200,approved);assert approved['review_status']=='PUBLISHED'
        code,d=api(f'/api/resources/{rid}/discussions','POST',{"title":"How to reproduce this project?","content":"Please share the environment details."},tb);ok(code,201,d);did=d['id']
        code,_=api(f'/api/resources/{rid}/discussions','POST',{"title":"How to reproduce this project?","content":"x"});ok(code,401,_)
        code,items=api(f'/api/resources/{rid}/discussions');ok(code,200,items);assert items['total']==1
        code,comment=api(f'/api/discussions/{did}/comments','POST',{"content":"Use the provided environment file."},tc);ok(code,201,comment)
        code,_=api('/api/comments/'+str(comment['id']),'PATCH',{"content":"no"},tb);ok(code,403,_)
        code,_=api(f'/api/discussions/{did}/pin','POST',{},ta);ok(code,200,_)
        code,_=api(f'/api/discussions/{did}/pin','POST',{},tb);ok(code,403,_)
        code,_=api(f'/api/discussions/{did}/lock','POST',{},ta);ok(code,200,_)
        code,_=api(f'/api/discussions/{did}/comments','POST',{"content":"blocked"},tc);ok(code,409,_)
        code,issue=api(f'/api/resources/{rid}/issues','POST',{"title":"Dataset path error in example","description":"The documented path is not found.","issue_type":"BUG"},tb);ok(code,201,issue);iid=issue['id']
        code,_=api(f'/api/issues/{iid}','PATCH',{"status":"IN_PROGRESS","priority":"HIGH","assignee_id":res['author_id']},ta);ok(code,200,_)
        code,_=api(f'/api/issues/{iid}','PATCH',{"priority":"CRITICAL"},tb);ok(code,403,_)
        code,_=api(f'/api/issues/{iid}/comments','POST',{"content":"I am investigating it."},ta);ok(code,201,_)
        code,_=api(f'/api/issues/{iid}','PATCH',{"status":"RESOLVED"},ta);ok(code,200,_)
        code,_=api(f'/api/issues/{iid}/comments','POST',{"content":"This follow-up is blocked after resolution."},tc);ok(code,409,_)
        code,state=api(f'/api/users/{a}/follow','POST',{},tb);ok(code,200,state);assert state['followers_count']==1
        code,state2=api(f'/api/users/{a}/follow','POST',{},tb);ok(code,200,state2);assert state2['followers_count']==1
        code,_=api(f'/api/users/{b}/follow','POST',{},tb);ok(code,400,_)
        code,n=api('/api/notifications',token=ta);ok(code,200,n);assert n['unread_count']>=3
        code,count=api('/api/notifications/unread-count',token=ta);ok(code,200,count)
        code,count2=api('/api/notifications/read-all','POST',{},ta);ok(code,200,count2);assert count2['unread_count']==0
        code,_=api('/api/notifications',token=tb);ok(code,200,_)
        print('V9 Community & Collaboration smoke checks passed.')
    finally:
        if rid: api('/api/resources/'+str(rid),'DELETE',token=ta)
if __name__=='__main__':
    try: run()
    except Exception as e: print('V9 smoke failed:',e,file=sys.stderr);raise
