#!/bin/bash

# Config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}"
BACKUP_DIR="$ROOT_DIR/backup"
ENV_FILE="$ROOT_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "[ERROR] Missing .env file at: $ENV_FILE"
  exit 1
fi

# Load environment variables
set -o allexport
source "$ENV_FILE"
set +o allexport

DARTS_WORK_DIR="${DARTS_WORK_DIR:-/app/data/darts}"

shopt -s nullglob
backup_files=(
  "$BACKUP_DIR"/dartsdata_backup_*.tar.gz
)

if [ ${#backup_files[@]} -eq 0 ]; then
  echo "[ERROR] No backup files found in: $BACKUP_DIR"
  exit 1
fi

latest_backup=$(ls -1t "${backup_files[@]}" 2>/dev/null | head -n 1)
if [ -z "$latest_backup" ]; then
  echo "[ERROR] Unable to determine latest backup file."
  exit 1
fi

echo "[INFO] Restoring dartsdata from: $latest_backup"
cat "$latest_backup" | docker compose run --rm --no-deps -T web \
  sh -c 'mkdir -p "$DARTS_WORK_DIR" && find "$DARTS_WORK_DIR" -mindepth 1 -delete && tar -xzf - -C "$DARTS_WORK_DIR" --strip-components=1 dartsdata'
if [ $? -ne 0 ]; then
  echo "[ERROR] Dartsdata restore failed!"
  exit 1
fi

echo "[DONE] Dartsdata restore completed."
