"""One explicitly requested owner-only demonstration, outside actual site records."""
SOURCE='INSPECTION_DEMO'
KEY='inspection-demo:20261109:owner-96'
PUBLIC_ID='576c61bf-813c-4df8-bef3-69d848962b96'
OWNER=96

def is_demo(row):
    return bool(row and row.source==SOURCE and row.client_item_key==KEY and row.public_id==PUBLIC_ID and row.assigned_user_id==OWNER and row.created_by_user_id==OWNER)

def activity_value():
    return {'state':'ACTIVE','active':True,'demo':True}
