#!/bin/sh
set -eu

: "${DATABASE_URL:?DATABASE_URL is required}"
: "${BACKUP_DIR:?BACKUP_DIR is required}"

umask 077
mkdir -p "$BACKUP_DIR"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="$BACKUP_DIR/infomir-$timestamp.dump"
pg_dump --dbname="$DATABASE_URL" --format=custom --no-owner --file="$target"
find "$BACKUP_DIR" -type f -name 'infomir-*.dump' -mtime +30 -delete
printf '%s\n' "$target"

