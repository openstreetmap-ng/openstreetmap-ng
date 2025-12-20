{ processComposeConf, ... }:
''
  if process-compose list -U >/dev/null 2>&1; then
    echo "Services are already running"
    exit 0
  fi

  if [ ! -f data/postgres/PG_VERSION ]; then
    initdb -D data/postgres \
      --no-instructions \
      --locale-provider=icu \
      --icu-locale=und \
      --no-locale \
      --text-search-config=pg_catalog.simple \
      --auth=trust \
      --username=postgres
  fi

  mkdir -p data/mailpit data/postgres_unix data/pcompose
  echo "Services starting..."
  process-compose up -U --detached -f "''${1:-${processComposeConf}}" >/dev/null
  process-compose project is-ready -U --wait

  while read -r name; do
    if [ -z "$name" ]; then
      continue
    fi

    echo -n "Waiting for $name..."
    while [ "$(process-compose process get "$name" -U --output json | jq -r '.[0].is_ready')" != "Ready" ]; do
      sleep 1
      echo -n "."
    done
    echo " ready"
  done < <(process-compose list -U)

  echo "Services started"
  _dev-upgrade
''
