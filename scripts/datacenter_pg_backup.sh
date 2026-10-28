#!/bin/sh
# Runs in postgres:15-alpine. Creates a portable transaction-consistent database dump.
set -eu
umask 077
mkdir -p /backup/postgres
chmod 700 /backup/postgres
cd /backup/postgres
while :; do
  requested=$(cat /state/pg_backup.trigger 2>/dev/null || true)
  completed=$(cat .last_run 2>/dev/null || true)
  case "$requested" in ''|*[!0-9a-f]*) sleep 15; continue;; esac
  if [ "$requested" = "$completed" ]; then sleep 15; continue; fi
  stamp=$(date +%Y%m%d-%H%M%S)
  filename="office-pg-$stamp-$requested.dump"
  printf '{"state":"running","run_id":"%s","started_at":"%s"}\n' "$requested" "$(date -Iseconds)" > /state/pg_backup.json.tmp
  chmod 644 /state/pg_backup.json.tmp
  mv /state/pg_backup.json.tmp /state/pg_backup.json
  if pg_dump --format=custom --no-owner --no-acl --exclude-table-data=app.cache_documents --exclude-table-data=app.cache_blobs --file="$filename.tmp" && pg_restore --list "$filename.tmp" >/dev/null; then
    mv "$filename.tmp" "$filename"
    sha256sum "$filename" > "$filename.sha256"
    tar -czf "$filename.restore-tools.tar.gz" -C /source/project       backend/datacenter_db.py backend/datacenter_archive.py backend/datacenter_lib.py backend/datacenter_sql.py       scripts/datacenter_restore.py vendor/pgdeps docs/data-center-migration.md
    sha256sum "$filename.restore-tools.tar.gz" > "$filename.restore-tools.tar.gz.sha256"
    bytes=$(wc -c < "$filename" | tr -d ' ')
    digest=$(cut -d ' ' -f1 "$filename.sha256")
    printf '{"state":"complete","run_id":"%s","finished_at":"%s","file":"%s","bytes":%s,"sha256":"%s","verification":"archive-readable"}\n' "$requested" "$(date -Iseconds)" "$filename" "$bytes" "$digest" > /state/pg_backup.json.tmp
    chmod 644 /state/pg_backup.json.tmp
  mv /state/pg_backup.json.tmp /state/pg_backup.json
    printf '%s' "$requested" > .last_run
    # Keep 14 successful database dumps; never prune the in-progress archive.
    set -- office-pg-*.dump
    while [ "$#" -gt 14 ]; do
      rm -f -- "$1" "$1.sha256" "$1.restore-tools.tar.gz" "$1.restore-tools.tar.gz.sha256"
      shift
    done
    echo "PostgreSQL backup complete: $filename ($bytes bytes)"
  else
    rm -f "$filename.tmp"
    printf '{"state":"failed","run_id":"%s","finished_at":"%s"}\n' "$requested" "$(date -Iseconds)" > /state/pg_backup.json.tmp
    chmod 644 /state/pg_backup.json.tmp
  mv /state/pg_backup.json.tmp /state/pg_backup.json
    echo 'PostgreSQL backup failed; retrying in 60 seconds' >&2
    sleep 60
  fi
  sleep 15
done
