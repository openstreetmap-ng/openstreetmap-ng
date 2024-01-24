{ isDevelopment ? true }:

let
  # Currently using nixpkgs-23.11-darwin
  # Get latest hashes from https://status.nixos.org/
  pkgs = import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/d2003f2223cbb8cd95134e4a0541beea215c1073.tar.gz") { };

  libraries' = with pkgs; [
    # Base libraries
    stdenv.cc.cc.lib
    file.out
    libxml2.out
    zlib.out
  ];

  packages' = with pkgs; [
    # Base packages
    python312
    coreutils
    zstd
    bun

    # Scripts
    # -- Misc
    (writeShellScriptBin "make-version" ''
      sed \
        --in-place \
        --regexp-extended \
        "s|VERSION = '([0-9.]+)'|VERSION = '\1.$(date +%y%m%d)'|g" \
        "app/config.py"
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

    # Scripts
    # -- Cython
    (writeShellScriptBin "cython-build" ''
      python setup.py build_ext --inplace --parallel $(nproc --all)
    '')
    (writeShellScriptBin "cython-clean" ''
      rm -rf build/ app/{exceptions,exceptions06,format06,format07,lib,middlewares,responses}/**/*{.c,.html,.so}
    '')

    # -- Alembic
    (writeShellScriptBin "alembic-revision" ''
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
      rm -rf config/locale
    '')
    (writeShellScriptBin "locale-download" ''
      set -e
      rm -rf config/locale/download
      python scripts/locale_download.py
    '')
    (writeShellScriptBin "locale-postprocess" ''
      set -e
      rm -rf config/locale/postprocess
      python scripts/locale_postprocess.py
    '')
    (writeShellScriptBin "locale-make-i18next" ''
      set -e
      rm -rf config/locale/i18next
      python scripts/locale_make_i18next.py
    '')
    (writeShellScriptBin "locale-make-gnu" ''
      set -e
      rm -rf config/locale/gnu
      mkdir -p config/locale/gnu

      for file in $(find config/locale/i18next -type f); do
        stem=$(basename "$file" .json)
        locale=''${stem::-17}
        target="config/locale/gnu/$locale/LC_MESSAGES/messages.po"

        mkdir -p "$(dirname "$target")"

        bun run i18next-conv \
          --quiet \
          --language "$locale" \
          --source "$file" \
          --target "$target" \
          --keyseparator "." \
          --ctxSeparator "__" \
          --compatibilityJSON "v4"

        msgfmt "$target" --output-file "''${target%.po}.mo";
        echo "[✅] '$locale': converted to gnu"
      done
    '')
    (writeShellScriptBin "locale-local-pipeline" ''
      set -e
      locale-postprocess
      locale-make-i18next
      locale-make-gnu
    '')
    (writeShellScriptBin "locale-remote-pipeline" ''
      set -e
      locale-download
      locale-local-pipeline
    '')

    # -- Wiki-tags
    (writeShellScriptBin "wiki-tags-download" ''
      set -e
      python scripts/wiki_tags_download.py
    '')

    # -- Docker (dev)
    (writeShellScriptBin "dev-start" ''
      [ -d data/pgadmin ] || install -d -o 5050 -g 5050 data/pgadmin
      docker compose -f docker-compose.dev.yml up -d
    '')
    (writeShellScriptBin "dev-stop" ''
      docker compose -f docker-compose.dev.yml down
    '')
    (writeShellScriptBin "dev-logs" ''
      docker compose -f docker-compose.dev.yml logs -f
    '')
    (writeShellScriptBin "dev-clean" ''
      dev-stop
      rm -rf data/db data/pgadmin
    '')

    # -- Misc
    (writeShellScriptBin "docker-build-push" ''
      set -e
      cython-clean && cython-build
      if command -v podman &> /dev/null; then docker() { podman "$@"; } fi
      docker push $(docker load < "$(sudo nix-build --no-out-link)" | sed -En 's/Loaded image: (\S+)/\1/p')
    '')
    (writeShellScriptBin "watch-sass" ''
      bun run watch:sass
    '')
    (writeShellScriptBin "watch-test" ''
      ptw --now . --cov app --cov-report xml
    '')
    (writeShellScriptBin "load-osm" ''
      python scripts/load_osm.py $(find . -maxdepth 1 -name '*.osm' -print -quit)
    '')
    (writeShellScriptBin "open-pgadmin" ''
      xdg-open http://127.0.0.1:5433
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
    export SECRET="development-secret"
    export TEST_ENV=1
    export HTTPS_ONLY=0
    export APP_URL="http://127.0.0.1:3000"
    export API_URL="http://127.0.0.1:3000"
    export ID_URL="http://127.0.0.1:3000"
    export RAPID_URL="http://127.0.0.1:3000"

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
