{ pkgs, ... }:

# Service configuration for OSM-NG testing instance
# Specs: hmad.large (4T, 32GB RAM, 100GB SSD) + 1000GB SSD
# https://cloudferro.com/pricing/virtual-machines-vm-2/

let
  commonServiceConfig = {
    User = "osm-ng";
    WorkingDirectory = "/data/osm-ng";

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
  nixShellRun = script: ''
    NIX_PATH="nixpkgs=/nix/var/nix/profiles/per-user/root/channels/nixos:/nix/var/nix/profiles/per-user/root/channels" \
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

  systemd.services.osm-ng-dev = {
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];
    unitConfig = {
      StartLimitIntervalSec = "infinity";
      StartLimitBurst = 30;
    };
    serviceConfig = pkgs.lib.mkMerge [
      commonServiceConfig
      {
        Type = "oneshot";
        RemainAfterExit = true;
        Restart = "on-failure";
        RestartSec = "30s";
      }
    ];
    script = nixShellRun "static-precompress && dev-start";
    preStop = nixShellRun "dev-stop";
  };

  systemd.services.osm-ng = {
    enable = false;
    after = [ "osm-ng-dev.service" ];
    bindsTo = [ "osm-ng-dev.service" ];
    wantedBy = [ "default.target" ];
    unitConfig = {
      StartLimitIntervalSec = "infinity";
      StartLimitBurst = 30;
    };
    serviceConfig = pkgs.lib.mkMerge [
      commonServiceConfig
      {
        Type = "exec";
        Restart = "on-failure";
        RestartSec = "30s";
      }
    ];
    script = nixShellRun ''
      APP_URL=https://openstreetmap.ng \
      API_URL=https://api.openstreetmap.ng \
      ID_URL=https://id.openstreetmap.ng \
      RAPID_URL=https://rapid.openstreetmap.ng \
      FORCE_CRASH_REPORTING=1 \
      run
    '';
  };

  systemd.services.osm-ng-replication = {
    enable = false;
    after = [ "osm-ng-dev.service" ];
    bindsTo = [ "osm-ng-dev.service" ];
    wantedBy = [ "default.target" ];
    unitConfig = {
      StartLimitIntervalSec = "infinity";
      StartLimitBurst = 30;
    };
    serviceConfig = pkgs.lib.mkMerge [
      commonServiceConfig
      {
        Type = "exec";
        Nice = 10;
        Restart = "on-failure";
        RestartSec = "30s";
      }
    ];
    script = nixShellRun "replication";
  };
}
