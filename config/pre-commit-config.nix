{ pkgs, makeScript }:

pkgs.writeText "pre-commit-config.yaml" ''
  repos:
    - repo: local
      hooks:
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

        - id: biome
          name: biome
          entry: ${makeScript "entry" ''
            ${pkgs.biome}/bin/biome format --write --no-errors-on-unmatched "$@"
          ''}/bin/entry
          language: system
          types_or: [ts, javascript]
          require_serial: true

        - id: nixpkgs-fmt
          name: nixpkgs-fmt
          entry: ${makeScript "entry" ''
            ${pkgs.nixpkgs-fmt}/bin/nixpkgs-fmt "$@"
          ''}/bin/entry
          language: system
          types_or: [nix]
          require_serial: true

        - id: prettier
          name: prettier
          entry: ${makeScript "entry" ''
            ${pkgs.bun}/bin/bunx prettier --write "$@"
          ''}/bin/entry
          language: system
          types_or: [scss]
          require_serial: true
''
