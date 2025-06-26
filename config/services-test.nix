{ pkgs, ... }:

# Service configuration for OSM-NG testing instance
# Specs: hmad.large (4T, 32GB RAM, 100GB SSD) + 4000GB SSD
# https://cloudferro.com/pricing/virtual-machines-vm-2/

let
  commonServiceConfig = {
    User = "osm-ng";
    WorkingDirectory = "/data/osm-ng";

    ProtectSystem = "strict";
    ReadWritePaths = [
      "/home/osm-ng"
      "/data/osm-ng"
      "/data/tmp"
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
    RestrictAddressFamilies = [
      "AF_UNIX"
      "AF_INET"
      "AF_INET6"
    ];
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
      --arg hostMemoryMb 29886 \
      --arg hostDiskCoW true \
      --arg postgresParallelWorkers 4 \
      --arg postgresParallelWorkersPerGather 1 \
      --arg postgresParallelMaintenanceWorkers 1 \
      --arg postgresMaxWalSizeGb 50 \
      --arg postgresVerbose 1 \
      --arg gunicornWorkers 3 \
      --run "
        export ENV=test \
        && export APP_URL=https://www.openstreetmap.ng \
        && export API_URL=https://api.openstreetmap.ng \
        && export LEGACY_ALLOW_MISSING_ELEMENT_MEMBERS=1 \
        && ${script}"
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
        Nice = -10;
        RemainAfterExit = true;
        Restart = "on-failure";
        RestartSec = "30s";
      }
    ];
    script = nixShellRun "css-pipeline && js-pipeline && static-precompress && dev-start";
    preStop = nixShellRun "dev-stop";
  };

  systemd.services.osm-ng = {
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
        Nice = -5;
        Restart = "on-failure";
        RestartSec = "30s";
      }
    ];
    script = nixShellRun "run";
  };

  systemd.services.osm-ng-http =
    let
      caddyArgs = "--config config/Caddyfile";
    in
    {
      after = [ "osm-ng.service" ];
      bindsTo = [ "osm-ng.service" ];
      wantedBy = [ "default.target" ];
      unitConfig = {
        StartLimitIntervalSec = "infinity";
        StartLimitBurst = 30;
      };
      serviceConfig = pkgs.lib.mkMerge [
        (removeAttrs commonServiceConfig [
          "CapabilityBoundingSet"
          "PrivateUsers"
        ])
        {
          Type = "exec";
          Nice = -3;
          Restart = "on-failure";
          RestartPreventExitStatus = 1;
          RestartSec = "5s";
          ExecStartPre = "${pkgs.toybox}/bin/mkdir -p data/caddy";
          ExecReload = "${pkgs.caddy}/bin/caddy reload --force ${caddyArgs}";
          CapabilityBoundingSet = "CAP_NET_BIND_SERVICE";
          AmbientCapabilities = "CAP_NET_BIND_SERVICE";
        }
      ];
      script = "${pkgs.caddy}/bin/caddy run ${caddyArgs}";
    };

  systemd.services.osm-ng-replication-generate-hour = {
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
        Nice = 5;
        Restart = "on-failure";
        RestartSec = "30s";
      }
    ];
    script = nixShellRun "replication-generate hour --no-backfill";
  };

  systemd.services.osm-ng-replication-download = {
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
    script = nixShellRun "replication-download";
  };
}
