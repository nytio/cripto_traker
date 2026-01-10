#!/bin/bash

# Config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}"
BACKUP_DIR="$ROOT_DIR/backup"
INIT_SQL="$BACKUP_DIR/init.sql"
ENV_FILE="$ROOT_DIR/.env"
POSTGRES_CONTAINER="$(docker compose ps -q db)"

mkdir -p "$BACKUP_DIR"

if [ ! -f "$ENV_FILE" ]; then
  echo "[ERROR] Missing .env file at: $ENV_FILE"
  exit 1
fi

# Load environment variables
set -o allexport
source "$ENV_FILE"
set +o allexport

# === STEP 1: Dump PostgreSQL DB ===
echo "[INFO] Dumping PostgreSQL database..."
docker exec "$POSTGRES_CONTAINER" pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "$INIT_SQL"
if [ $? -ne 0 ]; then
  echo "[ERROR] PostgreSQL dump failed!"
  exit 1
fi
echo "[INFO] PostgreSQL dump created at: $INIT_SQL"
