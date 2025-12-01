{
  isDevelopment,
  enablePostgres,
  enableMailpit,
  mailpitHttpPort,
  mailpitSmtpPort,
  pkgs,
  postgresConf,
}:

with pkgs;
let
  # Render multiline commands for readability in Nix, but
  # normalize them to a single-line string for Process Compose.
  mkMultiline = cmd: lib.replaceStrings [ "\\\n" ] [ " " ] cmd;

  availability = {
    restart = "on_failure";
  };

  log_configuration = {
    fields_order = [ "message" ];
    disable_json = true;
    no_color = true;
    flush_each_line = true;
    rotation = {
      max_size_mb = 20;
      max_age_days = 7;
      max_backups = 10;
    };
  };

  postgresProcess = {
    postgres = {
      availability = availability;
      command = mkMultiline ''
        postgres \
          -c config_file=${postgresConf} \
          -D data/postgres
      '';
      ready_log_line = "database system is ready to accept connections";
      log_location = "data/pcompose/postgres.log";
      log_configuration = log_configuration // {
        no_metadata = true;
      };
      shutdown = {
        signal = 2; # SIGINT
        timeout_seconds = 600;
      };
    };
  };

  mailpitProcess = {
    mailpit = {
      availability = availability;
      command = mkMultiline ''
        mailpit \
          -d data/mailpit/mailpit.db \
          -l "localhost:${toString mailpitHttpPort}" \
          -s "localhost:${toString mailpitSmtpPort}" \
          --smtp-auth-accept-any \
          --smtp-auth-allow-insecure \
          --enable-spamassassin spamassassin.monicz.dev:783
      '';
      ready_log_line = "[http] accessible via ";
      log_location = "data/pcompose/mailpit.log";
      log_configuration = log_configuration // {
        no_metadata = true;
      };
    };
  };

  developmentProcesses = {
    watch-proto = {
      availability = availability;
      command = "watch-proto";
      ready_log_line = "[Command was successful]";
    };
    watch-locale = {
      availability = availability;
      command = "watch-locale";
      ready_log_line = "[Command was successful]";
    };
    vite = {
      availability = availability;
      command = "vite";
      ready_log_line = " ready in ";
      depends_on = {
        watch-proto = {
          condition = "process_log_ready";
        };
        watch-locale = {
          condition = "process_log_ready";
        };
      };
      log_configuration = log_configuration // {
        no_metadata = true;
      };
    };
  };

in
writeText "process-compose.yaml" (
  builtins.toJSON {
    version = "0.5";
    is_strict = true;
    is_tui_disabled = true;
    log_location = "data/pcompose/global.log";
    log_configuration = log_configuration;
    processes =
      { }
      // lib.optionalAttrs enablePostgres postgresProcess
      // lib.optionalAttrs enableMailpit mailpitProcess
      // lib.optionalAttrs isDevelopment developmentProcesses;
  }
)
