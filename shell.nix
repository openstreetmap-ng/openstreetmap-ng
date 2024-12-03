{ isDevelopment ? true }:

let
  # Update packages with `nixpkgs-update` command
  pkgs = import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/af51545ec9a44eadf3fe3547610a5cdd882bc34e.tar.gz") { };

  projectDir = builtins.toString ./.;
  preCommitConf = import ./config/pre-commit-config.nix { inherit pkgs; };
  preCommitHook = import ./config/pre-commit-hook.nix { inherit pkgs projectDir preCommitConf; };
  supervisordConf = import ./config/supervisord.nix { inherit pkgs projectDir; };

  wrapPrefix = if (!pkgs.stdenv.isDarwin) then "LD_LIBRARY_PATH" else "DYLD_LIBRARY_PATH";
  pythonLibs = with pkgs; [
    cairo.out
    file.out
    libxml2.out
    libyaml.out
    zlib.out
    stdenv.cc.cc.lib
  ];
  python' = with pkgs; symlinkJoin {
    name = "python";
    paths = [
      # Enable compiler optimizations when in production
      (if isDevelopment then python313 else python313.override { enableOptimizations = true; })
    ];
    buildInputs = [ makeWrapper ];
    postBuild = ''
      wrapProgram "$out/bin/python3.13" --prefix ${wrapPrefix} : "${lib.makeLibraryPath pythonLibs}"
    '';
  };
  watchexec' = makeScript "watchexec" ''
    exec ${pkgs.watchexec}/bin/watchexec --wrap-process=none "$@"
  '';

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
    findutils
    curl
    watchexec'
    brotli
    zstd
    nil
    nixpkgs-fmt
    # Python:
    python'
    uv
    ruff
    gcc14
    gettext
    protobuf
    # Frontend:
    bun
    biome
    # Services:
    (postgresql_17_jit.withPackages (ps: [ ps.postgis ]))
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
    (makeScript "cython-build" "python scripts/cython_build.py build_ext --inplace --parallel \"$(nproc --all)\"")
    (makeScript "cython-clean" ''
      rm -rf build/
      dirs=(app scripts)
      find "''${dirs[@]}" \
        -type f \
        \( -name '*.c' -o -name '*.html' -o -name '*.so' \) \
        -not \
        \( -path 'app/static/*' -o -path 'app/templates/*' \) \
        -delete
    '')
    (makeScript "watch-cython" "exec watchexec -o queue -w app --exts py cython-build")

    # -- SASS
    (makeScript "sass-pipeline" ''
      bun run sass \
        --quiet-deps \
        --silence-deprecation=import \
        --style compressed \
        --load-path node_modules \
        --no-source-map \
        app/static/sass:app/static/css
      bun run postcss \
        app/static/css/**/*.css \
        --use autoprefixer \
        --replace \
        --no-map
    '')
    (makeScript "watch-sass" "exec watchexec -o queue -w app/static/sass sass-pipeline")

    # -- JavaScript
    (makeScript "node" "exec bun \"$@\"")
    (makeScript "js-pipeline" ''
      if [ "$1" = "hash" ]; then
        echo "[js-pipeline] Working in hash mode"
        mode_hash=1
      fi

      dir=app/static/js
      generated="$dir/_generated"
      find "$dir" \
        -maxdepth 1 \
        -type f \
        -name "bundle-*" \
        -delete
      bun run babel \
        --extensions ".ts" \
        --delete-dir-on-start \
        --out-dir "$generated" \
        "$dir"
      files=$(find "$generated" \
        -maxdepth 1 \
        -type f \
        -name "*.js" \
        -not -name "_*")

      if [ -n "$mode_hash" ]; then
        bun_args=(
          --minify
          --sourcemap=linked
        )
      else
        bun_args=(
          --minify-syntax --minify-whitespace
          --sourcemap=inline
        )
      fi
      exec 5>&1
      # shellcheck disable=SC2086
      output=$(
        bun build \
          "''${bun_args[@]}" \
          --entry-naming "[dir]/bundle-[name].[ext]" \
          --outdir "$dir" \
          $files | tee >(cat - >&5))

      if [ -n "$mode_hash" ]; then
        for file in $files; do
          file_name="''${file##*/}"
          file_stem="''${file_name%.js}"
          bundle_name=$(
            grep --only-matching --extended-regexp --max-count 1 \
            "bundle-$file_stem-\w{8}\.js" <<< "$output") || true

          if [ -z "$bundle_name" ]; then
            echo "ERROR: Failed to match bundle name for $file"
            exit 1
          fi

          # TODO: sed replace
          # echo "Replacing $file_name with $bundle_name"
        done
      fi
    '')
    (makeScript "watch-js" "exec watchexec -o queue -w app/static/js -i 'bundle-*' -i '**/_generated/**' js-pipeline")

    # -- Static
    (makeScript "static-img-clean" "rm -rf app/static/img/element/_generated")
    (makeScript "static-img-pipeline" "python scripts/rasterize.py static-img-pipeline")
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
    (makeScript "locale-make-i18next" "python scripts/locale_make_i18next.py")
    (makeScript "locale-make-gnu" "python scripts/locale_make_gnu.py")
    (makeScript "locale-pipeline" ''
      locale-postprocess
      locale-make-i18next &
      locale-make-gnu &
      wait
    '')
    (makeScript "locale-pipeline-with-download" ''
      set -x
      locale-download
      locale-pipeline
    '')
    (makeScript "watch-locale" "exec watchexec -o queue -w config/locale/extra_en.yaml locale-pipeline")

    # -- Protobuf
    (makeScript "proto-pipeline" ''
      mkdir -p app/static/js/proto
      protoc \
        -I app/models/proto \
        --plugin=node_modules/.bin/protoc-gen-es \
        --es_out app/static/js/proto \
        --es_opt target=ts \
        --python_out app/models/proto \
        --pyi_out app/models/proto \
        app/models/proto/*.proto
    '')
    (makeScript "watch-proto" "exec watchexec -o queue -w app/models/proto --exts proto proto-pipeline")

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
        kill -TERM "$pid"
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
      cp --archive --link --force data/preload/*.csv.zst "data/preload/$dataset/"
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
      remote_checksums=$(curl --silent --location "$remote_check_url")
      names=$(grep --only-matching --perl-regexp '[^/]+(?=\.csv\.zst)' <<< "$remote_checksums")

      mkdir -p "data/preload/$dataset"
      for name in $names; do
        remote_url="https://files.monicz.dev/openstreetmap-ng/preload/$dataset/$name.csv.zst"
        local_file="data/preload/$dataset/$name.csv.zst"
        local_check_file="data/preload/$dataset/$name.csv.zst.sha256"

        # recompute checksum if missing but file exists
        if [ -f "$local_file" ] && [ ! -f "$local_check_file" ]; then
          sha256sum "$local_file" | cut -d' ' -f1 > "$local_check_file"
        fi

        # compare with remote checksum
        remote_checksum=$(grep "$local_file" <<< "$remote_checksums" | cut -d' ' -f1)
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
      term_output=0
      extended_tests=0
      for arg in "$@"; do
        case "$arg" in
          --term)
            term_output=1
            ;;
          --extended)
            extended_tests=1
            ;;
          *)
            echo "Unknown argument: $arg"
            echo "Usage: $0 [--extended] [--term]"
            exit 1
            ;;
        esac
      done

      set +e
      COVERAGE_CORE=sysmon python -m coverage run -m pytest \
        --verbose \
        --no-header \
        "$([ "$extended_tests" = "1" ] && echo "--extended")"
      result=$?
      set -e

      if [ "$term_output" = "1" ]; then
        python -m coverage report --skip-covered
      else
        python -m coverage xml --quiet
      fi
      python -m coverage erase
      exit $result
    '')
    (makeScript "watch-tests" "exec watchexec -w app -w tests --exts py run-tests")

    # -- Misc
    (makeScript "run" ''
      python -m uvicorn app.main:main \
        --reload \
        --reload-include "*.mo" \
        --reload-exclude scripts \
        --reload-exclude tests \
        --reload-exclude typings
    '')
    (makeScript "format" ''
      set +e
      ruff check . --fix
      python -m pre_commit run -c ${preCommitConf} --all-files
    '')
    (makeScript "pyright" "bunx pyright")
    (makeScript "feature-icons-popular-update" "python scripts/feature_icons_popular_update.py")
    (makeScript "replication" "python scripts/replication.py")
    (makeScript "timezone-bbox-update" "python scripts/timezone_bbox_update.py")
    (makeScript "wiki-pages-update" "python scripts/wiki_pages_update.py")
    (makeScript "open-mailpit" "python -m webbrowser http://127.0.0.1:8025")
    (makeScript "open-app" "python -m webbrowser http://127.0.0.1:8000")
    (makeScript "nixpkgs-update" ''
      hash=$(
        curl --silent --location \
        https://prometheus.nixos.org/api/v1/query \
        -d "query=channel_revision{channel=\"nixpkgs-unstable\"}" | \
        grep --only-matching --extended-regexp "[0-9a-f]{40}")
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
  ];

  shell' = with pkgs; ''
    export SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt
    export PYTHONNOUSERSITE=1
    export PYTHONPATH=""
    export TZ=UTC

    current_python=$(readlink -e .venv/bin/python || echo "")
    current_python=''${current_python%/bin/*}
    [ "$current_python" != "${python'}" ] && rm -rf .venv/

    echo "Installing Python dependencies"
    export UV_COMPILE_BYTECODE=1
    export UV_PYTHON="${python'}/bin/python"
    uv sync --frozen

    echo "Installing Bun dependencies"
    export DO_NOT_TRACK=1
    bun install --frozen-lockfile

    echo "Activating Python virtual environment"
    source .venv/bin/activate

    if [ -d .git ]; then
      echo "Installing pre-commit hooks"
      python -m pre_commit install -c ${preCommitConf} --overwrite
      cp --force --symbolic-link ${preCommitHook}/bin/pre-commit-hook .git/hooks/pre-commit
    fi

    export TEST_ENV=1
    export SECRET=development-secret
    export APP_URL=http://127.0.0.1:8000
    export SMTP_HOST=127.0.0.1
    export SMTP_PORT=1025
    export SMTP_USER=mail@openstreetmap.org
    export SMTP_PASS=anything
    export NOMINATIM_URL=https://nominatim.monicz.dev
    export OVERPASS_INTERPRETER_URL=https://overpass.monicz.dev/api/interpreter
    export GITHUB_OAUTH_PUBLIC=Ov23lidLgxluuWuo0PNn
    export GITHUB_OAUTH_SECRET=4ed29823ee9d975e9f42a14e5c3d4b8293041cda
    export GOOGLE_OAUTH_PUBLIC=329628600169-6du7d20fo0poong0aqttuikstq97bten.apps.googleusercontent.com
    export GOOGLE_OAUTH_SECRET=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
    export GRAPHHOPPER_API_KEY=e6d61235-3e37-4290-91a7-d7be9e5a8909
    export MICROSOFT_OAUTH_PUBLIC=db54bdb3-08af-481b-9641-39f49065b640
    export WIKIMEDIA_OAUTH_PUBLIC=2f7fe9e2825acc816d1e1103d203e8ec
    export WIKIMEDIA_OAUTH_SECRET=d07aaeabb5f7a5de76e3d667db3dfe0b2a5abf11
    export LEGACY_HIGH_PRECISION_TIME=1
    export LEGACY_SEQUENCE_ID_MARGIN=1

    if [ -f .env ]; then
      echo "Loading .env file"
      set -o allexport
      source .env set
      set +o allexport
    else
      echo "Skipped loading .env file (not found)"
    fi

    echo "Running [proto-pipeline]"
    proto-pipeline &
    echo "Running [locale-pipeline]"
    locale-pipeline &
    echo "Running [static-img-pipeline]"
    static-img-pipeline &
    wait
  '' + lib.optionalString (!isDevelopment) ''
    make-version
  '';
in
pkgs.mkShellNoCC {
  packages = packages';
  shellHook = shell';
}
