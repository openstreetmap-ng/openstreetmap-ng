{ processComposeFastIngestConf, ... }:
''
  set -x
  : Restarting database in fast-ingest mode :
  dev-stop
  dev-start "${processComposeFastIngestConf}"
  python scripts/db_load.py -m "$1"
  : Restarting database in normal mode :
  dev-stop
  dev-start
''
