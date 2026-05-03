#!/bin/bash
# TABLESYS Postgres Database Backup Script
# This script creates a compressed database backup and retains the last 7 days of backups
# Usage: ./backup.sh

set -e

# Configuration
BACKUP_DIR="/backups"
DB_HOST=${POSTGRES_HOST:-postgres}
DB_PORT=${POSTGRES_PORT:-5432}
DB_USER=${POSTGRES_USER:-unza_admin}
DB_NAME=${POSTGRES_DB:-tablesys}
DATE=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_FILE="${BACKUP_DIR}/tablesys_backup_${DATE}.sql.gz"

echo "[$(date)] Starting backup process for ${DB_NAME} on ${DB_HOST}..."

# Ensure backup directory exists
mkdir -p "${BACKUP_DIR}"

# Run pg_dump and compress
# PGPASSWORD must be injected via environment variable
if [ -z "$POSTGRES_PASSWORD" ]; then
    echo "Warning: POSTGRES_PASSWORD is not set. Backup might fail if authentication is required."
fi

PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" | gzip > "${BACKUP_FILE}"

echo "[$(date)] Backup completed successfully: ${BACKUP_FILE}"

# Cleanup backups older than 7 days
echo "[$(date)] Cleaning up backups older than 7 days..."
find "${BACKUP_DIR}" -type f -name "tablesys_backup_*.sql.gz" -mtime +7 -delete

echo "[$(date)] Cleanup finished."
