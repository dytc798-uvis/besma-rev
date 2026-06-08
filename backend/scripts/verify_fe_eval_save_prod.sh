#!/bin/bash
# Save one FUNCTIONAL assessment on prod (smoke) then revert by saving again is ok for test worker
set -e
BASE="http://127.0.0.1:8001"
TOKEN=$(curl -fsS -X POST "$BASE/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=26025&password=681125" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

WORKER_ID=$(curl -fsS "$BASE/functional-eval/my-site/workers" -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['items'][0]['id'])")

CAT=$(curl -fsS "$BASE/functional-eval/eval-catalog" -H "Authorization: Bearer $TOKEN")
SCORES=$(echo "$CAT" | python3 -c "
import sys,json
d=json.load(sys.stdin)
scores={c['id']: c['grades'][0]['key'] for c in d['FUNCTIONAL']['criteria']}
import json as J
print(J.dumps(scores))
")

RES=$(curl -fsS -X PUT "$BASE/functional-eval/workers/$WORKER_ID/assessment/FUNCTIONAL" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"scores\": $SCORES}")

echo "$RES" | python3 -c "import sys,json; a=json.load(sys.stdin)['assessment']; assert a['is_complete']; print('saved', a['grade_label'], a['total_score'])"
echo "PROD_EVAL_SAVE_OK"
