{ pkgs, ... }:
(
  ''
    rm -rf node_modules/bootstrap/dist/css

    static-img-pipeline &

    if [ ! data/cache/browserslist_versions.json -nt bun.lock ]; then
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
    ((''${#sass_dirs[@]})) && while IFS= read -r -d "" bin; do
      curr=$(patchelf --print-interpreter "$bin" 2>/dev/null || true)
      if [ "$curr" != "$interpreter" ]; then
        patchelf --set-interpreter "$interpreter" "$bin"
        echo "Patched $bin interpreter to $interpreter"
      fi
    done < <(fd -0 -t x "^dart$" "''${sass_dirs[@]}")
  ''
  + ''
    wait
  ''
)
