{
  pkgs,
  enablePostgres,
  pkgsUrl,
  ...
}:
(pkgs.lib.optionalString enablePostgres ''
  current_pkgs_url=
  { read -r current_pkgs_url <data/.dev-version; } 2>/dev/null || true
  [[ $current_pkgs_url == "${pkgsUrl}" ]] && exit 0
  echo "Nixpkgs changed, performing services upgrade"

  psql() {
    PGOPTIONS='-c timescaledb.disable_load=on' \
      command psql -X "$POSTGRES_URL" "$@"
  }
  if [[ -n $(psql -tAc "SELECT 1 FROM information_schema.tables WHERE table_name = 'migration'") ]]; then
    echo "Upgrading postgres/timescaledb"
    psql -c "ALTER EXTENSION timescaledb UPDATE"

    echo "Upgrading postgres/postgis"
    psql -c "SELECT postgis_extensions_upgrade()" || true

    echo "Upgrading postgres/h3"
    psql -c "ALTER EXTENSION h3 UPDATE"
    psql -c "ALTER EXTENSION h3_postgis UPDATE"
  fi

  echo "${pkgsUrl}" > data/.dev-version
  echo "Services upgrade completed"
'')
