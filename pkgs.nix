{
  # check latest hashes at https://status.nixos.org/
  pkgs = import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/1ed863a65c91f77e027955818bf6679f4c966320.tar.gz") { };
  unstable = import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/09ec6a0881e1a36c29d67497693a67a16f4da573.tar.gz") { };
}
