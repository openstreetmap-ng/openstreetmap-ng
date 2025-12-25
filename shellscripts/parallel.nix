{ pkgs, ... }:
''
  args=(--will-cite)
  if [[ -t 1 ]]; then
    args+=(--bar --eta)
  fi
  exec ${pkgs.parallel}/bin/parallel "''${args[@]}" "$@"
''
