import os
import sys
from pathlib import Path


def pytest_configure(config):
    # 테스트 픽스처의 datetime.utcnow() Deprecation만 억제 (앱/모델은 utc_now 사용).
    config.addinivalue_line(
        "filterwarnings",
        r"ignore:datetime\.datetime\.utcnow\(\) is deprecated:DeprecationWarning",
    )


# Allow `import app.*` in tests when running from `backend/`
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Ensure consistent working directory expectations (optional)
os.environ.setdefault("PYTHONUTF8", "1")

