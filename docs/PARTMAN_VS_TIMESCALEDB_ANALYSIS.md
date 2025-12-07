# pg_partman vs TimescaleDB Analysis for OpenStreetMap-NG

**Date:** 2025-12-07
**Status:** Analysis Complete
**Recommendation:** Migration to pg_partman is **favorable** for this project

---

## Executive Summary

Your current TimescaleDB implementation uses **integer/ID-based partitioning** (not time-series), which is actually **misaligned with TimescaleDB's core design**. TimescaleDB is optimized for time-series data and requires timestamp columns for optimal performance. pg_partman with native PostgreSQL partitioning is a better fit for your use case with:

- ✅ Proper support for serial/integer-based partitioning
- ✅ Simpler operational model (fewer background workers, lower lock requirements)
- ✅ Better ecosystem compatibility (standard pg_dump/restore)
- ✅ No proprietary licensing concerns
- ✅ Active maintenance by Crunchy Data

**Trade-offs:**
- ⚠️ Medium-high migration complexity (5 tables, custom query code)
- ⚠️ Need to pre-create partitions (vs TimescaleDB's automatic chunk creation)
- ⚠️ Loss of potential future time-series features (compression, continuous aggregates)

---

## Current Implementation Analysis

### Tables Using TimescaleDB Hypertables

| Table | Partition Column | Chunk Interval | Use Case |
|-------|------------------|----------------|----------|
| `changeset` | `id` (bigint) | 5,000,000 | Monotonically increasing IDs |
| `changeset_bounds` | `changeset_id` | 5,000,000 | FK relationship |
| `element` | `typed_id` | 1,152,921,504,606,846,976 | Very large chunks |
| `note` | `id` (bigint) | 1,000,000 | Monotonically increasing IDs |
| `trace` | `id` (bigint) | 1,000,000 | Monotonically increasing IDs |

### TimescaleDB-Specific Dependencies

```
app/queries/timescaledb_query.py     → queries timescaledb_information.chunks
app/queries/changeset_query.py       → uses TimescaleDBQuery.get_chunks_ranges()
app/queries/trace_query.py           → uses TimescaleDBQuery.get_chunks_ranges()
config/postgres.nix                  → timescaledb.max_background_workers
app/migrations/0.sql                 → tsdb.* table options
```

### Key Observation

**None of your tables use timestamps as partition keys.** This means you're not leveraging TimescaleDB's core value proposition (time-series optimization, time_bucket functions, continuous aggregates).

---

## Detailed Comparison

### 1. Partitioning Model Fit

| Aspect | TimescaleDB | pg_partman | Winner |
|--------|-------------|------------|--------|
| Integer/ID partitioning | Supported but suboptimal | First-class support | **pg_partman** |
| Time-series partitioning | Excellent | Good | TimescaleDB |
| Automatic partition creation | Yes (as data arrives) | Pre-creation required | TimescaleDB |
| Partition naming | Internal management | Predictable `_p#####` suffix | pg_partman |

**Verdict:** pg_partman is designed for your exact use case; TimescaleDB is fighting against its design.

### 2. Operational Complexity

| Aspect | TimescaleDB | pg_partman |
|--------|-------------|------------|
| Background workers | 16 default (configurable) | 1 BGW |
| Lock requirements | 256+ `max_locks_per_transaction` | Standard PostgreSQL |
| Memory overhead | Higher (chunk management) | Minimal |
| Configuration tuning | Complex (`timescaledb-tune`) | Simple |
| Upgrade complexity | Cannot upgrade TS + PG simultaneously | Standard PG upgrades |

**Verdict:** pg_partman has significantly lower operational overhead.

### 3. Ecosystem & Compatibility

| Aspect | TimescaleDB | pg_partman |
|--------|-------------|------------|
| pg_dump/restore | Requires special procedures | Standard PostgreSQL |
| Cloud provider support | Often limited to Apache features | Full support everywhere |
| Other extensions | Some incompatibilities reported | Standard compatibility |
| PgBouncer | Prepared statement issues | No known issues |
| Monitoring | Custom views required | Standard pg_stat_* |

**Verdict:** pg_partman has better ecosystem integration.

### 4. Licensing & Vendor Risk

| Aspect | TimescaleDB | pg_partman |
|--------|-------------|------------|
| License | Apache 2.0 + TSL (dual) | PostgreSQL License |
| Compression | TSL only (not Apache) | N/A (PG native) |
| Continuous aggregates | TSL only | N/A |
| Vendor | Timescale Inc → Tiger Data (renamed 2025) | Crunchy Data |
| Cloud restrictions | TSL restricts DBaaS offerings | None |

**Verdict:** pg_partman has cleaner licensing with no vendor lock-in.

### 5. Performance Characteristics

| Aspect | TimescaleDB | pg_partman |
|--------|-------------|------------|
| Insert throughput | ~225K rows/s | ~320K rows/s (native PG) |
| Simple SELECTs | 40% slower than native PG | Native PG speed |
| Time-series queries | 350x faster (with proper schema) | Standard performance |
| Partition pruning | Automatic | Requires proper constraints |
| Storage overhead | +14% vs vanilla PG | Native PG efficiency |

**Verdict:** For integer-based partitioning, pg_partman/native PG is faster.

### 6. Community & Support

| Aspect | TimescaleDB | pg_partman |
|--------|-------------|------------|
| GitHub stars | ~18k | ~2.5k |
| Release frequency | Monthly | Monthly (7+ releases in 2024-2025) |
| PostgreSQL support | PG 15-18 | PG 12-18 |
| Documentation | Comprehensive | Comprehensive |
| Maintainer | Tiger Data (commercial) | Crunchy Data (PostgreSQL company) |

**Verdict:** Both are well-maintained; TimescaleDB has larger community but pg_partman is backed by PostgreSQL experts.

---

## Migration Assessment

### Code Changes Required

#### 1. Schema Migration (Medium complexity)

Replace TimescaleDB table options with native partitioning:

```sql
-- Before (TimescaleDB)
CREATE TABLE note (
    id bigint GENERATED ALWAYS AS IDENTITY,
    ...
) WITH (
    tsdb.hypertable,
    tsdb.partition_column = 'id',
    tsdb.chunk_interval = '1000000'
);

-- After (pg_partman)
CREATE TABLE note (
    id bigint GENERATED ALWAYS AS IDENTITY,
    ...
) PARTITION BY RANGE (id);

SELECT partman.create_parent(
    p_parent_table => 'public.note',
    p_control => 'id',
    p_type => 'native',
    p_interval => '1000000'
);
```

#### 2. Query Rewrite (Low-Medium complexity)

Replace `timescaledb_information.chunks` queries:

```python
# Before (TimescaleDB)
SELECT range_start_integer, range_end_integer
FROM timescaledb_information.chunks
WHERE hypertable_name = %s

# After (pg_partman / native PG)
SELECT
    (regexp_match(pg_get_expr(c.relpartbound, c.oid),
                  'FROM \((\d+)\) TO \((\d+)\)'))[1]::bigint AS range_start,
    (regexp_match(pg_get_expr(c.relpartbound, c.oid),
                  'FROM \((\d+)\) TO \((\d+)\)'))[2]::bigint - 1 AS range_end
FROM pg_class p
JOIN pg_inherits i ON i.inhparent = p.oid
JOIN pg_class c ON c.oid = i.inhrelid
WHERE p.relname = %s
ORDER BY range_end DESC
```

#### 3. Configuration Changes (Low complexity)

```nix
# Remove from postgres.nix
- timescaledb.max_background_workers = ${toString postgresTimescaleWorkers}
- max_locks_per_transaction = 256
- shared_preload_libraries = '...timescaledb...'

# Add
+ shared_preload_libraries = 'auto_explain,pg_partman_bgw,pg_hint_plan'
+ pg_partman_bgw.interval = 3600  # Run maintenance hourly
```

### Data Migration Strategy

**Recommended: Parallel Table Approach**

1. Create new partitioned tables with `_new` suffix
2. Bulk copy historical data in batches
3. Use triggers or logical replication for ongoing changes
4. Atomic rename during brief maintenance window
5. Keep old tables for rollback (rename to `_old`)

**Estimated effort:**
- Schema changes: 2-4 hours
- Query rewrites: 4-8 hours
- Data migration testing: 8-16 hours
- Production migration: 2-4 hours (with maintenance window)

---

## Risk Analysis

### Risks of Migrating

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Query performance regression | Low | Medium | Benchmark before/after |
| Data migration errors | Low | High | Thorough testing, keep rollback tables |
| Missing edge cases in query rewrite | Medium | Medium | Comprehensive test coverage |
| Partition pre-creation gaps | Medium | Medium | Configure adequate `premake` value |

### Risks of NOT Migrating

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| TimescaleDB breaking changes | Medium | High | Track releases carefully |
| Vendor direction changes | Medium | Medium | None available |
| Operational complexity growth | High | Low | Accept overhead |
| Cloud deployment limitations | High | Medium | Self-host only |

---

## Recommendation

### ✅ Proceed with Migration to pg_partman

**Rationale:**
1. **Architectural Fit**: Your integer-based partitioning is a natural fit for pg_partman and a mismatch for TimescaleDB
2. **Operational Simplicity**: Fewer moving parts, standard PostgreSQL tooling
3. **Future-Proofing**: No proprietary dependencies, better cloud portability
4. **Performance**: Native PostgreSQL performance without hypertable overhead

### Migration Priority

| Table | Priority | Rationale |
|-------|----------|-----------|
| `note` | High | Simplest schema, good test case |
| `trace` | High | Similar to note, validates approach |
| `changeset` | Medium | More indexes, moderate complexity |
| `changeset_bounds` | Medium | FK relationship considerations |
| `element` | Low | Very large chunks, may not need partitioning at all |

### Suggested Timeline

1. **Phase 1**: Migrate `note` and `trace` tables (lower risk, validate approach)
2. **Phase 2**: Migrate `changeset` and `changeset_bounds` (apply learnings)
3. **Phase 3**: Evaluate `element` table (consider if partitioning is necessary given huge chunk size)

---

## Alternative: Remove Partitioning Entirely

Given that your partitioning is ID-based and PostgreSQL B-tree indexes on bigint are extremely efficient, consider whether partitioning provides meaningful benefits:

**When partitioning helps:**
- Tables with billions of rows where you frequently query recent data
- Need to drop old data efficiently (DROP PARTITION vs DELETE)
- Parallel query execution across partitions

**When it may not be needed:**
- Queries typically filter by indexed columns other than partition key
- Data retention is not a concern
- Table size is manageable (<100GB)

If your primary use of `TimescaleDBQuery.get_chunks_ranges()` is just for query optimization, native PostgreSQL index scans may be sufficient.

---

## Appendix: Quick Reference

### pg_partman Key Functions

```sql
-- Create partitioned parent table
SELECT partman.create_parent('schema.table', 'partition_column', 'native', 'interval');

-- View partition info
SELECT * FROM partman.part_config;

-- Run maintenance manually
SELECT partman.run_maintenance();

-- Get partition boundaries
SELECT * FROM partman.show_partitions('schema.table');
```

### PostgreSQL Native Partition Queries

```sql
-- List all partitions
SELECT c.relname, pg_get_expr(c.relpartbound, c.oid)
FROM pg_class p
JOIN pg_inherits i ON p.oid = i.inhparent
JOIN pg_class c ON c.oid = i.inhrelid
WHERE p.relname = 'parent_table';

-- Check if partition pruning is working
EXPLAIN (COSTS OFF) SELECT * FROM parent_table WHERE id = 12345;
```

---

## Sources

- [pg_partman GitHub](https://github.com/pgpartman/pg_partman)
- [pg_partman Documentation](https://pgxn.org/dist/pg_partman/doc/pg_partman.html)
- [Crunchy Data: Native Partitioning with pg_partman](https://www.crunchydata.com/blog/native-partitioning-with-postgres)
- [AWS: Managing PostgreSQL partitions with pg_partman](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL_Partitions.html)
- [Tiger Data: pg_partman vs Hypertables](https://www.tigerdata.com/learn/pg_partman-vs-hypertables-for-postgres-partitioning)
- [TimescaleDB Documentation](https://docs.tigerdata.com/)
- [TimescaleDB GitHub Releases](https://github.com/timescale/timescaledb/releases)
- [PostgreSQL Partitioning Documentation](https://www.postgresql.org/docs/current/ddl-partitioning.html)
