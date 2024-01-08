{ config, pkgs, lib, ... }:

let
  isDevelopment = !config.container.isBuilding;

  # Configure installed packages - https://devenv.sh/packages/
  # Also see: https://search.nixos.org/packages
  libraries' = with pkgs; [
    stdenv.cc.cc.lib
    file.out
    expat.out
    libxml2.out
    zlib.out
  ];

  packages' = with pkgs; [
    # Base packages
    busybox
    zstd
  ] ++ lib.optionals isDevelopment [
    # Development packages
    gettext
    gcc
    ruff
    biome
    dart-sass
    esbuild
  ];
in
{
  env = lib.optionalAttrs isDevelopment {
    # Development environment variables
    SECRET = "development-secret";
    TEST_ENV = true;
    HTTPS_ONLY = false;
    APP_URL = "http://127.0.0.1:3000";
    API_URL = "http://127.0.0.1:3000";
    ID_URL = "http://127.0.0.1:3000";
  };

  packages = libraries' ++ packages';

  enterShell = ''
    export LD_LIBRARY_PATH="${lib.makeLibraryPath libraries'}"
  '';

  # Configure scripts - https://devenv.sh/scripts/
  # -- Cython
  scripts.cython-build.exec = ''
    python "$DEVENV_ROOT/setup.py" build_ext --build-lib "$DEVENV_ROOT/src/lib_cython"
  '';
  scripts.cython-clean.exec = ''
    rm -rf "$DEVENV_ROOT/build/" "$DEVENV_ROOT/src/lib_cython/"*{.c,.html,.so}
  '';

  # -- Alembic
  scripts.alembic-revision.exec = ''
    name=$1
    if [ -z "$name" ]; then
      read -p "Database migration name: " name
    fi
    alembic revision --autogenerate --message "$name"
  '';
  scripts.alembic-upgrade.exec = ''
    alembic upgrade head
  '';

  # -- NPM scripts
  scripts.watch-sass.exec = ''
    npm run watch:sass
  '';

  # -- Shortcuts
  scripts.open-pgadmin.exec = ''
    xdg-open http://127.0.0.1:5433
  '';

  # Configure languages - https://devenv.sh/languages/
  languages.python = {
    enable = true;
    package = pkgs.python312;
    poetry = {
      enable = true;
      activate.enable = true;
      install.enable = true;
      install.installRootPackage = true;
    };
  };

  languages.javascript = {
    enable = isDevelopment;
    package = pkgs.nodejs_20;
    npm.install.enable = isDevelopment;
  };

  # https://devenv.sh/pre-commit-hooks/
  # pre-commit.hooks.shellcheck.enable = true;

  # https://devenv.sh/processes/
  # processes.ping.exec = "ping example.com";

  # See full reference at https://devenv.sh/reference/options/
}
