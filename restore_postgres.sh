#!/bin/bash

# Config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}"
BACKUP_DIR="$ROOT_DIR/backup"
INIT_SQL="$BACKUP_DIR/init.sql"
ENV_FILE="$ROOT_DIR/.env"
POSTGRES_CONTAINER="$(docker compose ps -q db)"

if [ ! -f "$INIT_SQL" ]; then
  echo "[ERROR] Missing backup file: $INIT_SQL"
  exit 1
fi
if [ ! -f "$ENV_FILE" ]; then
  echo "[ERROR] Missing .env file at: $ENV_FILE"
  exit 1
fi

if [ -z "$POSTGRES_CONTAINER" ]; then
  echo "[ERROR] PostgreSQL container not running."
  exit 1
fi

# Load environment variables
set -o allexport
source "$ENV_FILE"
set +o allexport

echo "[INFO] Restoring PostgreSQL database from: $INIT_SQL"
cat "$INIT_SQL" | docker exec -i "$POSTGRES_CONTAINER" psql -U "$POSTGRES_USER" "$POSTGRES_DB"
if [ $? -ne 0 ]; then
  echo "[ERROR] PostgreSQL restore failed!"
  exit 1
fi

echo "[DONE] PostgreSQL restore completed."
