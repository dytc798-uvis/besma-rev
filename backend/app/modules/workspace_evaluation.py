"""Read-only view of the existing evaluation ledger; never creates a period."""
from sqlalchemy import select,inspect
from app.core.permissions import assert_fe_hq_read
from app.modules.functional_eval import service
from app.modules.functional_eval.models import FunctionalEvalPeriod,FunctionalEvalSiteApproval

SCOPE='REGISTERED_EVALUATION_TARGETS'
def empty(state):
 return {'state':state,'period':None,'sites':[],'scope':SCOPE,'whole_roster_verified':False}

def evaluation_status(db,user):
 assert_fe_hq_read(user)
 periods=db.scalars(select(FunctionalEvalPeriod).where(FunctionalEvalPeriod.is_active==True).order_by(FunctionalEvalPeriod.id.desc()).limit(2)).all()
 if len(periods)!=1:return empty('NO_PERIOD'if not periods else'CHECK_REQUIRED')
 period=periods[0]
 # This operating service predates additional-round and continuous-mode tables.
 # Do not silently project those ledgers as the first periodic evaluation.
 names=inspect(db.connection()).get_table_names()
 for name in names:
  if not name.startswith(('functional_eval_period_modes','functional_eval_additional_','functional_eval_target_enrollment','functional_eval_intake_receipt')):continue
  columns={c['name']for c in inspect(db.connection()).get_columns(name)}
  if 'period_id'not in columns:return empty('CHECK_REQUIRED')
  from sqlalchemy import text
  # Empty extension tables or records for another period do not change this
  # legacy period. A configured mode/round needs its own compatible service.
  if db.execute(text('SELECT 1 FROM "'+name+'" WHERE period_id=:period LIMIT 1'),{'period':period.id}).first():return empty('CHECK_REQUIRED')
 with db.no_autoflush:
  summary=service.build_hq_summary_response(db,period,include_inactive=True,persist_completion_locks=False)
  approvals={row.site_code:row.status for row in db.scalars(select(FunctionalEvalSiteApproval).where(FunctionalEvalSiteApproval.period_id==period.id)).all()}
 sites=[]
 for row in summary['sites']:
  item={key:row.get(key)for key in ['site_code','site_name','total','fully_complete','evaluator_name','evaluator_missing','completion_locked']};item['approval_status']=approvals.get(row['site_code']);sites.append(item)
 status=summary['period']
 if type(status.get('is_closed'))is not bool or type(status.get('evaluation_open'))is not bool:return empty('CHECK_REQUIRED')
 return {'state':'VERIFIED','period':{'id':period.id,'title':period.title,'deadline_date':str(period.deadline_date),'evaluation_mode':'PERIODIC','is_closed':status['is_closed'],'evaluation_open':status['evaluation_open'],'evaluation_opens_at':status.get('evaluation_opens_at')},'sites':sites,'scope':SCOPE,'target_basis':'ATTENDANCE_OR_ASSESSMENT_HISTORY','whole_roster_verified':False,'history_only':status['is_closed']}
