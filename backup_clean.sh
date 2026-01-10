#!/bin/bash

# Config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}"
BACKUP_DIR="$ROOT_DIR/backup"
INIT_SQL="$BACKUP_DIR/init.sql"

mkdir -p "$BACKUP_DIR"

shopt -s nullglob

backup_files=(
  "$BACKUP_DIR"/dartsdata_backup_*.tar.gz
)

latest_backup=""
latest_stamp=""
for file in "${backup_files[@]}"; do
    [ -f "$file" ] || continue
    filename="${file##*/}"
    if [[ "$filename" =~ ^dartsdata_backup_([0-9]{8})_([0-9]{6})\.tar\.gz$ ]]; then
        stamp="${BASH_REMATCH[1]}${BASH_REMATCH[2]}"
        if [ -z "$latest_stamp" ] || [[ "$stamp" > "$latest_stamp" ]]; then
            latest_stamp="$stamp"
            latest_backup="$file"
        fi
    fi
done

# === STEP 3: Retention policy ===
echo "[INFO] Cleaning up old backups..."
for file in "${backup_files[@]}"; do
    [ -f "$file" ] || continue

    if [ -n "$latest_backup" ] && [ "$file" = "$latest_backup" ]; then
        continue
    fi

    filename="${file##*/}"
    if [[ "$filename" =~ ^dartsdata_backup_([0-9]{8})_([0-9]{6})\.tar\.gz$ ]]; then
        date_part="${BASH_REMATCH[1]}"
    else
        continue
    fi

    # Keep first of month
    if [[ "${date_part:6:2}" == "01" ]]; then
        continue
    fi

    # Delete if older than 7 days
    file_date=$(date -d "${date_part}" +%s 2>/dev/null)
    [ -n "$file_date" ] || continue
    now=$(date +%s)
    age_days=$(( (now - file_date) / 86400 ))

    if (( age_days > 7 )); then
        echo "[INFO] Deleting old backup: $file (age: $age_days days)"
        rm -f "$file"
    fi
done

if [ -n "$latest_backup" ] && [ -f "$INIT_SQL" ]; then
    rm -f "$INIT_SQL"
fi

echo "[DONE] Backup cleaned."
