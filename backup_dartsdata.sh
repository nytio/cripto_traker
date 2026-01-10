#!/bin/bash

# Config
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}"
BACKUP_DIR="$ROOT_DIR/backup"
ARCHIVE_NAME="dartsdata_backup_$TIMESTAMP.tar.gz"
ARCHIVE_PATH="$BACKUP_DIR/$ARCHIVE_NAME"
ENV_FILE="$ROOT_DIR/.env"
INIT_SQL="$BACKUP_DIR/init.sql"

mkdir -p "$BACKUP_DIR"

if [ ! -f "$ENV_FILE" ]; then
  echo "[ERROR] Missing .env file at: $ENV_FILE"
  exit 1
fi
if [ ! -f "$INIT_SQL" ]; then
  echo "[ERROR] Missing init.sql backup at: $INIT_SQL"
  exit 1
fi

# Load environment variables
set -o allexport
source "$ENV_FILE"
set +o allexport

DARTS_WORK_DIR="${DARTS_WORK_DIR:-/app/data/darts}"

TMP_DIR="$(mktemp -d)"
DATA_TAR="$TMP_DIR/dartsdata_backup_$TIMESTAMP.tar"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

# === STEP 1: Backup dartsdata volume ===
echo "[INFO] Backing up dartsdata from: $DARTS_WORK_DIR"
docker compose run --rm --no-deps -T web tar -cf - --transform='s,^\./,dartsdata/,' -C "$DARTS_WORK_DIR" . > "$DATA_TAR"
if [ $? -ne 0 ]; then
  echo "[ERROR] Dartsdata backup failed!"
  exit 1
fi

# === STEP 2: Include .env ===
tar -rf "$DATA_TAR" -C "$ROOT_DIR" .env
if [ $? -ne 0 ]; then
  echo "[ERROR] Failed to add .env to backup!"
  exit 1
fi

# === STEP 3: Include init.sql ===
tar -rf "$DATA_TAR" -C "$BACKUP_DIR" init.sql
if [ $? -ne 0 ]; then
  echo "[ERROR] Failed to add init.sql to backup!"
  exit 1
fi

# === STEP 4: Compress archive ===
gzip -c "$DATA_TAR" > "$ARCHIVE_PATH"
if [ $? -ne 0 ]; then
  echo "[ERROR] Compression failed!"
  exit 1
fi

echo "[DONE] Backup created at: $ARCHIVE_PATH"
