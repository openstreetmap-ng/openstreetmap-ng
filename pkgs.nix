{
  # check latest hashes at https://status.nixos.org/
  pkgs = import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/da4024d0ead5d7820f6bd15147d3fe2a0c0cec73.tar.gz") { };
  unstable = import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/85f1ba3e51676fa8cc604a3d863d729026a6b8eb.tar.gz") { };
}
