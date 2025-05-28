{ isDevelopment
, enablePostgres
, enableMailpit
, mailpitHttpPort
, mailpitSmtpPort
, pkgs
, postgresConf
}:

with pkgs; writeText "supervisord.conf" (''
  [supervisord]
  logfile=data/supervisor/supervisord.log
  pidfile=data/supervisor/supervisord.pid
  strip_ansi=true

'' + lib.optionalString enablePostgres ''
  [program:postgres]
  command=postgres
    -c config_file=${postgresConf}
    -D data/postgres
  stdout_logfile=data/supervisor/postgres.log
  stderr_logfile=data/supervisor/postgres.log

'' + lib.optionalString enableMailpit ''
  [program:mailpit]
  command=mailpit -d data/mailpit/mailpit.db
    -l "127.0.0.1:${toString mailpitHttpPort}"
    -s "127.0.0.1:${toString mailpitSmtpPort}"
    --smtp-auth-accept-any
    --smtp-auth-allow-insecure
    --enable-spamassassin spamassassin.monicz.dev:783
  stdout_logfile=data/supervisor/mailpit.log
  stderr_logfile=data/supervisor/mailpit.log

'' + lib.optionalString isDevelopment ''
  [program:watch-js]
  command=watch-js
  stdout_logfile=data/supervisor/watch-js.log
  stderr_logfile=data/supervisor/watch-js.log

  [program:watch-locale]
  command=watch-locale
  stdout_logfile=data/supervisor/watch-locale.log
  stderr_logfile=data/supervisor/watch-locale.log

  [program:watch-proto]
  command=watch-proto
  stdout_logfile=data/supervisor/watch-proto.log
  stderr_logfile=data/supervisor/watch-proto.log

  [program:watch-css]
  command=watch-css
  stdout_logfile=data/supervisor/watch-css.log
  stderr_logfile=data/supervisor/watch-css.log
'')
