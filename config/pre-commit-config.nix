{ pkgs }:

pkgs.writeText "pre-commit-config.yaml" ''
  repos:
    - repo: local
      hooks:
        - id: ruff
          name: ruff
          entry: ${pkgs.ruff}/bin/ruff format --force-exclude
          language: system
          types_or: [python, pyi]
          require_serial: true

        - id: ruff-isort
          name: ruff-isort
          entry: ${pkgs.ruff}/bin/ruff check --select I --fix --force-exclude
          language: system
          types_or: [python, pyi]
          require_serial: true

        - id: biome
          name: biome
          entry: ${pkgs.biome}/bin/biome format --write --files-ignore-unknown=true --no-errors-on-unmatched
          language: system
          types_or: [ts, javascript]
          require_serial: true

        - id: nixpkgs-fmt
          name: nixpkgs-fmt
          entry: ${pkgs.nixpkgs-fmt}/bin/nixpkgs-fmt
          language: system
          types_or: [nix]
          require_serial: true

        - id: prettier
          name: prettier
          entry: ${pkgs.bun}/bin/bunx prettier --write
          language: system
          types_or: [scss]
          require_serial: true
''
