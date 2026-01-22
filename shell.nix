{
  isDevelopment ? true,
  shellHook ? true,
  hostMemoryMb ? 8192,
  hostDiskCoW ? false,
  enablePostgres ? true,
  postgresPort ? 49560,
  postgresSharedBuffersPerc ? 0.3,
  postgresWorkMemMb ? 64,
  postgresWorkers ?
    postgresParallelWorkers + postgresAutovacuumWorkers + postgresTimescaleWorkers + 1,
  postgresParallelWorkers ? postgresParallelMaintenanceWorkers * 2,
  postgresParallelMaintenanceWorkers ? 4,
  postgresAutovacuumWorkers ? 2,
  postgresTimescaleWorkers ? 3,
  postgresIOConcurrency ? 300,
  postgresRandomPageCost ? 1.1,
  postgresMinWalSizeGb ? 1,
  postgresMaxWalSizeGb ? 10,
  postgresVerbose ? 2, # 0 = no, 1 = some, 2 = most
  duckdbMemoryLimitPerc ? 0.8 - (if enablePostgres then postgresSharedBuffersPerc else 0),
  enableMailpit ? true,
  mailpitHttpPort ? 49566,
  mailpitSmtpPort ? 49565,
  gunicornWorkers ? 1,
  gunicornPort ? 8000,
}:

