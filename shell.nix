{ isDevelopment ? true
, hostMemoryMb ? 8192
, hostDiskCoW ? false
, enablePostgres ? true
, postgresCpuThreads ? 8
, postgresMinWalSizeGb ? 1
, postgresMaxWalSizeGb ? 10
, postgresVerbose ? 2  # 0 = no, 1 = some, 2 = most
, enableValkey ? true
, enableMailpit ? true
, gunicornWorkers ? 1
, gunicornPort ? 8000
}:

let
  # Update packages with `nixpkgs-update` command
  pkgs = import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/d98abf5cf5914e5e4e9d57205e3af55ca90ffc1d.tar.gz") { };

  projectDir = builtins.toString ./.;
  postgresConf = import ./config/postgres.nix { inherit hostMemoryMb hostDiskCoW postgresCpuThreads postgresMinWalSizeGb postgresMaxWalSizeGb postgresVerbose pkgs projectDir; };
  preCommitConf = import ./config/pre-commit-config.nix { inherit pkgs; };
  preCommitHook = import ./config/pre-commit-hook.nix { inherit pkgs projectDir preCommitConf; };
  supervisordConf = import ./config/supervisord.nix { inherit isDevelopment enablePostgres enableValkey enableMailpit pkgs postgresConf; };

  stdenv' = pkgs.gcc14Stdenv;
  wrapPrefix = if (!stdenv'.isDarwin) then "LD_LIBRARY_PATH" else "DYLD_LIBRARY_PATH";
  pythonLibs = with pkgs; [
    cairo.out
    file.out
    libxml2.out
    libyaml.out
    zlib.out
    stdenv'.cc.cc.lib
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

  # local update until fixed upstream:
  # https://github.com/NixOS/nixpkgs/issues/383368
  timescaledb-parallel-copy' = pkgs.buildGoModule rec {
    pname = "timescaledb-parallel-copy";
    version = "0.9.0";
    doCheck = false;
    src = pkgs.fetchFromGitHub {
      owner = "timescale";
      repo = pname;
      rev = "v${version}";
      sha256 = "sha256-vd+2KpURyVhcVf2ESHcyZLJCw+z+WbnTJX9Uy4ZAPoE=";
    };
    vendorHash = "sha256-MRso2uihMUc+rLwljwZZR1+1cXADCNg+JUpRcRU918g=";
  };

  # https://github.com/NixOS/nixpkgs/blob/nixpkgs-unstable/pkgs/build-support/trivial-builders/default.nix
  makeScript = with pkgs; name: text:
    writeTextFile {
      inherit name;
      executable = true;
      destination = "/bin/${name}";
      text = ''
        #!${runtimeShell} -e
        shopt -s extglob nullglob globstar
        cd "${projectDir}"
        ${text}
      '';
      checkPhase = ''
        ${stdenv'.shellDryRun} "$target"
        ${shellcheck}/bin/shellcheck --severity=style "$target"
      '';
      meta.mainProgram = name;
    };

  packages' = with pkgs; [
    ps
    coreutils
    findutils
    parallel
    curl
    jq
    watchexec'
    brotli
    zstd
    b3sum
    nil
    nixpkgs-fmt
    # Python:
    python'
    uv
    ruff
    gettext
    protobuf
    # Frontend:
    bun
    biome
    # Services:
    (postgresql_17_jit.withPackages (ps: [ ps.postgis ])) # SOON: ps.timescaledb-apache
    timescaledb-parallel-copy'
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
      latest_version=6
      current_version=$(cat data/alembic/version.txt 2>/dev/null || echo "")
      if [ -n "$current_version" ] && [ "$current_version" -ne "$latest_version" ]; then
        echo "NOTICE: Database migrations are not compatible"
        echo "NOTICE: Run 'dev-clean' to reset the database before proceeding"
        exit 1
      fi
      python -m alembic -c config/alembic.ini upgrade head
      echo $latest_version > data/alembic/version.txt
    '')

    # -- Cython
    (makeScript "cython-build" "python scripts/cython_build.py build_ext --inplace --parallel \"$(nproc --all)\"")
    (makeScript "cython-build-pgo" ''
      found_so=false
      files_up_to_date=true
      while IFS= read -r so_file; do
        found_so=true
        py_file="''${so_file%.*.*}.py"
        if [ -f "$py_file" ] && [ "$py_file" -nt "$so_file" ]; then
          files_up_to_date=false
          break
        fi
      done < <(find . -type f -name "*.so" -not -path './.*')
      if [ "$found_so" = true ] && [ "$files_up_to_date" = true ]; then
        echo "All cython modules are up-to-date, skipping PGO build"
        exit 0
      fi

      tmpdir=$(mktemp -d)
      trap 'rm -rf "$tmpdir"' EXIT
      cython-clean
      CYTHON_FLAGS="\
        -fprofile-dir=$tmpdir \
        -fprofile-generate \
        -fprofile-update=prefer-atomic" \
      cython-build

      set +e
      run-tests --extended
      result=$?
      set -e
      if [ "$result" -ne 0 ]; then
        echo "Aborting PGO build due to test failure"
        cython-clean
        exit $result
      fi

      rm -rf build/
      CYTHON_FLAGS="\
        -fprofile-dir=$tmpdir \
        -fprofile-use \
        -fprofile-partial-training" \
      cython-build
    '')
    (makeScript "cython-clean" ''
      rm -rf build/
      find app scripts \
        -type f \
        \( -name '*.c' -o -name '*.html' -o -name '*.so' \) \
        -not \
        \( -path 'app/static/*' -o -path 'app/templates/*' \) \
        -delete
    '')
    (makeScript "watch-cython" "exec watchexec -o queue -w app --exts py cython-build")

    # -- SASS
    (makeScript "sass-pipeline" ''
      src=app/static/sass
      dst=app/static/css
      rm -f "$dst"/*.{css,map}

      bun run sass \
        --quiet-deps \
        --silence-deprecation=import \
        --style compressed \
        --load-path node_modules \
        --no-source-map \
        "$src":"$dst"
      bun run postcss \
        "$dst"/*.css \
        --use autoprefixer \
        --replace \
        --no-map
      mode_hash=${if isDevelopment then "0" else "1"}
      if [ "$1" = "hash" ]; then mode_hash=1; fi
      if [ "$mode_hash" -eq 1 ]; then
        echo "[sass-pipeline] Working in hash mode"
        for file in "$dst"/*.css; do
          hash=$(b3sum --no-names --length=6 "$file")
          new_file="''${file%.css}.$hash.css"
          mv "$file" "$new_file"
          echo "  $new_file"
        done
      fi
    '')
    (makeScript "watch-sass" "exec watchexec -o queue -w app/static/sass sass-pipeline")

    # -- JavaScript
    (makeScript "node" "exec bun \"$@\"")
    (makeScript "js-pipeline" ''
      src=app/static/ts
      dst=app/static/js
      tmp="$dst/_generated"
      mkdir -p "$tmp"
      rm -f "$dst"/*.{js,map}

      bun run babel \
        --extensions ".js,.ts" \
        --copy-files \
        --no-copy-ignored \
        --out-dir "$tmp" \
        "$src"

      files=("$tmp"/!(_*).js)
      mode_hash=${if isDevelopment then "0" else "1"}
      if [ "$1" = "hash" ]; then mode_hash=1; fi
      if [ "$mode_hash" -eq 1 ]; then
        echo "[js-pipeline] Working in hash mode"
        bun_args=(
          --entry-naming="[dir]/[name].[hash].[ext]"
          --minify
          --sourcemap=linked
        )
      else
        bun_args=(
          --entry-naming="[dir]/[name].[ext]"
          --minify-syntax --minify-whitespace
          --sourcemap=inline
        )
      fi
      bun build \
        "''${bun_args[@]}" \
        --outdir "$dst" \
        "''${files[@]}"
    '')
    (makeScript "watch-js" "exec watchexec -o queue -w app/static/ts js-pipeline")

    # -- Static
    (makeScript "static-img-clean" "rm -rf app/static/img/element/_generated")
    (makeScript "static-img-pipeline" "python scripts/rasterize.py static-img-pipeline")
    (makeScript "static-precompress-clean" "static-precompress clean")
    (makeScript "static-precompress" ''
      process_file() {
        file="$1"
        mode="$2"

        process_file_inner() {
          dest="$file.$extension"
          if [ "$mode" = "clean" ]; then
            rm -f "$dest"
            return
          fi
          if [ ! -f "$dest" ] || [ "$dest" -ot "$file" ]; then
              tmpfile=$(mktemp -t "$(basename "$dest").XXXXXXXXXX")
              $compressor "''${args[@]}" "$file" -o "$tmpfile"
              touch --reference "$file" "$tmpfile"
              mv -f "$tmpfile" "$dest"
          fi
        }

        extension="zst"
        compressor="zstd"
        args=(--force --ultra -22 --single-thread --quiet)
        process_file_inner

        extension="br"
        compressor="brotli"
        args=(--force --best)
        process_file_inner
      }
      export -f process_file

      find  \
        "app/static" \
        "config/locale/i18next" \
        "node_modules/iD/dist" \
        "node_modules/@rapideditor/rapid/dist" \
        -type f \
        -not -path "app/static/js/_generated/*" \
        -not -path "node_modules/@rapideditor/rapid/dist/examples/*" \
        -not -name "*.xcf" \
        -not -name "*.gif" \
        -not -name "*.jpg" \
        -not -name "*.jpeg" \
        -not -name "*.png" \
        -not -name "*.webp" \
        -not -name "*.ts" \
        -not -name "*.scss" \
        -not -name "*.br" \
        -not -name "*.zst" \
        -size +499c \
        -printf "%s\t%p\0"  \
      | sort -z --numeric-sort --reverse \
      | cut -z -f2- \
      | parallel --will-cite --null \
        --bar --eta \
        --halt now,fail=1 \
        process_file {} "$@"
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
      mkdir -p app/static/ts/proto
      protoc \
        -I app/models/proto \
        --plugin=node_modules/.bin/protoc-gen-es \
        --es_out app/static/ts/proto \
        --es_opt target=ts \
        --python_out app/models/proto \
        --pyi_out app/models/proto \
        app/models/proto/*.proto
      rm app/static/ts/proto/server*
    '')
    (makeScript "watch-proto" "exec watchexec -o queue -w app/models/proto --exts proto proto-pipeline")

    # -- Supervisor
    (makeScript "dev-start" ''
      pid=$(cat data/supervisor/supervisord.pid 2>/dev/null || echo "")
      if [ -n "$pid" ] && ps -wwp "$pid" -o command= | grep -q "supervisord"; then
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
          --auth=trust \
          --username=postgres
      fi

      mkdir -p data/alembic data/mailpit data/postgres_unix data/supervisor
      python -m supervisor.supervisord -c ${supervisordConf}
      echo "Supervisor started"

      echo "Waiting for Postgres to start..."
      time_start=$(date +%s)
      while ! pg_isready -q -h "${projectDir}/data/postgres_unix" -p 49560; do
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
      pid=$(cat data/supervisor/supervisord.pid 2>/dev/null || echo "")
      if [ -n "$pid" ] && ps -wwp "$pid" -o command= | grep -q "supervisord"; then
        kill -TERM "$pid"
        echo "Supervisor stopping..."
        while kill -0 "$pid" 2>/dev/null; do sleep 0.1; done
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
      if [ "$dataset" != "mazowieckie" ]; then
        echo "Invalid dataset name, must be one of: mazowieckie"
        exit 1
      fi
      mkdir -p "data/preload/$dataset"
      cp --archive --link --force data/preload/*.csv.zst "data/preload/$dataset/"
      echo "Computing checksums file"
      b3sum "data/preload/$dataset/"*.csv.zst > "data/preload/$dataset/checksums.b3"
      rsync \
        --verbose \
        --archive \
        --whole-file \
        --delay-updates \
        --human-readable \
        --progress \
        "data/preload/$dataset/"*.csv.zst \
        "data/preload/$dataset/checksums.b3" \
        edge:"/var/www/files.monicz.dev/openstreetmap-ng/preload/$dataset/"
    '')
    (makeScript "preload-download" ''
      echo "Available preload datasets:"
      echo "  * mazowieckie: Masovian Voivodeship; 1.6 GB download; 60 GB disk space; 15-30 minutes"
      read -rp "Preload dataset name [default: mazowieckie]: " dataset
      dataset="''${dataset:-mazowieckie}"
      if [ "$dataset" != "mazowieckie" ]; then
        echo "Invalid dataset name, must be one of: mazowieckie"
        exit 1
      fi

      echo "Checking for preload data updates"
      remote_check_url="https://files.monicz.dev/openstreetmap-ng/preload/$dataset/checksums.b3"
      remote_checksums=$(curl --silent --location "$remote_check_url")
      names=$(grep -Po '[^/]+(?=\.csv\.zst)' <<< "$remote_checksums")

      mkdir -p "data/preload/$dataset"
      for name in $names; do
        remote_url="https://files.monicz.dev/openstreetmap-ng/preload/$dataset/$name.csv.zst"
        local_file="data/preload/$dataset/$name.csv.zst"
        local_check_file="data/preload/$dataset/$name.csv.zst.b3"

        # recompute checksum if missing but file exists
        if [ -f "$local_file" ] && [ ! -f "$local_check_file" ]; then
          b3sum --no-names "$local_file" > "$local_check_file"
        fi

        # compare with remote checksum
        remote_checksum=$(grep -F "$local_file" <<< "$remote_checksums" | cut -d' ' -f1)
        local_checksum=$(cat "$local_check_file" 2>/dev/null || echo "x")
        if [ "$remote_checksum" = "$local_checksum" ]; then
          echo "File $local_file is up to date"
          continue
        fi

        echo "Downloading $name preload data"
        curl --location "$remote_url" -o "$local_file"

        # recompute checksum
        local_checksum=$(b3sum --no-names "$local_file")
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
    (makeScript "replication" "python scripts/replication.py")
    (makeScript "replication-convert" "python scripts/replication_convert.py")
    (makeScript "replication-load" "python scripts/replication_load.py")

    # -- Testing
    (makeScript "run-tests" ''
      pid=$(cat data/supervisor/supervisord.pid 2>/dev/null || echo "")
      if [ -n "$pid" ] && ps -wwp "$pid" -o command= | grep -q "supervisord"; then true; else
        echo "NOTICE: Supervisor is not running"
        echo "NOTICE: Run 'dev-start' before executing tests"
        exit 1
      fi

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

      args=(
        --verbose
        --no-header
      )
      [ "$extended_tests" = "1" ] && args+=(--extended)
      set +e
      python -m coverage run -m pytest "''${args[@]}"
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
    (makeScript "run" (if isDevelopment then ''
      python -m uvicorn app.main:main \
        --reload \
        --reload-include "*.mo" \
        --reload-exclude scripts \
        --reload-exclude tests \
        --reload-exclude typings
    '' else ''
      python -m gunicorn app.main:main \
        --bind 127.0.0.1:${toString gunicornPort} \
        --workers ${toString gunicornWorkers} \
        --worker-class uvicorn.workers.UvicornWorker \
        --max-requests 10000 \
        --max-requests-jitter 1000 \
        --graceful-timeout 5 \
        --keep-alive 300 \
        --access-logfile -
    ''))
    (makeScript "format" ''
      set +e
      ruff check . --fix
      python -m pre_commit run -c ${preCommitConf} --all-files
    '')
    (makeScript "pyright" "bunx basedpyright")
    (makeScript "feature-icons-popular-update" "python scripts/feature_icons_popular_update.py")
    (makeScript "timezone-bbox-update" "python scripts/timezone_bbox_update.py")
    (makeScript "wiki-pages-update" "python scripts/wiki_pages_update.py")
    (makeScript "vector-styles-update" ''
      dir=app/static/ts/vector-styles
      mkdir -p "$dir"
      styles=(
        "liberty+https://tiles.openfreemap.org/styles/liberty"
      )
      for style in "''${styles[@]}"; do
        name="''${style%%+*}"
        url="''${style#*+}"
        file="$dir/$name.json"
        echo "Updating $name vector style"
        curl --silent --location "$url" | jq --sort-keys . > "$file"
      done
    '')
    (makeScript "open-mailpit" "python -m webbrowser http://127.0.0.1:49566")
    (makeScript "open-app" "python -m webbrowser http://127.0.0.1:8000")
    (makeScript "nixpkgs-update" ''
      hash=$(
        curl --silent --location \
        https://prometheus.nixos.org/api/v1/query \
        -d "query=channel_revision{channel=\"nixpkgs-unstable\"}" | \
        grep -Eo "[0-9a-f]{40}")
      sed -i -E "s|/nixpkgs/archive/[0-9a-f]{40}\.tar\.gz|/nixpkgs/archive/$hash.tar.gz|" shell.nix
      echo "Nixpkgs updated to $hash"
    '')
    (makeScript "docker-build-push" ''
      cython-clean && cython-build
      if command -v podman &> /dev/null; then docker() { podman "$@"; } fi
      docker push "$(docker load < "$(nix-build --no-out-link)" | sed -n -E 's/Loaded image: (\S+)/\1/p')"
    '')
  ];

  shell' = ''
    export SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt
    export PYTHONNOUSERSITE=1
    export PYTHONPATH=""
    export TZ=UTC
    export COVERAGE_CORE=sysmon

    en_yaml_path="${projectDir}/config/locale/download/en.yaml"
    en_yaml_sym_path="${projectDir}/config/locale/en.yaml"
    current_en_yaml=$(readlink -e "$en_yaml_sym_path" || echo "")
    if [ "$current_en_yaml" != "$en_yaml_path" ]; then
      echo "Creating convenience symlink for en.yaml"
      ln -s "$en_yaml_path" "$en_yaml_sym_path"
    fi

    current_python=$(readlink -e .venv/bin/python || echo "")
    current_python=''${current_python%/bin/*}
    [ "$current_python" != "${python'}" ] && rm -rf .venv/

    echo "Installing Python dependencies"
    export UV_PYTHON="${python'}/bin/python"
    uv sync --frozen

    echo "Installing Bun dependencies"
    export DO_NOT_TRACK=1
    bun install --frozen-lockfile

    echo "Activating Python virtual environment"
    source .venv/bin/activate

    if [ -d .git ] && command -v git &>/dev/null; then
      echo "Installing pre-commit hooks"
      python -m pre_commit install -c ${preCommitConf} --overwrite
      cp --force --symbolic-link ${preCommitHook}/bin/pre-commit-hook .git/hooks/pre-commit
    fi

    export LEGACY_SEQUENCE_ID_MARGIN=1
  '' + pkgs.lib.optionalString isDevelopment ''
    export TEST_ENV=1
    export FREEZE_TEST_USER=0
    export FORCE_RELOAD_LOCALE_FILES=1
    export SECRET=development-secret
    export APP_URL=http://127.0.0.1:8000
    export NOMINATIM_URL=https://nominatim.monicz.dev
    export GRAPHHOPPER_API_KEY=e6d61235-3e37-4290-91a7-d7be9e5a8909
    export FACEBOOK_OAUTH_PUBLIC=1538918736889845
    export FACEBOOK_OAUTH_SECRET=4090c8e1f08a93af65c6d6cc56350f4b
    export GITHUB_OAUTH_PUBLIC=Ov23lidLgxluuWuo0PNn
    export GITHUB_OAUTH_SECRET=4ed29823ee9d975e9f42a14e5c3d4b8293041cda
    export GOOGLE_OAUTH_PUBLIC=329628600169-6du7d20fo0poong0aqttuikstq97bten.apps.googleusercontent.com
    export GOOGLE_OAUTH_SECRET=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
    export MICROSOFT_OAUTH_PUBLIC=db54bdb3-08af-481b-9641-39f49065b640
    export WIKIMEDIA_OAUTH_PUBLIC=2f7fe9e2825acc816d1e1103d203e8ec
    export WIKIMEDIA_OAUTH_SECRET=d07aaeabb5f7a5de76e3d667db3dfe0b2a5abf11
    export LEGACY_HIGH_PRECISION_TIME=1
  '' + pkgs.lib.optionalString enableMailpit ''
    export SMTP_HOST=127.0.0.1
    export SMTP_PORT=49565
    export SMTP_USER=mail@openstreetmap.org
    export SMTP_PASS=anything
  '' + ''

    if [ -f .env ]; then
      echo "Loading .env file"
      set -o allexport
      source .env set
      set +o allexport
    else
      echo "Skipped loading .env file (not found)"
    fi

    if [ ! -d app/static/css ]; then
      echo "Running [sass-pipeline]"
      sass-pipeline &
    fi
    if [ ! -d app/static/js ]; then
      echo "Running [js-pipeline]"
      js-pipeline &
    fi
    echo "Running [proto-pipeline]"
    proto-pipeline &
    echo "Running [locale-pipeline]"
    locale-pipeline &
    echo "Running [static-img-pipeline]"
    static-img-pipeline &
    wait
  '';
in
pkgs.mkShell.override { stdenv = stdenv'; } {
  packages = packages';
  shellHook = shell';
}
