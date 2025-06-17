{
  hostMemoryMb,
  hostDiskCoW,
  postgresPort,
  postgresCpuThreads,
  postgresMinWalSizeGb,
  postgresMaxWalSizeGb,
  postgresFullPageWrites,
  postgresVerbose,
  fastIngest ? false,
  pkgs,
  projectDir,
}:

with pkgs;
writeText "postgres.conf" (
  ''
    # configure listen interfaces
    port = ${toString postgresPort}
    unix_socket_directories = '${projectDir}/data/postgres_unix'

    # increase buffers and memory usage
    shared_buffers = ${toString (builtins.floor (hostMemoryMb / 4))}MB
    effective_cache_size = ${toString (builtins.floor (hostMemoryMb / 2))}MB
    work_mem = 64MB
    hash_mem_multiplier = 4.0
    maintenance_work_mem = ${toString (builtins.floor (hostMemoryMb / postgresCpuThreads / 1.5))}MB
    vacuum_buffer_usage_limit = ${toString (builtins.floor (hostMemoryMb / 32))}MB

    # use UTC timezone
    timezone = 'UTC'

    # disable parallel gather:
    # introduces noticeable overhead and is never useful
    # we only perform relatively small queries and rely heavily on indexes
    max_parallel_workers_per_gather = 0

    # configure number of workers
    max_worker_processes = ${toString postgresCpuThreads}
    max_parallel_workers = ${toString postgresCpuThreads}
    max_parallel_maintenance_workers = ${toString postgresCpuThreads}
    # SOON: timescaledb.max_background_workers = ${toString postgresCpuThreads}
    autovacuum_max_workers = ${toString (builtins.floor (postgresCpuThreads / 2))}

    # timescaledb require open-source license and disable telemetry
    # SOON: timescaledb.license = apache
    # SOON: timescaledb.telemetry_level = off

    # more aggressive autovacuum
    autovacuum_vacuum_scale_factor = 0.1
    autovacuum_vacuum_insert_scale_factor = 0.1

    # increase statistics target
    # reason: more accurate query plans
    default_statistics_target = 500

    # increase max connections
    max_connections = 500

    # detect disconnected clients
    # reason: safeguard resource usage
    client_connection_check_interval = 5s

    # disconnect idle clients with open transactions
    # reason: safeguard resource usage
    idle_in_transaction_session_timeout = 10min

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
    random_page_cost = 1.1
  ''
  + lib.optionalString (!stdenv.isDarwin) ''
    effective_io_concurrency = 200
    maintenance_io_concurrency = 200
  ''
  + "\n"
  + lib.optionalString hostDiskCoW ''
    # optimize for Copy-On-Write storage
    wal_init_zero = off
    wal_recycle = off
  ''
  + ''
    full_page_writes = ${if postgresFullPageWrites then "on" else "off"}

    # increase logging verbosity
    # reason: useful for troubleshooting
  ''
  + lib.optionalString (postgresVerbose >= 2) ''
    log_connections = on
    log_disconnections = on
    log_statement = 'all'
    log_lock_waits = on
    log_temp_files = 0 # == log all temp files
  ''
  + lib.optionalString (postgresVerbose == 1) ''
    log_statement = 'ddl'
    log_lock_waits = on
  ''
  + ''

    # configure additional libraries
    shared_preload_libraries = 'auto_explain' # SOON: ,timescaledb

    # automatically explain slow queries
    # reason: useful for troubleshooting
    auto_explain.log_min_duration = 200ms

  ''
  + lib.optionalString fastIngest ''
    autovacuum = off
    bgwriter_lru_maxpages = 0
    checkpoint_completion_target = 0
    fsync = off
    full_page_writes = off
    synchronous_commit = off
    wal_buffers = 262143
    wal_writer_delay = 10s
    wal_writer_flush_after = 131071
  ''
)
