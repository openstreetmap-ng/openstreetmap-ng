{ pkgs, projectDir, preCommitConf }:

with pkgs; writeShellScriptBin "pre-commit-hook" ''
  exec "${projectDir}/.venv/bin/python" -m pre_commit hook-impl \
    --config "${preCommitConf}" \
    --hook-dir "${projectDir}/.git/hooks" \
    --hook-type pre-commit \
    -- "$@"
''
