{ hostMemoryMb
, hostDiskCoW
, postgresCpuThreads
, postgresMinWalSizeGb
, postgresMaxWalSizeGb
, postgresVerbose
, pkgs
, projectDir
}:

pkgs.writeText "postgres.conf" (''
  # change default port
  # reason: avoid conflicts with other services
  port = 49560

  # listen on socket
  # reason: reduce latency
  unix_socket_directories = '${projectDir}/data/postgres_unix'

  # increase buffers and memory usage
  shared_buffers = ${toString (builtins.floor (hostMemoryMb / 4))}MB
  effective_cache_size = ${toString (builtins.floor (hostMemoryMb / 2))}MB
  work_mem = 64MB
  hash_mem_multiplier = 4.0
  maintenance_work_mem = 1024MB
  vacuum_buffer_usage_limit = 256MB

  # use UTC timezone
  timezone = 'UTC'

  # disable parallel gather:
  # introduces noticeable overhead and is never useful
  # we only perform relatively small queries and rely heavily on indexes
  max_parallel_workers_per_gather = 0

  # use one worker per CPU thread
  max_worker_processes = ${toString postgresCpuThreads}
  max_parallel_workers = ${toString postgresCpuThreads}
  max_parallel_maintenance_workers = ${toString postgresCpuThreads}
  # SOON: timescaledb.max_background_workers = ${toString postgresCpuThreads}

  # timescaledb require open-source license and disable telemetry
  # SOON: timescaledb.license = apache
  # SOON: timescaledb.telemetry_level = off

  # increase statistics target
  # reason: more accurate query plans
  default_statistics_target = 1000

  # increase max connections
  max_connections = 10000

  # detect disconnected clients
  # reason: safeguard resource usage
  client_connection_check_interval = 5s

  # disconnect idle clients with open transactions
  # reason: safeguard resource usage
  idle_in_transaction_session_timeout = 5min

  # change toast compression
  # reason: minimal overhead compression
  default_toast_compression = lz4

  # disable replication and reduce WAL usage
  # reason: unused, reduced resource usage
  wal_level = minimal
  max_wal_senders = 0

  # compress WAL logs
  # reason: reduced IO usage, higher throughput
  wal_compression = zstd

  # group WAL commits during high load (delay 20ms)
  # reason: higher throughput
  commit_delay = 20000
  commit_siblings = 5

  # reduce checkpoint frequency
  # reason: higher chance of vacuuming in-memory, reduced WAL usage
  checkpoint_timeout = 1h

  # print early checkpoint warnings
  # reason: detect too-frequent checkpoints
  checkpoint_warning = 30min

  # limit min WAL size
  # reason: prefer file recycling
  min_wal_size = ${toString postgresMinWalSizeGb}GB

  # increase max WAL size
  # reason: reduce checkpoint frequency
  max_wal_size = ${toString postgresMaxWalSizeGb}GB

  # adjust configuration for SSDs
  # reason: improved performance on expected hardware
  random_page_cost = 1
'' + pkgs.lib.optionalString (!pkgs.stdenv.isDarwin) ''
  effective_io_concurrency = 200
  maintenance_io_concurrency = 200
'' + ''

'' + pkgs.lib.optionalString hostDiskCoW ''
  # optimize for Copy-On-Write storage
  wal_init_zero = off
  wal_recycle = off
'' + ''

  # increase logging verbosity
  # reason: useful for troubleshooting
'' + pkgs.lib.optionalString (postgresVerbose >= 2) ''
  log_connections = on
  log_disconnections = on
  log_statement = 'all'
  log_lock_waits = on
  log_temp_files = 0 # == log all temp files
'' + pkgs.lib.optionalString (postgresVerbose == 1) ''
  log_statement = 'ddl'
  log_lock_waits = on
'' + ''

  # configure autovacuum to use absolute thresholds
  # reason: more frequent vacuuming, predictable behavior
  autovacuum_max_workers = 4
  autovacuum_naptime = 3min
  autovacuum_vacuum_scale_factor = 0.0
  autovacuum_vacuum_threshold = 500
  autovacuum_vacuum_insert_scale_factor = 0.0
  autovacuum_vacuum_insert_threshold = 1000
  autovacuum_analyze_scale_factor = 0.0
  autovacuum_analyze_threshold = 1000

  # configure additional libraries
  shared_preload_libraries = 'auto_explain' # SOON: ,timescaledb

  # automatically explain slow queries
  # reason: useful for troubleshooting
  auto_explain.log_min_duration = 100ms
'')
