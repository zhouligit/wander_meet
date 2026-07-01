#!/usr/bin/env bash
# 最快回到 2026-07-01 实名/资料门槛改动之前：代码 5ef7522 + 数据库 0031。
# 服务器示例：
#   cd /opt/wander_meet && bash scripts/rollback_pre_20260701.sh
# 可选：SERVICE_NAME=wandermeet
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TARGET="5ef7522"
SERVICE_NAME="${SERVICE_NAME:-wandermeet}"

echo "==> Git reset -> $TARGET"
git fetch origin 2>/dev/null || true
git reset --hard "$TARGET"

echo "==> 数据库：撤销 0032 实名字段（若已应用）"
bash scripts/rollback_enrollment_identity_db.sh

if command -v systemctl >/dev/null 2>&1; then
  echo "==> 重启 $SERVICE_NAME"
  sudo systemctl restart "$SERVICE_NAME"
fi

echo "==> 完成。代码 HEAD=$(git rev-parse --short HEAD)，请确认 alembic current 为 20260614_0031"
