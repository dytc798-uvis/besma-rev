"""Verify HQ Korean accounts can login and access FE + document explorer APIs."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.modules.users.hq_safe_accounts import HQ_SAFE_ACCOUNTS  # noqa: E402

TARGETS = {
    "안전보건-김복수": "721228",
    "안전보건-정상익": "790808",
    "안전보건-엄재복": "920619",
    "hq01": "1111",
    "hq02": "1111",
    "hq03": "1111",
}


def _post_login(login_id: str, password: str) -> str:
    body = urllib.parse.urlencode({"username": login_id, "password": password}).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:8001/auth/login",
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
        return data["access_token"]


def _get(path: str, token: str) -> int:
    req = urllib.request.Request(
        f"http://127.0.0.1:8001{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


def main() -> None:
    pw_map = {lid: pw for _n, lid, pw in HQ_SAFE_ACCOUNTS}
    for login_id, password in TARGETS.items():
        password = pw_map.get(login_id, password)
        try:
            token = _post_login(login_id, password)
        except urllib.error.HTTPError as e:
            print(f"LOGIN FAIL {login_id}: {e.code} {e.read().decode()[:120]}")
            continue
        fe = _get("/functional-eval/hq/summary", token)
        doc = _get("/document-explorer/list?category=template", token)
        me = _get("/auth/me", token)
        print(f"OK {login_id} me={me} fe_hq={fe} docs={doc}")


if __name__ == "__main__":
    main()
