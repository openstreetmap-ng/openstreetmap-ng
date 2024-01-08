{ isDevelopment ? true }:

let
  # Currently using nixpkgs-23.11-darwin
  # Get latest hashes from https://status.nixos.org/
  pkgs = import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/207b14c6bd1065255e6ecffcfe0c36a7b54f8e48.tar.gz") { };

  libraries' = with pkgs; [
    # Base libraries
    stdenv.cc.cc.lib
    file.out
    expat.out
    libxml2.out
    zlib.out
  ];

  packages' = with pkgs; [
    # Base packages
    python312
    busybox
    zstd
    gettext

    # Scripts
    (writeShellScriptBin "make-version" ''
      sed -i -r "s|VERSION = '([0-9.]+)'|VERSION = '\1.$(date +%y%m%d)'|g" config.py
    '')
    (writeShellScriptBin "make-locale" ''
      set -e
      [ "$(realpath $(pwd))" != "$(realpath "$PROJECT_DIR")" ] && echo "WARNING: CWD != $PROJECT_DIR"

      echo "Processing osm-community-index"
      python scripts/make_locale_oci.py

      echo "Merging .po files"
      for file in $(find config/locale -type f -name out-osm-0-all.po); do
        locale_dir=$(dirname "$file")
        msgcat --use-first "$file" "$locale_dir/oci.po" | sed 's/%{/{/g' > "$locale_dir/combined.po"
      done

      echo "Compiling .po files"
      for file in $(find config/locale -type f -name combined.po); do
        msgfmt "$file" -o "''${file%.po}.mo";
      done
    '')
  ] ++ lib.optionals isDevelopment [
    # Development packages
    poetry
    nodejs_20
    gcc
    ruff
    biome
    dart-sass
    esbuild

    # Scripts
    # -- Cython
    (writeShellScriptBin "cython-build" ''
      python "$PROJECT_DIR/setup.py" build_ext --build-lib "$PROJECT_DIR/src/lib_cython"
    '')
    (writeShellScriptBin "cython-clean" ''
      rm -rf "$PROJECT_DIR/build/" "$PROJECT_DIR/src/lib_cython/"*{.c,.html,.so}
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
      docker push $(docker load < $(nix-build --no-out-link) | sed -En 's/Loaded image: (\S+)/\1/p')
    '')
    (writeShellScriptBin "watch-sass" ''
      npm run watch:sass
    '')
    (writeShellScriptBin "load-osm" ''
      python "$PROJECT_DIR/scripts/load_osm.py" $(find "$PROJECT_DIR" -maxdepth 1 -name '*.osm' -print -quit)
    '')
    (writeShellScriptBin "open-pgadmin" ''
      xdg-open http://127.0.0.1:5433
    '')
  ];

  shell' = with pkgs; ''
    [ ! -e .venv/bin/python ] && [ -h .venv/bin/python ] && rm -r .venv

    echo "Installing Python dependencies"
    poetry install --compile

    echo "Installing Node.js dependencies"
    npm install --no-fund

    echo "Activating Python virtual environment"
    source .venv/bin/activate

    export LD_LIBRARY_PATH="${lib.makeLibraryPath libraries'}"
  '' + lib.optionalString isDevelopment ''
    export PROJECT_DIR="$(pwd)"

    # Development environment variables
    export SECRET="development-secret"
    export TEST_ENV=1
    export HTTPS_ONLY=0
    export APP_URL="http://127.0.0.1:3000"
    export API_URL="http://127.0.0.1:3000"
    export ID_URL="http://127.0.0.1:3000"
  '';
in
pkgs.mkShell {
  packages = libraries' ++ packages';
  shellHook = shell';
}
