{ isDevelopment ? true }:

let
  # Currently using nixpkgs-23.11-darwin
  # Update with `nixpkgs-update` command
  pkgs = import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/4f24018c731df5f1d522aefb0b9c958e2a701552.tar.gz") { };

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
    bun
    (postgresql_16_jit.withPackages (ps: [ ps.postgis ]))
    redis

    # Scripts
    # -- Misc
    (writeShellScriptBin "make-version" "sed -i -E \"s|VERSION_DATE = '.*?'|VERSION_DATE = '$(date +%y%m%d)'|\" app/config.py")
    (writeShellScriptBin "make-bundle" ''
      set -e
      dir="app/static/js"

      bundle_paths=$(find "$dir" \
        -maxdepth 1 \
        -type f \
        -name "bundle-*")

      [ -z "$bundle_paths" ] || rm $bundle_paths

      bunx babel \
        --verbose \
        --ignore "$dir/old/**" \
        --keep-file-extension \
        --out-dir "$dir" \
        "$dir"

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
          --sourcemap=external \
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

        echo "TODO: sed replace"
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
    curl
    zstd

    # Scripts
    # -- Cython
    (writeShellScriptBin "cython-build" "python setup.py build_ext --inplace --parallel $(nproc --all)")
    (writeShellScriptBin "cython-clean" ''
      set -e
      shopt -s globstar
      rm -rf build/
      dirs=(
        app/controllers
        app/exceptions
        app/exceptions06
        app/format06
        app/format07
        app/lib
        app/middlewares
        app/repositories
        app/responses
        app/services
        app/validators
      )
      for dir in "''${dirs[@]}"; do
        rm -rf "$dir"/**/*{.c,.html,.so}
      done
    '')

    # -- Alembic
    (writeShellScriptBin "alembic-migration" ''
      set -e
      name=$1
      if [ -z "$name" ]; then
        read -p "Database migration name: " name
      fi
      alembic -c config/alembic.ini revision --autogenerate --message "$name"
    '')
    (writeShellScriptBin "alembic-upgrade" "alembic -c config/alembic.ini upgrade head")

    # -- Locale
    (writeShellScriptBin "locale-clean" "rm -rf config/locale/*/")
    (writeShellScriptBin "locale-download" "python scripts/locale_download.py")
    (writeShellScriptBin "locale-postprocess" "python scripts/locale_postprocess.py")
    (writeShellScriptBin "locale-make-i18next" ''
      rm -rf config/locale/i18next
      python scripts/locale_make_i18next.py
    '')
    (writeShellScriptBin "locale-make-gnu" ''
      set -e
      mkdir -p config/locale/gnu
      echo "Converting to GNU gettext format"

      for source_file in config/locale/postprocess/*.json; do
        locale=$(basename "$source_file" .json)
        target_file="config/locale/gnu/$locale/LC_MESSAGES/messages.po"
        target_file_bin="''${target_file%.po}.mo"

        if [ ! -f "$target_file_bin" ] || [ "$source_file" -nt "$target_file_bin" ]; then
          mkdir -p "$(dirname "$target_file")"

          bunx i18next-conv \
            --quiet \
            --language "$locale" \
            --source "$source_file" \
            --target "$target_file" \
            --keyseparator "." \
            --ctxSeparator "__" \
            --compatibilityJSON "v4"

          # convert format to python-style
          sed -i -E 's/\{\{/{/g; s/\}\}/}/g' "$target_file"

          msgfmt "$target_file" --output-file "$target_file_bin";

          # preserve original timestamps
          touch -r "$source_file" "$target_file" "$target_file_bin"

          echo "[✅] $locale"
        fi
      done
    '')
    (writeShellScriptBin "locale-pipeline" ''
      set -ex
      locale-postprocess
      locale-make-i18next
      locale-make-gnu
    '')
    (writeShellScriptBin "locale-pipeline-with-download" ''
      set -ex
      locale-download
      locale-pipeline
    '')
    (writeShellScriptBin "watch-locale" ''
      locale-pipeline
      while inotifywait -e close_write config/locale/extra_en.yaml; do
        locale-pipeline
      done
    '')

    # -- Supervisor
    (writeShellScriptBin "dev-start" ''
      set -e
      pid=$(cat data/supervisor/supervisord.pid 2> /dev/null || echo "")
      if [ -n "$pid" ] && $(kill -0 "$pid" 2> /dev/null); then
        echo "Supervisor is already running"
        exit 0
      fi

      fresh_start=0
      if [ ! -d data/postgres ]; then
        initdb -D data/postgres \
          --no-instructions \
          --locale=C.UTF-8 \
          --encoding=UTF8 \
          --text-search-config=pg_catalog.simple \
          --auth=password \
          --username=postgres \
          --pwfile=<(echo postgres)
        fresh_start=1
      fi

      mkdir -p data/supervisor
      supervisord -c config/supervisord.conf
      echo "Supervisor started"

      if [ "$fresh_start" -eq 1 ]; then
        echo "This is a fresh start. Waiting for Postgres to start..."
        while ! pg_isready -q -h 127.0.0.1 -t 10; do sleep 0.1; done
        echo "Postgres started, running migrations"
        alembic-upgrade
      fi
    '')
    (writeShellScriptBin "dev-stop" ''
      set -e
      if [ -f data/supervisor/supervisord.pid ]; then
        pid=$(cat data/supervisor/supervisord.pid)
        kill -INT "$pid"
        echo "Supervisor stopping..."
        while $(kill -0 "$pid" 2> /dev/null); do sleep 0.1; done
        echo "Supervisor stopped"
      else
        echo "Supervisor is not running"
      fi
    '')
    (writeShellScriptBin "dev-restart" ''
      set -ex
      dev-stop
      dev-start
    '')
    (writeShellScriptBin "dev-clean" ''
      set -e
      dev-stop
      rm -rf data/postgres
    '')
    (writeShellScriptBin "dev-logs-postgres" "tail -f data/supervisor/postgres.log")
    (writeShellScriptBin "dev-logs-redis" "tail -f data/supervisor/redis.log")
    (writeShellScriptBin "dev-logs-supervisord" "tail -f data/supervisor/supervisord.log")
    (writeShellScriptBin "dev-logs-watch-js" "tail -f data/supervisor/watch-js.log")
    (writeShellScriptBin "dev-logs-watch-locale" "tail -f data/supervisor/watch-locale.log")
    (writeShellScriptBin "dev-logs-watch-sass" "tail -f data/supervisor/watch-sass.log")

    # -- Preload
    (writeShellScriptBin "preload-clean" "rm -rf data/preload")
    (writeShellScriptBin "preload-convert" "python scripts/preload_convert.py")
    (writeShellScriptBin "preload-compress" ''
      set -e
      for file in data/preload/*.csv; do
        zstd \
          --force \
          --compress -19 \
          --threads "$(( $(nproc) * 2 ))" \
          "$file" \
          -o "$file.zst"
      done
    '')
    (writeShellScriptBin "preload-download" ''
      set -e
      mkdir -p data/preload
      for name in "user" "changeset" "element"; do
        final_file="data/preload/$name.csv"

        if [ -f "$final_file" ]; then
          echo "File $final_file already exists. Skipping $name preload data download."
          continue
        fi

        echo "Downloading $name preload data"
        curl \
          --location \
          "https://files.monicz.dev/openstreetmap-ng/preload/$name.csv.zst" \
          -o "data/preload/$name.csv.zst"

        echo "Decompressing"
        zstd \
          --force \
          --decompress \
          --rm \
          "data/preload/$name.csv.zst" \
          -o "data/preload/$name.csv.tmp"

        mv "data/preload/$name.csv.tmp" "$final_file"
      done
    '')
    (writeShellScriptBin "preload-load" "python scripts/preload_load.py")
    (writeShellScriptBin "preload-pipeline" ''
      set -ex
      preload-download
      dev-start
      preload-load
    '')

    # -- SASS
    (writeShellScriptBin "sass-pipeline" ''
      set -e
      shopt -s globstar
      sass \
        --style compressed \
        --load-path node_modules \
        --no-source-map \
        app/static/sass:app/static/css
      bunx postcss \
        app/static/css/**/*.css \
        --use autoprefixer \
        --replace \
        --no-map
    '')
    (writeShellScriptBin "watch-sass" ''
      shopt -s globstar
      sass-pipeline
      while inotifywait -e close_write app/static/sass/**/*.scss; do
        sass-pipeline
      done
    '')

    # -- Misc
    (writeShellScriptBin "watch-js" ''
      while true; do
        bun build \
          --watch \
          --entry-naming "[dir]/bundle-[name].[ext]" \
          --sourcemap=inline \
          --outdir app/static/js \
          app/static/js/id.js app/static/js/main.js app/static/js/matomo.js app/static/js/rapid.js
        echo "Bun exit unexpectedly, restarting..."
        sleep 2
      done
    '')
    (writeShellScriptBin "watch-tests" "ptw --now . --cov app --cov-report xml")
    (writeShellScriptBin "timezone-bbox-update" "python scripts/timezone_bbox_update.py")
    (writeShellScriptBin "wiki-pages-update" "python scripts/wiki_pages_update.py")
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
    export AUTHLIB_INSECURE_TRANSPORT=1
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
