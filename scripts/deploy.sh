#!/usr/bin/env bash
set -euo pipefail

# One-command deploy script for Ubuntu server.
# Usage:
#   bash scripts/deploy.sh
# Optional env:
#   APP_DIR=/opt/wander_meet SERVICE_NAME=wandermeet BRANCH=main bash scripts/deploy.sh

APP_DIR="${APP_DIR:-/opt/wander_meet}"
SERVICE_NAME="${SERVICE_NAME:-wandermeet}"
BRANCH="${BRANCH:-main}"
VENV_PATH="${VENV_PATH:-$APP_DIR/.venv}"

echo "==> Deploy start"
echo "APP_DIR=$APP_DIR SERVICE_NAME=$SERVICE_NAME BRANCH=$BRANCH"

if [[ ! -d "$APP_DIR" ]]; then
  echo "ERROR: app dir not found: $APP_DIR"
  exit 1
fi

cd "$APP_DIR"

if [[ ! -d ".git" ]]; then
  echo "ERROR: $APP_DIR is not a git repository"
  exit 1
fi

echo "==> Git pull ($BRANCH)"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

if [[ ! -d "$VENV_PATH" ]]; then
  echo "==> Create virtualenv"
  python3 -m venv "$VENV_PATH"
fi

echo "==> Install dependencies"
"$VENV_PATH/bin/pip" install -U pip
"$VENV_PATH/bin/pip" install -r requirements.txt

echo "==> Run migrations"
"$VENV_PATH/bin/alembic" upgrade head

echo "==> Restart service"
sudo systemctl restart "$SERVICE_NAME"
sudo systemctl status "$SERVICE_NAME" --no-pager -l

echo "==> Deploy success"
