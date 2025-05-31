#!/usr/bin/env bash
set -ex
cd /data/osm-ng/data
umount postgres/pg_wal
umount postgres/base/pgsql_tmp
umount postgres/base
rm -rf postgres
mkdir -p \
  postgres \
  postgres/base \
  postgres/base/pgsql_tmp \
  postgres/pg_wal \
  postgres-fresh/base/pgsql_tmp
mount -t zfs data/postgres postgres/base
mount -t zfs data/tmp/postgres postgres/base/pgsql_tmp
mount -t zfs rpool/postgres-wal postgres/pg_wal
rsync \
  --verbose \
  --human-readable \
  --whole-file \
  --archive \
  --delete \
  postgres-fresh/ postgres/
chown osm-ng:osm-ng /data/osm-ng/data -R
