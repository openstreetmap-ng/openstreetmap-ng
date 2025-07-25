{
  hostMemoryMb,
  hostDiskCoW,
  postgresPort,
  postgresSharedBuffersPerc,
  postgresWorkMemMb,
  postgresWorkers,
  postgresParallelWorkers,
  postgresParallelMaintenanceWorkers,
  postgresAutovacuumWorkers,
  postgresTimescaleWorkers,
  postgresIOConcurrency,
  postgresRandomPageCost,
  postgresMinWalSizeGb,
  postgresMaxWalSizeGb,
  postgresVerbose,
  fastIngest ? false,
  pkgs,
  projectDir,
}:

let
  postgresSharedBuffersMb = builtins.floor (hostMemoryMb * postgresSharedBuffersPerc);
in
with pkgs;
writeText "postgres.conf" (
  ''
    # configure listen interfaces
    port = ${toString postgresPort}
    unix_socket_directories = '${projectDir}/data/postgres_unix'

    # increase buffers and memory usage
    shared_buffers = ${toString postgresSharedBuffersMb}MB
    effective_cache_size = ${
      toString (
        postgresSharedBuffersMb + builtins.floor (hostMemoryMb * (1 - postgresSharedBuffersPerc) / 3)
      )
    }MB
    work_mem = ${toString postgresWorkMemMb}MB
    hash_mem_multiplier = 4.0
    maintenance_work_mem = ${
      toString (
        builtins.floor (
          (hostMemoryMb - postgresSharedBuffersMb)
          / (
            postgresParallelWorkers
            + (postgresParallelWorkers / postgresParallelMaintenanceWorkers)
            + postgresAutovacuumWorkers
          )
          * 0.6
        )
      )
    }MB
    vacuum_buffer_usage_limit = ${toString (builtins.floor (postgresSharedBuffersMb / 8))}MB

    # use UTC timezone
    timezone = UTC

    # configure number of workers
    max_worker_processes = ${toString postgresWorkers}
    max_parallel_workers = ${toString postgresParallelWorkers}
    max_parallel_workers_per_gather = 0
    max_parallel_maintenance_workers = ${toString postgresParallelMaintenanceWorkers}
  ''
  + (
    if postgresAutovacuumWorkers >= 1 then
      ''
        autovacuum_max_workers = ${toString postgresAutovacuumWorkers}
      ''
    else
      ''
        autovacuum = off
      ''
  )
  + ''
    timescaledb.max_background_workers = ${toString postgresTimescaleWorkers}

    # increase the maximum number of locks
    # reason: timescaledb requires 1 lock per chunk
    max_locks_per_transaction = 256

    # more aggressive autovacuum
    autovacuum_vacuum_scale_factor = 0.1
    autovacuum_vacuum_insert_scale_factor = 0.1

    # increase statistics target
    # reason: more accurate query plans
    default_statistics_target = 200

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

    # more responsive bgwriter
    # reason: avoid backend stalls during high load
    bgwriter_delay = 100ms
    bgwriter_lru_maxpages = 1000  # 80MB/s
    bgwriter_lru_multiplier = 4.0

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
    random_page_cost = ${toString postgresRandomPageCost}
  ''
  + lib.optionalString (!stdenv.isDarwin) ''
    effective_io_concurrency = ${toString postgresIOConcurrency}
    maintenance_io_concurrency = ${toString postgresIOConcurrency}
  ''
  + ''

  ''
  + lib.optionalString hostDiskCoW ''
    # optimize for Copy-On-Write storage
    wal_init_zero = off
    wal_recycle = off
    full_page_writes = off
  ''
  + ''

    # increase logging verbosity
    # reason: useful for troubleshooting
  ''
  + lib.optionalString (postgresVerbose >= 2) ''
    log_connections = on
    log_disconnections = on
    log_statement = all
    log_lock_waits = on
    log_temp_files = 0 # == log all temp files
  ''
  + lib.optionalString (postgresVerbose == 1) ''
    log_statement = ddl
    log_lock_waits = on
  ''
  + ''

    # configure additional libraries
    shared_preload_libraries = 'auto_explain,timescaledb,pg_hint_plan'

    # automatically explain slow queries
    # reason: useful for troubleshooting
    auto_explain.log_min_duration = 200ms

    # disable telemetry
    timescaledb.telemetry_level = off

  ''
  + lib.optionalString fastIngest ''
    # optimize for fast ingest
    bgwriter_flush_after = 0
    bgwriter_lru_maxpages = 1073741823
    checkpoint_completion_target = 0
    checkpoint_flush_after = 0
    fsync = off
    full_page_writes = off
    synchronous_commit = off
    wal_buffers = 16384  # 128MB
    wal_skip_threshold = 0
    wal_writer_delay = 10s
    wal_writer_flush_after = 131071
  ''
)
