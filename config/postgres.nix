{ pkgs, projectDir }:

# ( Developer Configuration )
# ===========================
# Targeted Specification:
# - 8 CPU Threads
# - 8GB RAM
# - 300GB SSD

pkgs.writeText "postgres.conf" (''
  # change default port
  # reason: avoid conflicts with other services
  port = 49560

  # listen on socket
  # reason: reduce latency
  unix_socket_directories = '${projectDir}/data/postgres_unix'

  # increase buffers and memory usage
  shared_buffers = 2GB
  effective_cache_size = 4GB
  work_mem = 64MB
  maintenance_work_mem = 1GB
  vacuum_buffer_usage_limit = 256MB

  # disable parallel gather:
  # introduces noticeable overhead and is never useful
  # we only perform relatively small queries and rely heavily on indexes
  max_parallel_workers_per_gather = 0

  # allow maintenance to use all workers
  max_parallel_maintenance_workers = 8

  # increase statistics target
  # reason: more accurate query plans
  default_statistics_target = 500

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
  # reason: higher chance of vaccuming in-memory, reduced WAL usage
  checkpoint_timeout = 1h

  # print early checkpoint warnings
  # reason: detect too-frequent checkpoints
  checkpoint_warning = 30min

  # increase max WAL size
  # reason: reduce checkpoint frequency
  max_wal_size = 20GB

  # limit min WAL size
  # reason: prefer file recycling
  min_wal_size = 1GB

  # adjust configuration for SSDs
  # reason: improved performance on expected hardware
  random_page_cost = 1
'' + pkgs.lib.optionalString (!pkgs.stdenv.isDarwin) ''
  effective_io_concurrency = 200
  maintenance_io_concurrency = 200
'' + ''

# increase logging verbosity
# reason: useful for troubleshooting
log_connections = on
log_disconnections = on
log_lock_waits = on
log_temp_files = 0 # == log all temp files

# configure autovacuum to use absolute thresholds
# reason: more frequent vacuuming, predictable behavior
autovacuum_max_workers = 3
autovacuum_naptime = 3min
autovacuum_vacuum_scale_factor = 0.0
autovacuum_vacuum_threshold = 500
autovacuum_vacuum_insert_scale_factor = 0.0
autovacuum_vacuum_insert_threshold = 1000
autovacuum_analyze_scale_factor = 0.0
autovacuum_analyze_threshold = 1000

# configure additional libraries
shared_preload_libraries = 'auto_explain'

# automatically explain slow queries
# reason: useful for troubleshooting
auto_explain.log_min_duration = 100ms
'')
