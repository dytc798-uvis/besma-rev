#!/usr/bin/env bash
set -euo pipefail

stage="${1:-}"
case "$stage" in
  /home/besma-admin/public-accident-cases-*) ;;
  *) echo "unsafe stage path: $stage" >&2; exit 2 ;;
esac

app_root=/srv/besma/backend
module_name=public_accident_cases
module_source="$stage/$module_name"
module_target="$app_root/app/modules/$module_name"
main_target="$app_root/app/main.py"
stamp="$(date +%Y%m%d_%H%M%S)"
snapshot="/srv/besma/ops_snapshots/task_public_accident_cases_$stamp"
next_main="$stage/main.py.next"

test -f "$module_source/routes.py"
test -f "$module_source/service.py"
test -f "$module_source/public_cases.json"
test -f "$module_source/__init__.py"

expected_count="$(python3 - "$module_source/public_cases.json" <<'PY'
import json
import sys
from pathlib import Path

source = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
required = {
    "survey_status": "제출완료",
    "risk_promotion_status": "승격대상",
    "distribution_status": "전파대상",
    "publication_status": "PUBLISHED",
}
cases = source.get("cases")
if not isinstance(cases, list):
    raise SystemExit("public accident-case list is invalid")
print(sum(all(case.get(key) == value for key, value in required.items()) for case in cases))
PY
)"
case "$expected_count" in
  ""|*[!0-9]*) echo "invalid public accident-case count: $expected_count" >&2; exit 2 ;;
esac
if [ "$expected_count" -lt 1 ]; then
  echo "public accident-case dataset is empty" >&2
  exit 2
fi

sudo -n install -d -o root -g besma -m 0750 "$snapshot"
sudo -n cp -a "$main_target" "$snapshot/main.py.before"
if sudo -n test -d "$module_target"; then
  sudo -n cp -a "$module_target" "$snapshot/$module_name.before"
fi
sudo -n sha256sum "$main_target" | sudo -n tee "$snapshot/main.py.before.sha256" >/dev/null

sudo -n cp "$main_target" "$next_main"
sudo -n chown "$(id -un):$(id -gn)" "$next_main"
python3 - "$next_main" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = path.read_bytes()
newline = b"\r\n" if b"\r\n" in data else b"\n"
import_line = b"from app.modules.public_accident_cases.routes import router as public_accident_cases_router"
include_line = b"    app.include_router(public_accident_cases_router)"

if import_line not in data:
    anchor = b"from app.modules.weather.routes import router as weather_router"
    if data.count(anchor) != 1:
        raise SystemExit("weather router import anchor is not unique")
    data = data.replace(anchor, anchor + newline + import_line, 1)

if include_line not in data:
    anchor = b"    app.include_router(weather_router)"
    if data.count(anchor) != 1:
        raise SystemExit("weather router include anchor is not unique")
    data = data.replace(anchor, anchor + newline + include_line, 1)

if data.count(import_line) != 1 or data.count(include_line) != 1:
    raise SystemExit("public accident-case router patch is not unique")
path.write_bytes(data)
PY

python3 -m py_compile \
  "$module_source/service.py" \
  "$module_source/routes.py" \
  "$next_main"

sudo -n install -d -o besma -g besma -m 0755 "$module_target"
for source in "$module_source"/__init__.py "$module_source"/public_cases.json "$module_source"/service.py "$module_source"/routes.py; do
  sudo -n install -o besma -g besma -m 0644 "$source" "$module_target/$(basename "$source")"
done
sudo -n install -o besma -g besma -m 0644 "$next_main" "$main_target"

rollback_main() {
  sudo -n install -o besma -g besma -m 0644 "$snapshot/main.py.before" "$main_target"
  sudo -n systemctl restart besma-backend.service || true
}
trap rollback_main ERR

sudo -n -u besma bash -c "cd '$app_root' && .venv/bin/python -m py_compile app/main.py app/modules/$module_name/service.py app/modules/$module_name/routes.py"
sudo -n -u besma bash -c "cd '$app_root' && .venv/bin/python -c 'from app.modules.public_accident_cases.service import load_public_dataset; data=load_public_dataset(); expected=$expected_count; assert data[\"case_count\"] == expected; print(\"PUBLIC_DATASET_OK count=%d\" % expected)'"
sudo -n systemctl restart besma-backend.service
for _ in $(seq 1 30); do
  if sudo -n systemctl is-active --quiet besma-backend.service && curl -fsS --max-time 2 http://127.0.0.1:8001/health >/dev/null; then
    break
  fi
  sleep 1
done
sudo -n systemctl is-active --quiet besma-backend.service
curl -fsS --max-time 5 http://127.0.0.1:8001/health
curl -fsS --max-time 5 http://127.0.0.1:8001/public/accident-cases/data | sudo -n tee "$snapshot/public-data-after.json" >/dev/null
{
  sudo -n sha256sum "$main_target"
  sudo -n find "$module_target" -maxdepth 1 -type f -exec sha256sum {} +
} | sudo -n tee "$snapshot/deployed.sha256" >/dev/null
sudo -n systemctl show besma-backend.service -p ActiveState -p SubState -p NRestarts -p MainPID | sudo -n tee "$snapshot/service-after.txt"
trap - ERR
echo "SNAPSHOT=$snapshot"
echo "DEPLOY_OK"
