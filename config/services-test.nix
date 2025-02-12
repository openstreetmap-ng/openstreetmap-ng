{ pkgs, ... }:

# Service configuration for OSM-NG testing instance
# Specs: hmad.large (4T, 32GB RAM, 100GB SSD) + 1000GB SSD
# https://cloudferro.com/pricing/virtual-machines-vm-2/

let
  nixShellRun = script: ''
    ${pkgs.nix}/bin/nix-shell \
      --pure \
      --arg isDevelopment false \
      --arg hostMemoryMb 32768 \
      --arg hostDiskCoW true \
      --arg postgresCpuThreads 4 \
      --arg gunicornWorkers 8 \
      --run "export TEST_ENV=1 && ${script}"
  '';
in
{
  users.groups.osm-ng = { };
  users.users.osm-ng = {
    group = "osm-ng";
    home = "/home/osm-ng";
    createHome = true;
    isSystemUser = true;
  };
  systemd.services.osm-ng = {
    enable = false;
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];
    wantedBy = [ "default.target" ];
    unitConfig = {
      StartLimitIntervalSec = "infinity";
      StartLimitBurst = 30;
    };
    serviceConfig = {
      Type = "exec";
      User = "osm-ng";
      WorkingDirectory = "/data/osm-ng";
      Restart = "on-failure";
      RestartSec = "10s";

      ProtectSystem = "strict";
      ReadWritePaths = [
        "/home/osm-ng"
        "/data/osm-ng"
        "/nix/var/nix/daemon-socket/socket"
      ];
      NoExecPaths = "/";
      ExecPaths = "/nix/store";

      CapabilityBoundingSet = "";
      LockPersonality = true;
      NoNewPrivileges = true;
      PrivateDevices = true;
      PrivateTmp = true;
      ProtectClock = true;
      ProtectControlGroups = true;
      ProtectHostname = true;
      ProtectKernelLogs = true;
      ProtectKernelModules = true;
      ProtectKernelTunables = true;
      ProtectProc = "noaccess";
      ProcSubset = "pid";
      PrivateUsers = true;
      RestrictAddressFamilies = [ "AF_UNIX" "AF_INET" "AF_INET6" ];
      RestrictNamespaces = true;
      RestrictRealtime = true;
      RestrictSUIDSGID = true;
      SystemCallArchitectures = "native";
      UMask = "0077";

      SystemCallFilter = [
        "~@clock"
        "~@cpu-emulation"
        "~@debug"
        "~@module"
        "~@mount"
        "~@obsolete"
        "~@raw-io"
        "~@reboot"
        "~@swap"
      ];
    };
    environment = {
      NIX_PATH = "nixpkgs=/nix/var/nix/profiles/per-user/root/channels/nixos:/nix/var/nix/profiles/per-user/root/channels";
    };
    preStart = nixShellRun "static-precompress && dev-start";
    script = nixShellRun ''
      export APP_URL=https://openstreetmap.ng
      && export API_URL=https://api.openstreetmap.ng
      && export ID_URL=https://id.openstreetmap.ng
      && export RAPID_URL=https://rapid.openstreetmap.ng
      && export FORCE_CRASH_REPORTING=1
      && run
    '';
    postStop = nixShellRun "dev-stop";
  };
}
