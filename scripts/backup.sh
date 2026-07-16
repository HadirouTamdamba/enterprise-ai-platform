#!/usr/bin/env bash
# Backup PostgreSQL and Qdrant from the Docker Compose stack.
# Usage: ./scripts/backup.sh [output_dir]
set -euo pipefail

OUT="${1:-backups/$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$OUT"

echo "→ PostgreSQL dump"
docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-eap}" "${POSTGRES_DB:-eap}" \
  | gzip > "$OUT/postgres.sql.gz"

echo "→ Qdrant snapshot"
curl -sf -X POST "http://localhost:6333/snapshots" > "$OUT/qdrant-snapshot.json"

echo "→ Uploaded documents volume"
docker run --rm -v enterprise-ai-platform_upload_data:/data -v "$(pwd)/$OUT":/backup \
  alpine tar czf /backup/uploads.tar.gz -C /data .

echo "Backup complete: $OUT"
