{ processComposeFastIngestConf, ... }:
''
  if [[ -f data/postgres/PG_VERSION ]]; then
    read -r -p "Database is not empty. Continue? (y/N): " reply
    if [[ $reply == [Yy] || $reply == [Yy][Ee][Ss] ]]; then
      dev-clean
    else
      echo "Aborted"
      exit 1
    fi
  fi

  set -x

  : Restarting database in fast-ingest mode :
  dev-stop
  dev-start "${processComposeFastIngestConf}"

  python scripts/db_load.py -m "$1"

  : Restarting database in normal mode :
  dev-stop
  dev-start
''