let
  # Update packages with `nixpkgs-update` command
  pkgsUrl = "https://github.com/NixOS/nixpkgs/archive/ed142ab1b3a092c4d149245d0c4126a5d7ea00b0.tar.gz";
  pkgs = import (fetchTarball pkgsUrl) { };

  projectDir = toString ./.;
  postgresArgs = {
    inherit
      hostMemoryMb
      hostDiskCoW
      postgresPort
      postgresSharedBuffersPerc
      postgresWorkMemMb
      postgresWorkers
      postgresParallelWorkers
      postgresParallelMaintenanceWorkers
      postgresAutovacuumWorkers
      postgresTimescaleWorkers
      postgresIOConcurrency
      postgresRandomPageCost
      postgresMinWalSizeGb
      postgresMaxWalSizeGb
      postgresVerbose
      pkgs
      projectDir
      ;
  };
  postgresConf = import ./config/postgres.nix postgresArgs;
  postgresFastIngestConf = import ./config/postgres.nix (
    postgresArgs
    // {
      postgresWorkers = postgresWorkers - postgresAutovacuumWorkers;
      postgresAutovacuumWorkers = 0;
      fastIngest = true;
    }
  );
  processComposeArgs = {
    inherit
      isDevelopment
      enablePostgres
      enableMailpit
      mailpitHttpPort
      mailpitSmtpPort
      pkgs
      postgresConf
      ;
  };
  processComposeConf = import ./config/process-compose.nix processComposeArgs;
  processComposeFastIngestConf = import ./config/process-compose.nix (
    processComposeArgs // { postgresConf = postgresFastIngestConf; }
  );

  pythonLibs = with pkgs; [
    cairo.out
    file.out
    libyaml.out
    libxml2.out
    openssl.out
    zlib.out
    stdenv.cc.cc.lib
  ];
  python' =
    with pkgs;
    symlinkJoin {
      name = "python";
      paths = [
        # Enable compiler optimizations when in production
        (if isDevelopment then python313 else python313.override { enableOptimizations = true; })
      ];
      buildInputs = [ makeWrapper ];
      postBuild = ''
        wrapProgram "$out/bin/python3.13" \
          --prefix ${if stdenv.isDarwin then "DYLD_LIBRARY_PATH" else "LD_LIBRARY_PATH"} : \
          "${lib.makeLibraryPath pythonLibs}"
      '';
    };
  # https://github.com/NixOS/nixpkgs/blob/nixpkgs-unstable/pkgs/build-support/trivial-builders/default.nix
  makeScript =
    with pkgs;
    name: text:
    writeTextFile {
      inherit name;
      executable = true;
      destination = "/bin/${name}";
      text = ''
        #!${runtimeShell} -e
        shopt -s extglob nullglob globstar lastpipe
        [[ -v GLOBSORT ]] || GLOBSORT=nosort
        cd "${projectDir}"
        ${text}
      '';
      checkPhase = ''
        ${stdenv.shellDryRun} "$target"
        ${shellcheck}/bin/shellcheck --severity=style "$target"
      '';
      meta.mainProgram = name;
    };

  scriptsDir = ./shellscripts;
  scriptsCtx = {
    inherit
      pkgs
      isDevelopment
      processComposeConf
      processComposeFastIngestConf
      gunicornPort
      gunicornWorkers
      enablePostgres
      pkgsUrl
      ;
  };
  scriptsFiles =
    let
      files = pkgs.lib.filesystem.listFilesRecursive scriptsDir;
      scriptPaths = builtins.filter (
        path: pkgs.lib.hasSuffix ".sh" (toString path) || pkgs.lib.hasSuffix ".nix" (toString path)
      ) files;
    in
    pkgs.lib.sort (a: b: (toString a) < (toString b)) scriptPaths;
  scriptNameFor =
    path:
    let
      rel = pkgs.lib.removePrefix "${toString scriptsDir}/" (toString path);
      noExt =
        if pkgs.lib.hasSuffix ".sh" rel then
          pkgs.lib.removeSuffix ".sh" rel
        else
          pkgs.lib.removeSuffix ".nix" rel;
    in
    pkgs.lib.replaceStrings [ "/" ] [ "-" ] noExt;
  scriptTextFor =
    path:
    let
      text =
        if pkgs.lib.hasSuffix ".nix" (toString path) then
          import path scriptsCtx
        else
          builtins.readFile path;
    in
    assert pkgs.lib.isString text;
    text;
  scriptPackages = map (path: makeScript (scriptNameFor path) (scriptTextFor path)) scriptsFiles;

  packages' =
    with pkgs;
    [
      b3sum
      biome
      brotli
      bun
      coreutils
      curl
      diffutils
      fd
      findutils
      gettext
      gnused
      gnutar
      gzip
      jq
      llvmPackages_latest.lld
      mailpit
      nixfmt
      nodejs-slim_24
      patchelf
      pigz
      process-compose
      procps
      protobuf_33
      python'
      ripgrep
      rsync
      ruff
      rustup
      shfmt
      timescaledb-parallel-copy
      tombi
      uv
      zstd

      (postgresql_18_jit.withPackages (ps: [
        ps.h3-pg
        ps.pg_hint_plan
        ps.postgis
        ps.timescaledb-apache
      ])).out
    ]
    ++ scriptPackages;

  shell' =
    with pkgs;
    ''
      [ "$NIX_SSL_CERT_FILE" = "/no-cert-file.crt" ] && unset NIX_SSL_CERT_FILE
      [ "$SSL_CERT_FILE" = "/no-cert-file.crt" ] && unset SSL_CERT_FILE
    ''
    + lib.optionalString stdenv.isDarwin ''
      [ -z "$NIX_SSL_CERT_FILE" ] && export NIX_SSL_CERT_FILE="${cacert}/etc/ssl/certs/ca-bundle.crt"
      [ -z "$SSL_CERT_FILE" ] && export SSL_CERT_FILE="$NIX_SSL_CERT_FILE"
    ''
    + ''
      export TZ=UTC
      export NIX_ENFORCE_NO_NATIVE=0
      export NIX_ENFORCE_PURITY=0
      export PROC_COMP_CONFIG=data/pcompose
      export PC_DISABLE_DOTENV=1
      export PC_LOG_FILE=data/pcompose/internal.log
      export PC_SOCKET_PATH="${projectDir}/data/pcompose/pcompose.sock"
      export PATH="$PATH:${gitMinimal}/bin"
      export PYTHONNOUSERSITE=1
      export PYTHONPATH="${projectDir}"
      export COVERAGE_CORE=sysmon

      export CFLAGS="$CFLAGS \
        -pipe -g ${if isDevelopment then "-Og" else "-O3"} \
        -march=''${CMARCH:-native} \
        -funsafe-math-optimizations \
        -fvisibility=hidden \
        -flto=thin \
        ${lib.optionalString stdenv.isLinux "-fno-plt"}"

      export LDFLAGS="$LDFLAGS \
        -flto=thin \
        -fuse-ld=lld \
        ${if isDevelopment then "-Wl,-O0" else "-Wl,-O2"} \
        ${lib.optionalString stdenv.isLinux "-Wl,-z,relro -Wl,-z,now"}"

      export RUSTFLAGS="$RUSTFLAGS \
        -C target-cpu=''${CMARCH:-native} \
        ${lib.optionalString stdenv.isLinux "-C link-arg=-fuse-ld=lld"} \
        -C link-arg=${if isDevelopment then "-Wl,-O0" else "-Wl,-O2"} \
        ${lib.optionalString stdenv.isLinux "-C link-arg=-Wl,-z,relro -C link-arg=-Wl,-z,now"}"
    ''
    + lib.optionalString isDevelopment ''
      export ENV=dev
      export SECRET=development-secret
      export APP_URL=http://localhost:8000
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
    ''
    + lib.optionalString enableMailpit ''
      export SMTP_HOST=localhost
      export SMTP_PORT=49565
      export SMTP_USER=mail@openstreetmap.org
      export SMTP_PASS=anything
    ''
    + ''
      export POSTGRES_URL="postgresql://postgres@/postgres\
      ?host=${projectDir}/data/postgres_unix\
      &port=${toString postgresPort}"
      export DUCKDB_MEMORY_LIMIT=${toString (builtins.floor (hostMemoryMb * duckdbMemoryLimitPerc))}MB

      if [ -f .env ]; then
        echo "Loading .env file"
        set -a; . .env; set +a
      else
        echo "Skipped loading .env file (not found)"
      fi

      browser-logos-update

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
      export UV_NATIVE_TLS=true
      export UV_PYTHON="${python'}/bin/python"
      uv sync --frozen
      source .venv/bin/activate
      export UV_PYTHON="$VIRTUAL_ENV/bin/python"

      python -m maturin_import_hook site install --args="${
        lib.optionalString (!isDevelopment) "--release"
      }" &

      echo "Installing TS/JS dependencies"
      bun install --frozen-lockfile
      export PATH="${projectDir}/node_modules/.bin:$PATH"

      if [ -d .git ]; then
        echo "Installing git hooks"
        ln -sf "$(command -v _pre-commit)" .git/hooks/pre-commit
      fi
    ''
    + lib.optionalString stdenv.isDarwin ''
      _patch-shebang &
    ''
    + ''
      echo "Running [static-img-pipeline]"
      static-img-pipeline &
      echo "Running [proto-pipeline]"
      proto-pipeline &
    ''
    + lib.optionalString (!isDevelopment) ''
      echo "Running [locale-pipeline]"
      locale-pipeline
      echo "Running [vite-build]"
      vite-build
    ''
    + ''
      wait
    '';
in
with pkgs;
mkShell.override
  {
    stdenv = if stdenv.isDarwin then stdenv else llvmPackages_latest.stdenv;
  }
  {
    packages = packages';
    shellHook = lib.optionalString shellHook shell';
  }
