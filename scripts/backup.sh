#!/bin/bash
# Backup do SQLite — ajuste DATA e DEST antes de usar.
# Agende no cron: 0 2 * * * /opt/manucontrol/scripts/backup.sh

set -euo pipefail

DATA="${DATABASE_PATH:-/var/lib/manucontrol/manu.db}"
DEST="${BACKUP_DIR:-/backup/manucontrol}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-30}"

if [ ! -f "$DATA" ]; then
  echo "Arquivo não encontrado: $DATA" >&2
  exit 1
fi

mkdir -p "$DEST"
STAMP="$(date +%Y%m%d-%H%M)"
cp "$DATA" "$DEST/manu-${STAMP}.db"
find "$DEST" -name "manu-*.db" -mtime +"$KEEP_DAYS" -delete
echo "Backup OK: $DEST/manu-${STAMP}.db"
