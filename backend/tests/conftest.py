import os
from pathlib import Path

# .env가 없을 때만 가짜 값을 넣어 DB가 필요 없는 테스트를 돌린다.
# .env가 있으면 그 값을 그대로 쓴다(환경 변수가 .env보다 우선하므로 덮어쓰지 않는다).
if not (Path(__file__).resolve().parents[1] / ".env").exists():
    os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
    os.environ.setdefault("JWT_SECRET", "test-secret")
