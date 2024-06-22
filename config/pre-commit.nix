{ pkgs }:

pkgs.writeText "pre-commit-config.yaml" ''
  repos:
    - repo: local
      hooks:
        - id: ruff-format
          name: ruff-format
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

        - id: biome-format
          name: biome-format
          entry: ${pkgs.biome}/bin/biome format --write --files-ignore-unknown=true --no-errors-on-unmatched
          language: system
          types_or: [javascript]
          require_serial: true

        - id: nixpkgs-fmt
          name: nixpkgs-fmt
          entry: ${pkgs.nixpkgs-fmt}/bin/nixpkgs-fmt
          language: system
          types_or: [nix]
          require_serial: true
''
