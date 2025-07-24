{ pkgs, makeScript }:

with pkgs;
writeText "pre-commit-config.yaml" ''
  repos:
    - repo: local
      hooks:
        - id: nixfmt
          name: nixfmt
          entry: ${makeScript "entry" ''
            ${nixfmt-rfc-style}/bin/nixfmt "$@"
          ''}/bin/entry
          language: system
          types_or: [nix]

        - id: ruff
          name: ruff
          entry: ${makeScript "entry" ''
            ${ruff}/bin/ruff format --force-exclude "$@"
          ''}/bin/entry
          language: system
          types_or: [python, pyi]
          require_serial: true

        - id: ruff-isort
          name: ruff-isort
          entry: ${makeScript "entry" ''
            ${ruff}/bin/ruff check --select I --fix --force-exclude "$@"
          ''}/bin/entry
          language: system
          types_or: [python, pyi]
          require_serial: true

        - id: clang-format
          name: clang-format
          entry: ${makeScript "entry" ''
            ${llvmPackages_latest.clang-tools}/bin/clang-format -i "$@"
          ''}/bin/entry
          language: system
          types_or: [c]

        - id: biome
          name: biome
          entry: ${makeScript "entry" ''
            ${biome}/bin/biome format --write --no-errors-on-unmatched "$@"
          ''}/bin/entry
          language: system
          types_or: [ts, javascript]

        - id: prettier
          name: prettier
          entry: ${makeScript "entry" ''
            ${pnpm}/bin/pnpx prettier --write "$@"
          ''}/bin/entry
          language: system
          types_or: [scss]
''
