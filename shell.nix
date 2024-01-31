{ isDevelopment ? true }:

let
  # Currently using nixpkgs-23.11-darwin
  # Update with `nixpkgs-update` command
  pkgs = import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/9658699e3ab26e6f499c95e2e9093819cac777b3.tar.gz") { };

  libraries' = with pkgs; [
    # Base libraries
    stdenv.cc.cc.lib
    file.out
    libxml2.out
    libyaml.out
    zlib.out
  ];

  packages' = with pkgs; [
    # Base packages
    python312
    coreutils
    zstd
    bun
    (postgresql_16_jit.withPackages (ps: [ ps.postgis ]))
    redis

    # Scripts
    # -- Misc
    (writeShellScriptBin "make-version" ''
      sed -i -E "s|VERSION_DATE = '.*?'|VERSION_DATE = '$(date +%y%m%d)'|" app/config.py
    '')
    (writeShellScriptBin "make-bundle" ''
      dir="app/static/js"

      bundle_paths=$(find "$dir" \
        -maxdepth 1 \
        -type f \
        -name "bundle-*")

      # Delete existing bundles
      [ -z "$bundle_paths" ] || rm $bundle_paths

      src_paths=$(find "$dir" \
        -maxdepth 1 \
        -type f \
        -name "*.js" \
        -not -name "_*")

      for src_path in $src_paths; do
        src_name=$(basename "$src_path")
        src_stem=$(echo "$src_name" | cut -d. -f1)
        src_ext=$(echo "$src_name" | cut -d. -f2)

        output=$(bun build \
          "$src_path" \
          --entry-naming "[dir]/bundle-[name]-[hash].[ext]" \
          --minify \
          --outdir "$dir" | tee /dev/stdout)

        bundle_name=$(grep \
          --only-matching \
          --extended-regexp \
          --max-count=1 \
          "bundle-$src_stem-[0-9a-f]{16}\.$src_ext" <<< "$output")

        if [ -z "$bundle_name" ]; then
          echo "ERROR: Failed to match bundle name for $src_path"
          exit 1
        fi

        # TODO: sed replace
        echo "Replacing $src_name with $bundle_name"
      done
    '')
  ] ++ lib.optionals isDevelopment [
    # Development packages
    poetry
    ruff
    biome
    gcc
    gettext
    dart-sass
    inotify-tools

    # Scripts
    # -- Cython
    (writeShellScriptBin "cython-build" ''
      python setup.py build_ext --inplace --parallel $(nproc --all)
    '')
    (writeShellScriptBin "cython-clean" ''
      shopt -s globstar
      rm -rf build/
      dirs=(
        app/exceptions
        app/exceptions06
        app/format06
        app/format07
        app/lib
        app/middlewares
        app/responses
        app/validators
      )
      for dir in "''${dirs[@]}"; do
        rm -rf "$dir"/**/*{.c,.html,.so}
      done
    '')

    # -- Alembic
    (writeShellScriptBin "alembic-migration" ''
      name=$1
      if [ -z "$name" ]; then
        read -p "Database migration name: " name
      fi
      alembic revision --autogenerate --message "$name"
    '')
    (writeShellScriptBin "alembic-upgrade" ''
      alembic upgrade head
    '')

    # -- Locale
    (writeShellScriptBin "locale-clean" ''
      rm -rf config/locale/*/
    '')
    (writeShellScriptBin "locale-download" ''
      python scripts/locale_download.py
    '')
    (writeShellScriptBin "locale-postprocess" ''
      python scripts/locale_postprocess.py
    '')
    (writeShellScriptBin "locale-make-i18next" ''
      rm -rf config/locale/i18next
      python scripts/locale_make_i18next.py
    '')
    (writeShellScriptBin "locale-make-gnu" ''
      set -e
      mkdir -p config/locale/gnu
      echo "Converting to GNU gettext format"

      for source_file in $(find config/locale/i18next -type f); do
        stem=$(basename "$source_file" .json)
        locale=''${stem::-17}
        target_file="config/locale/gnu/$locale/LC_MESSAGES/messages.po"
        target_file_bin="''${target_file%.po}.mo"

        if [ ! -f "$target_file_bin" ] || [ "$source_file" -nt "$target_file_bin" ]; then
          mkdir -p "$(dirname "$target_file")"

          bun run i18next-conv \
            --quiet \
            --language "$locale" \
            --source "$source_file" \
            --target "$target_file" \
            --keyseparator "." \
            --ctxSeparator "__" \
            --compatibilityJSON "v4"

          msgfmt "$target_file" --output-file "$target_file_bin";

          # preserve original timestamps
          touch -r "$source_file" "$target_file" "$target_file_bin"

          echo "[✅] $locale"
        fi
      done
    '')
    (writeShellScriptBin "locale-pipeline" ''
      set -e
      locale-postprocess
      locale-make-i18next
      locale-make-gnu
    '')
    (writeShellScriptBin "locale-pipeline-with-download" ''
      set -e
      locale-download
      locale-pipeline
    '')

    # -- Wiki-tags
    (writeShellScriptBin "wiki-tags-update" ''
      python scripts/wiki_tags_update.py
    '')

    # -- Supervisor
    (writeShellScriptBin "dev-start" ''
      set -e
      [ -d data/postgres ] || \
        initdb -D data/postgres \
          --no-instructions \
          --locale=C.UTF-8 \
          --encoding=UTF8 \
          --text-search-config=pg_catalog.simple \
          --auth=password \
          --username=postgres \
          --pwfile=<(echo postgres)
      mkdir -p data/supervisor
      supervisord -c config/supervisord.conf
      echo "Supervisor started"
    '')
    (writeShellScriptBin "dev-stop" ''
      set -e
      if [ -f data/supervisor/supervisord.pid ]; then
        kill -INT $(cat data/supervisor/supervisord.pid)
        echo "Supervisor stopped"
      else
        echo "Supervisor is not running"
      fi
    '')
    (writeShellScriptBin "dev-restart" ''
      set -e
      if [ -f data/supervisor/supervisord.pid ]; then
        kill -HUP $(cat data/supervisor/supervisord.pid)
        echo "Supervisor restarted"
      else
        dev-start
      fi
    '')
    (writeShellScriptBin "dev-clean" ''
      set -e
      dev-stop
      rm -rf data/postgres
    '')
    (writeShellScriptBin "dev-postgres-logs" "tail -f data/supervisor/postgres.log")
    (writeShellScriptBin "dev-redis-logs" "tail -f data/supervisor/redis.log")
    (writeShellScriptBin "dev-supervisord-logs" "tail -f data/supervisor/supervisord.log")

    # -- Watchers
    (writeShellScriptBin "watch-sass" "bun run watch:sass")
    (writeShellScriptBin "watch-tests" "ptw --now . --cov app --cov-report xml")
    (writeShellScriptBin "watch-locale" ''
      locale-pipeline
      while inotifywait -e close_write config/locale/extra_en.yaml; do
        locale-pipeline
      done
    '')

    # -- Misc
    (writeShellScriptBin "nixpkgs-update" ''
      set -e
      hash=$(git ls-remote https://github.com/NixOS/nixpkgs nixpkgs-23.11-darwin | cut -f 1)
      sed -i -E "s|/nixpkgs/archive/[0-9a-f]{40}\.tar\.gz|/nixpkgs/archive/$hash.tar.gz|" shell.nix
      echo "Nixpkgs updated to $hash"
    '')
    (writeShellScriptBin "docker-build-push" ''
      set -e
      cython-clean && cython-build
      if command -v podman &> /dev/null; then docker() { podman "$@"; } fi
      docker push $(docker load < "$(nix-build --no-out-link)" | sed -n -E 's/Loaded image: (\S+)/\1/p')
    '')
    (writeShellScriptBin "load-osm" ''
      python scripts/load_osm.py $(find . -maxdepth 1 -name '*.osm' -print -quit)
    '')
  ];

  shell' = with pkgs; lib.optionalString isDevelopment ''
    [ ! -e .venv/bin/python ] && [ -h .venv/bin/python ] && rm -r .venv

    echo "Installing Python dependencies"
    export POETRY_VIRTUALENVS_IN_PROJECT=1
    poetry install --compile

    echo "Installing Bun dependencies"
    bun install

    echo "Activating Python virtual environment"
    source .venv/bin/activate

    export LD_LIBRARY_PATH="${lib.makeLibraryPath libraries'}"

    # Development environment variables
    export PYTHONNOUSERSITE=1
    export TZ="UTC"

    export TEST_ENV=1
    export HTTPS_ONLY=0
    export POSTGRES_LOG=1
    export APP_URL="http://127.0.0.1:3000"
    export API_URL="http://127.0.0.1:3000"
    export ID_URL="http://127.0.0.1:3000"
    export OVERPASS_INTERPRETER_URL="https://overpass.monicz.dev/api/interpreter"
    export RAPID_URL="http://127.0.0.1:3000"
    export SECRET="development-secret"

    if [ -f .env ]; then
      echo "Loading .env file"
      set -o allexport
      source .env set
      +o allexport
    fi
  '' + lib.optionalString (!isDevelopment) ''
    make-version
  '';
in
pkgs.mkShell {
  libraries = libraries';
  buildInputs = libraries' ++ packages';
  shellHook = shell';
}
