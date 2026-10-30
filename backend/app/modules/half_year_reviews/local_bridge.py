"""Fixed SSH-stdin worker interface. Not a public route or an arbitrary command runner."""
import base64,json,os,sys

def handle(request):
    from app.main import app
    from app.core.database import SessionLocal
    from app.modules.users.models import User
    from app.modules.inspection_reports.routes import actor,plan
    from .routes import store
    from . import jobs
    if os.environ.get('BESMA_HALF_YEAR_REVIEWS_ENABLED','').lower()not in {'1','true'}:raise ValueError('FEATURE_DISABLED')
    with SessionLocal()as db:
        def allowed(uid,job):
            try:
                user=db.get(User,uid)
                if not user or not user.is_active:return False
                actor(db,user);row=plan(db,user,job['public_id'])
                from .catalog import context_key
                return context_key(row,job['period']).split('|')[0]==job.get('context_site',context_key(row,job['period']).split('|')[0])
            except Exception:return False
        if request['action']=='claim'and set(request)=={'action'}:
            item=jobs.claim(store(),allowed)
            if item is not None:item['source']=base64.b64encode(item['source']).decode()
            return {'item':item}
        if request['action']=='finish'and set(request)=={'action','id','lease','result','pages','source_sha256','error'}:
            result=jobs.finish(store(),request['id'],request['lease'],request['result'],request['pages'],request['source_sha256'],request['error'],allowed)
            return {'id':result['id'],'status':result['status']}
        raise ValueError('OPERATION_INVALID')

def main():
    data=sys.stdin.buffer.read(1024*1024+1)
    if len(data)>1024*1024:raise ValueError('REQUEST_TOO_LARGE')
    result=handle(json.loads(data))
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
