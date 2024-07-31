{ isDevelopment ? true }:

let
  # Update packages with `nixpkgs-update` command
  pkgs = import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/6af55cb91ca2005516b9562f707bb99c8f79bf77.tar.gz") { };

  projectDir = builtins.toString ./.;
  preCommitConf = import ./config/pre-commit-config.nix { inherit pkgs; };
  preCommitHook = import ./config/pre-commit-hook.nix { inherit pkgs projectDir preCommitConf; };
  supervisordConf = import ./config/supervisord.nix { inherit pkgs projectDir; };

  wrapPrefix = if (!pkgs.stdenv.isDarwin) then "LD_LIBRARY_PATH" else "DYLD_LIBRARY_PATH";
  pythonLibs = with pkgs; [
    stdenv.cc.cc.lib
    file.out
    libxml2.out
    libyaml.out
    zlib.out
  ];
  python' = with pkgs; (symlinkJoin {
    name = "python";
    paths = [
      # Enable compiler optimizations when in production
      (if isDevelopment then python312 else python312.override { enableOptimizations = true; })
    ];
    buildInputs = [ makeWrapper ];
    postBuild = ''
      wrapProgram "$out/bin/python3.12" --prefix ${wrapPrefix} : "${lib.makeLibraryPath pythonLibs}"
    '';
  });
  fswatch' = with pkgs; (symlinkJoin {
    # Locale workaround for https://github.com/emcrisostomo/fswatch/issues/166
    name = "fswatch";
    paths = [ fswatch ];
    buildInputs = [ makeWrapper ];
    postBuild = ''
      wrapProgram "$out/bin/fswatch" \
        --set LC_ALL POSIX \
        --set LANG POSIX \
        --add-flags "-1 --latency 0.1 --event Updated"
    '';
  });

  # https://github.com/NixOS/nixpkgs/blob/nixpkgs-unstable/pkgs/build-support/trivial-builders/default.nix
  makeScript = with pkgs; name: text:
    writeTextFile {
      inherit name;
      executable = true;
      destination = "/bin/${name}";
      text = ''
        #!${runtimeShell} -e
        shopt -s globstar
        cd "${projectDir}"
        ${text}
      '';
      checkPhase = ''
        ${stdenv.shellDryRun} "$target"
        ${shellcheck}/bin/shellcheck --severity=style "$target"
      '';
      meta.mainProgram = name;
    };

  packages' = with pkgs; [
    coreutils
    curl
    fswatch'
    brotli
    zstd
    nil
    nixpkgs-fmt
    # Python:
    python'
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
    (makeScript "alembic-migration" ''
      name="$1"
      if [ -z "$name" ]; then read -rp "Database migration name: " name; fi
      python -m alembic -c config/alembic.ini revision --autogenerate --message "$name"
    '')
    (makeScript "alembic-upgrade" ''
      lataest_version=4
      current_version=$(cat data/alembic/version.txt 2> /dev/null || echo "")
      if [ -n "$current_version" ] && [ "$current_version" -ne "$lataest_version" ]; then
        echo "NOTICE: Database migrations are not compatible"
        echo "NOTICE: Run 'dev-clean' to reset the database before proceeding"
        exit 1
      fi
      python -m alembic -c config/alembic.ini upgrade head
      echo $lataest_version > data/alembic/version.txt
    '')

    # -- Cython
    (makeScript "cython-build" ''
      python setup.py build_ext --inplace --parallel "$(nproc --all)"
    '')
    (makeScript "cython-clean" ''
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
      find "''${dirs[@]}" -type f \( -name '*.c' -o -name '*.html' -o -name '*.so' \) -delete
    '')
    (makeScript "watch-cython" ''
      cython-build || true
      while ${fswatch'}/bin/fswatch --recursive --include "\.py$" app; do
        cython-build || true
      done
    '')

    # -- SASS
    (makeScript "sass-pipeline" ''
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
    (makeScript "watch-sass" ''
      sass-pipeline || true
      while ${fswatch'}/bin/fswatch --recursive app/static/sass; do
        sass-pipeline || true
      done
    '')

    # -- JavaScript
    (makeScript "js-pipeline" ''
      files=$(find app/static/js \
        -maxdepth 1 \
        -type f \
        -name "*.js" \
        -not -name "_*" \
        -not -name "bundle-*")
      # TODO: --sourcemap=inline when https://github.com/oven-sh/bun/issues/7427
      # shellcheck disable=SC2086
      bun build \
        --entry-naming "[dir]/bundle-[name].[ext]" \
        --outdir app/static/js \
        $files
    '')
    (makeScript "watch-js" ''
      js-pipeline || true
      while ${fswatch'}/bin/fswatch --recursive --exclude "^bundle-" app/static/js; do
        js-pipeline || true
      done
    '')

    # -- Static
    (makeScript "static-precompress" ''
      dirs=(
        app/static
        config/locale/i18next
        node_modules/iD/dist
        node_modules/@rapideditor/rapid/dist
      )
      files=$(find "''${dirs[@]}" \
        -type f \
        -not -name "*.br" \
        -not -name "*.zst" \
        -size +1023c)
      for file in $files; do
        echo "Compressing $file"
        file_size=$(stat --printf="%s" "$file")
        min_size=$(( file_size * 9 / 10 ))

        zstd \
          --force \
          --ultra -22 \
          --quiet \
          "$file"
        file_compressed="$file.zst"
        file_compressed_size=$(stat --printf="%s" "$file_compressed")
        if [ "$file_compressed_size" -gt $min_size ]; then
          echo "Removing $file_compressed (not compressible)"
          rm "$file_compressed"
        fi

        brotli \
          --force \
          --best \
          "$file"
        file_compressed="$file.br"
        file_compressed_size=$(stat --printf="%s" "$file_compressed")
        if [ "$file_compressed_size" -gt $min_size ]; then
          echo "Removing $file_compressed (not compressible)"
          rm "$file_compressed"
        fi
      done
    '')

    # -- Locale
    (makeScript "locale-clean" "rm -rf config/locale/*/")
    (makeScript "locale-download" "python scripts/locale_download.py")
    (makeScript "locale-postprocess" "python scripts/locale_postprocess.py")
    (makeScript "locale-make-i18next" ''
      rm -rf config/locale/i18next/
      python scripts/locale_make_i18next.py
    '')
    (makeScript "locale-make-gnu" ''
      mkdir -p config/locale/gnu
      echo "Converting to GNU gettext format"

      for file in config/locale/postprocess/*.json; do
        locale="''${file##*/}"
        locale="''${locale%.json}"
        target_file="config/locale/gnu/$locale/LC_MESSAGES/messages.po"
        target_file_bin="''${target_file%.po}.mo"

        if [ ! -f "$target_file_bin" ] || [ "$file" -nt "$target_file_bin" ]; then
          target_dir="''${target_file%/*}"
          mkdir -p "$target_dir"

          bunx i18next-conv \
            --quiet \
            --language "$locale" \
            --source "$file" \
            --target "$target_file" \
            --keyseparator "." \
            --ctxSeparator "__" \
            --compatibilityJSON "v4"

          # convert format to python-style:
          sed -i -E "s/\{\{/{/g; s/\}\}/}/g" "$target_file"

          msgfmt "$target_file" --output-file "$target_file_bin"
          touch -r "$file" "$target_file" "$target_file_bin"
          echo "Generating GNU locale... $locale"
        fi
      done
    '')
    (makeScript "locale-pipeline" ''
      set -x
      locale-postprocess
      locale-make-i18next
      locale-make-gnu
    '')
    (makeScript "locale-pipeline-with-download" ''
      set -x
      locale-download
      locale-pipeline
    '')
    (makeScript "watch-locale" ''
      locale-pipeline || true
      while ${fswatch'}/bin/fswatch config/locale/extra_en.yaml; do
        locale-pipeline || true
      done
    '')

    # -- Supervisor
    (makeScript "dev-start" ''
      pid=$(cat data/supervisor/supervisord.pid 2> /dev/null || echo "")
      if [ -n "$pid" ] && grep -q "supervisord" "/proc/$pid/cmdline" 2> /dev/null; then
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

      mkdir -p data/alembic data/mailpit data/postgres_unix data/supervisor
      python -m supervisor.supervisord -c ${supervisordConf}
      echo "Supervisor started"

      echo "Waiting for Postgres to start..."
      time_start=$(date +%s)
      while ! pg_isready -q -h "${projectDir}/data/postgres_unix"; do
        elapsed=$(($(date +%s) - time_start))
        if [ "$elapsed" -gt 10 ]; then
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
    (makeScript "dev-stop" ''
      pid=$(cat data/supervisor/supervisord.pid 2> /dev/null || echo "")
      if [ -n "$pid" ] && grep -q "supervisord" "/proc/$pid/cmdline" 2> /dev/null; then
        kill -INT "$pid"
        echo "Supervisor stopping..."
        while kill -0 "$pid" 2> /dev/null; do sleep 0.1; done
        echo "Supervisor stopped"
      else
        echo "Supervisor is not running"
      fi
    '')
    (makeScript "dev-restart" ''
      set -x
      dev-stop
      dev-start
    '')
    (makeScript "dev-clean" ''
      dev-stop
      rm -rf data/alembic/ data/postgres/ data/postgres_unix/
    '')
    (makeScript "dev-logs-postgres" "tail -f data/supervisor/postgres.log")
    (makeScript "dev-logs-watch-js" "tail -f data/supervisor/watch-js.log")
    (makeScript "dev-logs-watch-locale" "tail -f data/supervisor/watch-locale.log")
    (makeScript "dev-logs-watch-sass" "tail -f data/supervisor/watch-sass.log")

    # -- Preload
    (makeScript "preload-clean" "rm -rf data/preload/")
    (makeScript "preload-convert" ''
      python scripts/preload_convert.py
      for file in data/preload/*.csv; do
        zstd \
          --rm \
          --force -19 \
          --threads "$(( $(nproc) * 2 ))" \
          "$file"
      done
    '')
    (makeScript "preload-upload" ''
      read -rp "Preload dataset name: " dataset
      if [ "$dataset" != "poland" ] && [ "$dataset" != "mazowieckie" ]; then
        echo "Invalid dataset name, must be one of: poland, mazowieckie"
        exit 1
      fi
      mkdir -p "data/preload/$dataset"
      cp --archive --link data/preload/*.csv.zst "data/preload/$dataset/"
      echo "Computing checksums.sha256 file"
      sha256sum "data/preload/$dataset/"*.csv.zst > "data/preload/$dataset/checksums.sha256"
      rsync \
        --verbose \
        --archive \
        --whole-file \
        --delay-updates \
        --human-readable \
        --progress \
        "data/preload/$dataset/"*.csv.zst \
        "data/preload/$dataset/checksums.sha256" \
        edge:"/var/www/files.monicz.dev/openstreetmap-ng/preload/$dataset/"
    '')
    (makeScript "preload-download" ''
      echo "Available preload datasets:"
      echo "  * poland: Country of Poland; 6 GB download; 320 GB disk space; 1-2 hours"
      echo "  * mazowieckie: Masovian Voivodeship; 1 GB download; 60 GB disk space; 15-30 minutes"
      read -rp "Preload dataset name [default: mazowieckie]: " dataset
      dataset="''${dataset:-mazowieckie}"
      if [ "$dataset" != "poland" ] && [ "$dataset" != "mazowieckie" ]; then
        echo "Invalid dataset name, must be one of: poland, mazowieckie"
        exit 1
      fi

      echo "Checking for preload data updates"
      remote_check_url="https://files.monicz.dev/openstreetmap-ng/preload/$dataset/checksums.sha256"
      remote_checsums=$(curl --silent --location "$remote_check_url")

      mkdir -p "data/preload/$dataset"
      for name in "user" "changeset" "element" "element_member"; do
        remote_url="https://files.monicz.dev/openstreetmap-ng/preload/$dataset/$name.csv.zst"
        local_file="data/preload/$dataset/$name.csv.zst"
        local_check_file="data/preload/$dataset/$name.csv.zst.sha256"

        # recompute checksum if missing but file exists
        if [ -f "$local_file" ] && [ ! -f "$local_check_file" ]; then
          sha256sum "$local_file" | cut -d' ' -f1 > "$local_check_file"
        fi

        # compare with remote checksum
        remote_checksum=$(grep "$local_file" <<< "$remote_checsums" | cut -d' ' -f1)
        local_checksum=$(cat "$local_check_file" 2> /dev/null || echo "x")
        if [ "$remote_checksum" = "$local_checksum" ]; then
          echo "File $local_file is up to date"
          continue
        fi

        echo "Downloading $name preload data"
        curl --location "$remote_url" -o "$local_file"

        # recompute checksum
        local_checksum=$(sha256sum "$local_file" | cut -d' ' -f1)
        echo "$local_checksum" > "$local_check_file"
        if [ "$remote_checksum" != "$local_checksum" ]; then
          echo "[!] Checksum mismatch for $local_file"
          echo "[!] Please retry this command after a few minutes"
          exit 1
        fi
      done
      cp --archive --link "data/preload/$dataset/"*.csv.zst data/preload/
    '')
    (makeScript "preload-load" "python scripts/preload_load.py")
    (makeScript "preload-pipeline" ''
      set -x
      preload-download
      dev-start
      preload-load
    '')

    # -- Testing
    (makeScript "run-tests" ''
      python -m pytest . \
        --verbose \
        --no-header \
        --cov app \
        --cov-report "''${1:-xml}"
    '')
    (makeScript "watch-tests" ''
      run-tests || true
      while ${fswatch'}/bin/fswatch --recursive --include "\.py$" .; do
        run-tests || true
      done
    '')

    # -- Misc
    (makeScript "run" "python -m uvicorn app.main:main --reload")
    (makeScript "format" ''
      set +e
      ruff check . --fix
      python -m pre_commit run -c ${preCommitConf} --all-files
    '')
    (makeScript "pyright" "bun run pyright")
    (makeScript "feature-icons-popular-update" "python scripts/feature_icons_popular_update.py")
    (makeScript "timezone-bbox-update" "python scripts/timezone_bbox_update.py")
    (makeScript "wiki-pages-update" "python scripts/wiki_pages_update.py")
    (makeScript "open-mailpit" "python -m webbrowser http://127.0.0.1:8025")
    (makeScript "open-app" "python -m webbrowser http://127.0.0.1:8000")
    (makeScript "nixpkgs-update" ''
      hash=$(git ls-remote https://github.com/NixOS/nixpkgs nixpkgs-unstable | cut -f 1)
      sed -i -E "s|/nixpkgs/archive/[0-9a-f]{40}\.tar\.gz|/nixpkgs/archive/$hash.tar.gz|" shell.nix
      echo "Nixpkgs updated to $hash"
    '')
    (makeScript "docker-build-push" ''
      cython-clean && cython-build
      if command -v podman &> /dev/null; then docker() { podman "$@"; } fi
      docker push "$(docker load < "$(nix-build --no-out-link)" | sed -n -E 's/Loaded image: (\S+)/\1/p')"
    '')
    (makeScript "make-version" ''
      version=$(date --iso-8601=seconds)
      echo "Setting application version to $version"
      sed -i -E "s|VERSION = '.*?'|VERSION = '$version'|" app/config.py
    '')
    (makeScript "make-bundle" ''
      dir=app/static/js

      find "$dir" \
        -maxdepth 1 \
        -type f \
        -name "bundle-*" \
        -delete

      bunx babel \
        --verbose \
        --keep-file-extension \
        --out-dir "$dir" \
        "$dir"

      files=$(find "$dir" \
        -maxdepth 1 \
        -type f \
        -name "*.js" \
        -not -name "_*")
      for file in $files; do
        file_name="''${file##*/}"
        file_stem="''${file_name%.js}"

        # TODO: --sourcemap=external when https://github.com/oven-sh/bun/issues/7427
        output=$(bun build \
          "$file" \
          --minify \
          --entry-naming "[dir]/bundle-[name]-[hash].[ext]" \
          --outdir "$dir" | tee /dev/stdout)

        bundle_name=$(grep \
          --only-matching \
          --extended-regexp \
          --max-count=1 \
          "bundle-$file_stem-[0-9a-f]{16}\.js" <<< "$output")
        if [ -z "$bundle_name" ]; then
          echo "ERROR: Failed to match bundle name for $file"
          exit 1
        fi

        # TODO: sed replace
        # echo "Replacing $file_name with $bundle_name"
      done
    '')
  ];

  shell' = with pkgs; ''
    current_python=$(readlink -e .venv/bin/python || echo "")
    current_python=''${current_python%/bin/*}
    [ "$current_python" != "${python'}" ] && rm -rf .venv/

    echo "Installing Python dependencies"
    poetry env use ${python'}/bin/python
    poetry install --compile

    echo "Installing Bun dependencies"
    bun install

    echo "Activating Python virtual environment"
    source .venv/bin/activate

    if [ -d .git ]; then
      echo "Installing pre-commit hooks"
      python -m pre_commit install -c ${preCommitConf} --overwrite
      cp --force --symbolic-link ${preCommitHook}/bin/pre-commit-hook .git/hooks/pre-commit
    fi

    # Development environment variables
    export PYTHONNOUSERSITE=1
    export TZ=UTC
    export PROJECT_DIR="${projectDir}"
    export TEST_ENV=1
    export SECRET=development-secret
    export APP_URL=http://127.0.0.1:8000
    export SMTP_HOST=127.0.0.1
    export SMTP_PORT=1025
    export SMTP_USER=mail@openstreetmap.org
    export SMTP_PASS=anything
    export NOMINATIM_URL=https://nominatim.monicz.dev
    export OVERPASS_INTERPRETER_URL=https://overpass.monicz.dev/api/interpreter
    export LEGACY_HIGH_PRECISION_TIME=1
    export LEGACY_SEQUENCE_ID_MARGIN=1

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
pkgs.mkShellNoCC {
  buildInputs = packages';
  shellHook = shell';
}
