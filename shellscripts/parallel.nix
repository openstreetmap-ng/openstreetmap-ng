{ pkgs, ... }:
''
  args=(--will-cite)
  [[ -t 1 ]] && args+=(--bar --eta)
  exec ${pkgs.parallel}/bin/parallel "''${args[@]}" "$@"
''
