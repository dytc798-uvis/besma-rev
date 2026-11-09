"""Fixed SSH-stdin local PDF renderer bridge; no arbitrary commands or delivery."""
import sys,json,base64
from . import signature_jobs

def handle(value):
    from app.main import app
    from app.core.database import SessionLocal
    from app.modules.users.models import User
    from .routes import selected,store
    with SessionLocal()as db:
        def allowed(uid,p):
            try:
                user=db.get(User,uid)
                if not user or not user.is_active:return False
                row,key=selected(db,user,p['public_id'],p['period']);return key==p['context_id']
            except Exception:return False
        if value=={'action':'prepare-weekly'}:
            from .weekly_pdf import prepare
            return prepare(db,store())
        if value=={'action':'finalize-weekly'}:
            from .weekly_pdf import finalize
            return finalize(store())
        if value=={'action':'claim'}:return {'item':signature_jobs.claim(store(),allowed)}
        if set(value)=={'action','id','lease','content','error'}and value['action']=='finish':
            return signature_jobs.finish(store(),value['id'],value['lease'],base64.b64decode(value['content'],validate=True),value['error'],allowed)
        raise ValueError('OPERATION_INVALID')

def main():
    raw=sys.stdin.buffer.read(30*1024*1024+1)
    if len(raw)>30*1024*1024:raise ValueError('REQUEST_TOO_LARGE')
    print(json.dumps(handle(json.loads(raw)),ensure_ascii=False))
if __name__=='__main__':main()
