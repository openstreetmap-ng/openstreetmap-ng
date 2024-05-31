{ isDevelopment ? true }:

let
  # Update packages with `nixpkgs-update` command
  pkgs = import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/14de0380da76de3f4cd662a9ef2352eed0c95b7d.tar.gz") { };

  supervisordConf = import ./config/supervisord.nix { inherit pkgs; };

  pythonLibs = with pkgs; [
    stdenv.cc.cc.lib
    file.out
    libxml2.out
    libyaml.out
    zlib.out
  ];
  wrappedPython = with pkgs; (symlinkJoin {
    name = "python";
    paths = [
      # Enable compiler optimizations when in production
      (if isDevelopment then python312 else python312.override { enableOptimizations = true; })
    ];
    buildInputs = [ makeWrapper ];
    postBuild = ''
      wrapProgram "$out/bin/python3.12" --prefix LD_LIBRARY_PATH : "${lib.makeLibraryPath pythonLibs}"
    '';
  });

  packages' = with pkgs; [
    coreutils
    curl
    fswatch
    brotli
    zstd
    # Python:
    wrappedPython
    poetry
    ruff
    gcc14
    gettext
    # Frontend:
    bun
    biome
    dart-sass
    # Services:
    (postgresql_16_jit.withPackages (ps: [ ps.postgis ]))
    valkey
    mailpit

    # Scripts:
    # -- Alembic
    (writeShellScriptBin "alembic-migration" ''
      set -e
      name=$1
      if [ -z "$name" ]; then
        read -p "Database migration name: " name
      fi
      python -m alembic -c config/alembic.ini revision --autogenerate --message "$name"
    '')
    (writeShellScriptBin "alembic-upgrade" "python -m alembic -c config/alembic.ini upgrade head")

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
        app/format
        app/lib
        app/middlewares
        app/responses
        app/services
        app/queries
        app/validators
      )
      for dir in "''${dirs[@]}"; do
        rm -rf "$dir"/**/*{.c,.html,.so}
      done
    '')
    (writeShellScriptBin "watch-cython" ''
      cython-build
      while fswatch -1 --latency 0.1 --event Updated --recursive --include "\.py$" app; do
        cython-build
      done
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
      sass-pipeline
      while fswatch -1 --latency 0.1 --event Updated --recursive app/static/sass; do
        sass-pipeline
      done
    '')

    # -- JavaScript
    (writeShellScriptBin "js-pipeline" ''
      set -e
      src_paths=$(find app/static/js \
        -maxdepth 1 \
        -type f \
        -name "*.js" \
        -not -name "_*" \
        -not -name "bundle-*")
      # TODO: --sourcemap=inline when https://github.com/oven-sh/bun/issues/7427
      bun build \
        --entry-naming "[dir]/bundle-[name].[ext]" \
        --outdir app/static/js \
        $src_paths
    '')
    (writeShellScriptBin "watch-js" ''
      js-pipeline
      while fswatch -1 --latency 0.1 --event Updated --recursive --exclude "^bundle-" app/static/js; do
        js-pipeline
      done
    '')

    # -- Static
    (writeShellScriptBin "static-precompress" ''
      set -e
      shopt -s globstar
      dirs=(
        app/static
        config/locale/i18next
        node_modules/iD/dist
        node_modules/@rapideditor/rapid/dist
      )
      for dir in "''${dirs[@]}"; do
        for file in "$dir"/**/*; do
          if [ ! -f "$file" ] || [[ "$file" == *.br ]] || [[ "$file" == *.zst ]]; then
            continue
          fi

          original_size=$(stat --printf="%s" "$file")
          if [ $original_size -lt 1024 ]; then
            continue
          fi

          echo "Compressing $file"
          min_size=$(( original_size * 9 / 10 ))

          zstd \
            --force -19 \
            --quiet \
            "$file"
          zst_size=$(stat --printf="%s" "$file.zst")
          if [ $zst_size -gt $min_size ]; then
            echo "$file.zst is not compressable"
            rm "$file.zst"
          fi

          brotli \
            --force \
            --best \
            "$file"
          br_size=$(stat --printf="%s" "$file.br")
          if [ $br_size -gt $min_size ]; then
            echo "$file.br is not compressable"
            rm "$file.br"
          fi
        done
      done
    '')

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

          # convert format to python-style:
          sed -i -E 's/\{\{/{/g; s/\}\}/}/g' "$target_file"

          msgfmt "$target_file" --output-file "$target_file_bin"
          touch -r "$source_file" "$target_file" "$target_file_bin"
          echo "Generating GNU locale... $locale"
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
      while fswatch -1 --latency 0.1 --event Updated config/locale/extra_en.yaml; do
        locale-pipeline
      done
    '')

    # -- Supervisor
    (writeShellScriptBin "dev-start" ''
      set -e
      pid=$(cat data/supervisor/supervisord.pid 2> /dev/null || echo "")
      if [ -n "$pid" ] && $(grep -q "supervisord" "/proc/$pid/cmdline" 2> /dev/null); then
        echo "Supervisor is already running"
        exit 0
      fi

      if [ ! -f data/postgres/PG_VERSION ]; then
        initdb -D data/postgres \
          --no-instructions \
          --locale-provider=icu \
          --icu-locale=und \
          --no-locale \
          --text-search-config=pg_catalog.simple \
          --auth=password \
          --username=postgres \
          --pwfile=<(echo postgres)
      fi

      mkdir -p /tmp/osm-postgres data/supervisor data/mailpit
      python -m supervisor.supervisord -c ${supervisordConf}
      echo "Supervisor started"

      echo "Waiting for Postgres to start..."
      time_start=$(date +%s)
      while ! pg_isready -q -h /tmp/osm-postgres; do
        elapsed=$(($(date +%s) - $time_start))
        if [ $elapsed -gt 10 ]; then
          tail -n 15 data/supervisor/supervisord.log data/supervisor/postgres.log
          echo "Postgres startup timeout, see above logs for details"
          dev-stop
          exit 1
        fi
        sleep 0.1
      done

      echo "Postgres started, running migrations"
      alembic-upgrade
    '')
    (writeShellScriptBin "dev-stop" ''
      set -e
      pid=$(cat data/supervisor/supervisord.pid 2> /dev/null || echo "")
      if [ -n "$pid" ] && $(grep -q "supervisord" "/proc/$pid/cmdline" 2> /dev/null); then
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
      rm -rf data/postgres data/mailpit
    '')
    (writeShellScriptBin "dev-logs-postgres" "tail -f data/supervisor/postgres.log")
    (writeShellScriptBin "dev-logs-watch-js" "tail -f data/supervisor/watch-js.log")
    (writeShellScriptBin "dev-logs-watch-locale" "tail -f data/supervisor/watch-locale.log")
    (writeShellScriptBin "dev-logs-watch-sass" "tail -f data/supervisor/watch-sass.log")

    # -- Preload
    (writeShellScriptBin "preload-clean" "rm -rf data/preload")
    (writeShellScriptBin "preload-convert" ''
      set -e
      python scripts/preload_convert.py
      for file in data/preload/*.csv; do
        zstd \
          --rm \
          --force -19 \
          --threads "$(( $(nproc) * 2 ))" \
          "$file"
      done
      sha256sum data/preload/*.csv.zst > data/preload/checksums.sha256
    '')
    (writeShellScriptBin "preload-upload" ''
      rsync \
        --verbose \
        --archive \
        --whole-file \
        --delay-updates \
        --human-readable \
        --progress \
        data/preload/*.csv.zst \
        data/preload/checksums.sha256 \
        edge:/var/www/files.monicz.dev/openstreetmap-ng/preload/
    '')
    (writeShellScriptBin "preload-download" ''
      set -e
      mkdir -p data/preload

      echo "Checking for preload data updates"
      remote_check_url="https://files.monicz.dev/openstreetmap-ng/preload/checksums.sha256"
      remote_checsums=$(curl --silent --location "$remote_check_url")

      for name in "user" "changeset" "element" "element_member"; do
        remote_url="https://files.monicz.dev/openstreetmap-ng/preload/$name.csv.zst"
        local_file="data/preload/$name.csv.zst"
        local_check_file="data/preload/$name.csv.zst.sha256"

        remote_checksum=$(grep "$local_file" <<< "$remote_checsums" | cut -d' ' -f1)
        local_checksum=$(cat "$local_check_file" 2> /dev/null || echo "x")
        if [ "$remote_checksum" = "$local_checksum" ]; then
          echo "File $local_file is up to date"
          continue
        fi

        echo "Downloading $name preload data"
        curl --location "$remote_url" -o "$local_file"

        local_checksum=$(sha256sum "$local_file" | cut -d' ' -f1)
        echo "$local_checksum" > "$local_check_file"
        if [ "$remote_checksum" != "$local_checksum" ]; then
          echo "[!] Checksum mismatch for $local_file"
          echo "[!] Please retry this command after a few minutes"
          exit 1
        fi
      done
    '')
    (writeShellScriptBin "preload-load" "python scripts/preload_load.py")
    (writeShellScriptBin "preload-pipeline" ''
      set -ex
      preload-download
      dev-start
      preload-load
    '')

    # -- Testing
    (writeShellScriptBin "run-tests" ''
      set -e
      python -m pytest . \
        --verbose \
        --no-header \
        --cov app \
        --cov-report "''${1:-xml}"
    '')
    (writeShellScriptBin "watch-tests" ''
      run-tests || true
      while fswatch -1 --latency 0.1 --event Updated --recursive --include "\.py$" .; do
        run-tests || true
      done
    '')

    # -- Misc
    (writeShellScriptBin "run" ''
      python -m uvicorn app.main:main --reload
    '')
    (writeShellScriptBin "feature-icons-popular-update" "python scripts/feature_icons_popular_update.py")
    (writeShellScriptBin "timezone-bbox-update" "python scripts/timezone_bbox_update.py")
    (writeShellScriptBin "wiki-pages-update" "python scripts/wiki_pages_update.py")
    (writeShellScriptBin "open-mailpit" "python -m webbrowser http://127.0.0.1:8025")
    (writeShellScriptBin "open-app" "python -m webbrowser http://127.0.0.1:8000")
    (writeShellScriptBin "nixpkgs-update" ''
      set -e
      hash=$(git ls-remote https://github.com/NixOS/nixpkgs nixpkgs-unstable | cut -f 1)
      sed -i -E "s|/nixpkgs/archive/[0-9a-f]{40}\.tar\.gz|/nixpkgs/archive/$hash.tar.gz|" shell.nix
      echo "Nixpkgs updated to $hash"
    '')
    (writeShellScriptBin "docker-build-push" ''
      set -e
      cython-clean && cython-build
      if command -v podman &> /dev/null; then docker() { podman "$@"; } fi
      docker push $(docker load < "$(nix-build --no-out-link)" | sed -n -E 's/Loaded image: (\S+)/\1/p')
    '')
    (writeShellScriptBin "make-version" "sed -i -E \"s|VERSION_DATE = '.*?'|VERSION_DATE = '$(date +%y%m%d)'|\" app/config.py")
    (writeShellScriptBin "make-bundle" ''
      set -e
      dir=app/static/js

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

        # TODO: --sourcemap=external when https://github.com/oven-sh/bun/issues/7427
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

        echo "TODO: sed replace"
        echo "Replacing $src_name with $bundle_name"
      done
    '')
  ];

  shell' = with pkgs; lib.optionalString isDevelopment ''
    current_python=$(readlink -e .venv/bin/python || echo "")
    current_python=''${current_python%/bin/*}
    [ "$current_python" != "${wrappedPython}" ] && rm -r .venv

    echo "Installing Python dependencies"
    poetry env use "${wrappedPython}/bin/python"
    poetry install --compile

    echo "Installing Bun dependencies"
    bun install

    echo "Activating Python virtual environment"
    source .venv/bin/activate

    # Development environment variables
    export PYTHONNOUSERSITE=1
    export TZ=UTC
    export TEST_ENV=1
    export SECRET=development-secret
    export APP_URL=http://127.0.0.1:8000
    export SMTP_HOST=127.0.0.1
    export SMTP_PORT=1025
    export SMTP_USER=mail@openstreetmap.org
    export SMTP_PASS=anything
    export OVERPASS_INTERPRETER_URL=https://overpass.monicz.dev/api/interpreter
    export LEGACY_HIGH_PRECISION_TIME=1
    export LEGACY_SEQUENCE_ID_MARGIN=1
    export AUTHLIB_INSECURE_TRANSPORT=1

    if [ -f .env ]; then
      echo "Loading .env file"
      set -o allexport
      source .env set
      set +o allexport
    fi

    if [ ! -f config/locale/gnu/pl/LC_MESSAGES/messages.mo ]; then
      echo "Running locale pipeline"
      locale-pipeline
    fi
  '' + lib.optionalString (!isDevelopment) ''
    make-version
  '';
in
pkgs.mkShell {
  buildInputs = packages';
  shellHook = shell';
}
