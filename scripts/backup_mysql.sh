#!/usr/bin/env bash
set -euo pipefail

# MySQL backup script for WanderMeet.
# Usage:
#   MYSQL_USER=wm_user MYSQL_PASSWORD='xxx' MYSQL_DB=wandermeet bash scripts/backup_mysql.sh
#
# Optional env:
#   BACKUP_DIR=/var/backups/wandermeet/mysql
#   RETENTION_DAYS=14
#   MYSQL_HOST=127.0.0.1
#   MYSQL_PORT=3306

MYSQL_HOST="${MYSQL_HOST:-127.0.0.1}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_USER="${MYSQL_USER:-}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-}"
MYSQL_DB="${MYSQL_DB:-wandermeet}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/wandermeet/mysql}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

if [[ -z "$MYSQL_USER" || -z "$MYSQL_PASSWORD" ]]; then
  echo "ERROR: MYSQL_USER and MYSQL_PASSWORD are required"
  exit 1
fi

mkdir -p "$BACKUP_DIR"

TS="$(date +%Y%m%d_%H%M%S)"
OUT_FILE="$BACKUP_DIR/${MYSQL_DB}_${TS}.sql.gz"
TMP_CNF="$(mktemp)"

cat > "$TMP_CNF" <<EOF
[client]
host=${MYSQL_HOST}
port=${MYSQL_PORT}
user=${MYSQL_USER}
password=${MYSQL_PASSWORD}
EOF

chmod 600 "$TMP_CNF"

cleanup() {
  rm -f "$TMP_CNF"
}
trap cleanup EXIT

echo "==> Backing up database: $MYSQL_DB"
mysqldump --defaults-extra-file="$TMP_CNF" \
  --single-transaction \
  --quick \
  --set-gtid-purged=OFF \
  "$MYSQL_DB" | gzip > "$OUT_FILE"

echo "==> Backup created: $OUT_FILE"

echo "==> Cleanup old backups (>${RETENTION_DAYS} days)"
find "$BACKUP_DIR" -type f -name "${MYSQL_DB}_*.sql.gz" -mtime +"$RETENTION_DAYS" -delete

echo "==> Backup completed"
