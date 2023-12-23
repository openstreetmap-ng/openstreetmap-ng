{
  # check latest hashes at https://status.nixos.org/
  pkgs = import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/f1f519256f007a3910a50b88bff7bcfe6d1202da.tar.gz") { };
  unstable = import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/d6863cbcbbb80e71cecfc03356db1cda38919523.tar.gz") { };
}
