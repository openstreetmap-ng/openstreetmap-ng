{ pkgs, projectDir, makeScript, python }:
{
  python = with pkgs; symlinkJoin {
    name = "python";
    paths = [
      python
      (
        let
          inner = makeScript "inner" ''
            BASH_ARGV0=$1
            shift
            # shellcheck disable=SC1091
            source ${python}/bin/python3.12
          '';
        in
        makeScript "python-sandbox" ''
          args=()
          while IFS="=" read -r -d "" name value; do
              args+=(--setenv "$name=$value")
          done < <(env -0) # --quiet \
          exec systemd-run \
            --collect \
            --user \
            --same-dir \
            --send-sighup \
            --service-type=exec \
            --pipe \
            --wait \
            "''${args[@]}" \
            -p NoExecPaths="/" \
            -p ExecPaths="/nix/store" \
            -p ReadWritePaths="${projectDir}" \
            -p KeyringMode=private \
            -p LockPersonality=yes \
            -p NoNewPrivileges=yes \
            -p PrivateDevices=yes \
            -p PrivateTmp=yes \
            -p PrivateUsers=yes \
            -p ProtectClock=yes \
            -p ProtectControlGroups=yes \
            -p ProtectHome=read-only \
            -p ProtectHostname=yes \
            -p ProtectKernelLogs=yes \
            -p ProtectKernelModules=yes \
            -p ProtectKernelTunables=yes \
            -p ProtectProc=noaccess \
            -p ProtectSystem=strict \
            -p RestrictRealtime=yes \
            -p RestrictSUIDSGID=yes \
            -p SystemCallArchitectures=native \
            -p SystemCallFilter=~@clock \
            -p SystemCallFilter=~@cpu-emulation \
            -p SystemCallFilter=~@debug \
            -p SystemCallFilter=~@module \
            -p SystemCallFilter=~@mount \
            -p SystemCallFilter=~@obsolete \
            -p SystemCallFilter=~@raw-io \
            -p SystemCallFilter=~@reboot \
            -p SystemCallFilter=~@swap \
            -p UMask=0077 \
            ${inner}/bin/inner "$0" "$@"
        ''
      )
    ];
    postBuild = ''
      rm "$out/bin/.python3.12-wrapped"
      ln -sf python-sandbox "$out/bin/python3.12"
    '';
  };
}
