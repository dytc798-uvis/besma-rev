#!/bin/bash
set -e
BASE="http://127.0.0.1:8001"
TOKEN=$(curl -fsS -X POST "$BASE/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=26025&password=681125" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "=== eval-catalog ==="
curl -fsS "$BASE/functional-eval/eval-catalog" -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('functional',len(d['FUNCTIONAL']['criteria']),'safety',len(d['SAFETY']['criteria']))"

echo "=== workers (row_no, eval status) ==="
curl -fsS "$BASE/functional-eval/my-site/workers" -H "Authorization: Bearer $TOKEN" \
  | python3 -c "
import sys,json
d=json.load(sys.stdin)
items=d['items'][:5]
for w in items:
  fa=w.get('functional_assessment')
  st='미평가' if not fa or not fa.get('is_complete') else fa.get('grade_label')
  print(w['row_no'], w['name'], st)
rows=[w['row_no'] for w in d['items']]
assert len(rows)==len(set(rows)) or max(rows)==len(rows), 'duplicate row_no'
print('total workers', len(d['items']), 'unique row_no', len(set(rows)))
"

echo "PROD_EVAL_VERIFY_OK"
