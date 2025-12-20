{ pkgs, ... }:
''
  exec ${pkgs.watchexec}/bin/watchexec --wrap-process=none "$@"
''
