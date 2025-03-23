#!/usr/bin/env bash
set -ex
cd /data/osm-ng/data
umount postgres/base
umount postgres/pg_wal
rm -rf postgres
mkdir -p postgres/base postgres/pg_wal
mount -t zfs data/postgres postgres/base
mount -t zfs data/postgres-wal postgres/pg_wal
rsync \
  --verbose \
  --human-readable \
  --whole-file \
  --archive \
  --delete \
  postgres-fresh/ postgres/
