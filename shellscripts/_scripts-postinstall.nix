{ pkgs, ... }:
(
  ''
    rm -rf node_modules/bootstrap/dist/css

    if [[ ! data/cache/browserslist_versions.json -nt bun.lock ]]; then
      echo "Regenerating browserslist cache"
      mkdir -p data/cache
      bunx browserslist | jq -Rnc '
        [inputs | split(" ") | {browser: .[0], version: (.[1] | split("-") | map(tonumber) | min)}] |
        group_by(.browser) |
        map({(.[0].browser): (map(.version) | min)}) |
        add
      ' > data/cache/browserslist_versions.json
    fi
  ''
  + pkgs.lib.optionalString pkgs.stdenv.isLinux ''
    interpreter="${pkgs.stdenv.cc.bintools.dynamicLinker}"
    sass_dirs=(node_modules/.bun/sass-embedded*)
    for dir in "''${sass_dirs[@]}"; do
      for bin in "$dir"/**/dart; do
        [[ -f $bin && -x $bin ]] || continue
        curr=$(patchelf --print-interpreter "$bin" 2>/dev/null || true)
        if [[ $curr != "$interpreter" ]]; then
          patchelf --set-interpreter "$interpreter" "$bin"
          echo "Patched $bin interpreter to $interpreter"
        fi
      done
    done
  ''
  + ''
    wait
  ''
)
