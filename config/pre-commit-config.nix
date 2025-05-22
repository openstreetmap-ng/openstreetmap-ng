{ pkgs, makeScript }:

pkgs.writeText "pre-commit-config.yaml" ''
  repos:
    - repo: local
      hooks:
        - id: nixpkgs-fmt
          name: nixpkgs-fmt
          entry: ${makeScript "entry" ''
            ${pkgs.nixpkgs-fmt}/bin/nixpkgs-fmt "$@"
          ''}/bin/entry
          language: system
          types_or: [nix]

        - id: ruff
          name: ruff
          entry: ${makeScript "entry" ''
            ${pkgs.ruff}/bin/ruff format --force-exclude "$@"
          ''}/bin/entry
          language: system
          types_or: [python, pyi]
          require_serial: true

        - id: ruff-isort
          name: ruff-isort
          entry: ${makeScript "entry" ''
            ${pkgs.ruff}/bin/ruff check --select I --fix --force-exclude "$@"
          ''}/bin/entry
          language: system
          types_or: [python, pyi]
          require_serial: true

        - id: clang-format
          name: clang-format
          entry: ${makeScript "entry" ''
            ${pkgs.llvmPackages_latest.clang-tools}/bin/clang-format -i "$@"
          ''}/bin/entry
          language: system
          types_or: [c]

        - id: biome
          name: biome
          entry: ${makeScript "entry" ''
            ${pkgs.biome}/bin/biome format --write --no-errors-on-unmatched "$@"
          ''}/bin/entry
          language: system
          types_or: [ts, javascript]

        - id: prettier
          name: prettier
          entry: ${makeScript "entry" ''
            ${pkgs.bun}/bin/bunx prettier --write "$@"
          ''}/bin/entry
          language: system
          types_or: [scss]
''
