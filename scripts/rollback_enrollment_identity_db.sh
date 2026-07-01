#!/usr/bin/env bash
# 撤销 20260622_0032 实名报名相关库表字段，使 DB 与 5ef7522（0031）代码一致。
# 用法（服务器或本地，需已配置 .env / DATABASE_URL）：
#   bash scripts/rollback_enrollment_identity_db.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MIG="alembic/versions/20260622_0032_enrollment_identity.py"
REV="20260622_0032"
DOWN="20260614_0031"

current="$(.venv/bin/alembic current 2>/dev/null | awk '{print $1}' || alembic current 2>/dev/null | awk '{print $1}' || true)"
echo "==> alembic current: ${current:-unknown}"

if [[ "$current" != "$REV" ]]; then
  echo "==> 无需回滚：当前 revision 不是 $REV（可能已回滚或未部署过实名迁移）"
  exit 0
fi

echo "==> 写入临时 migration 文件以执行 downgrade"
git show c6c42f8:"$MIG" > "$MIG"

cleanup() {
  rm -f "$MIG"
}
trap cleanup EXIT

if [[ -x .venv/bin/alembic ]]; then
  .venv/bin/alembic downgrade "$DOWN"
else
  alembic downgrade "$DOWN"
fi

echo "==> DB 已回滚至 $DOWN"
if [[ -x .venv/bin/alembic ]]; then
  .venv/bin/alembic current
else
  alembic current
fi
