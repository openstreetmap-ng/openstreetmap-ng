import logging
from asyncio import Semaphore, TaskGroup
from math import ceil
from operator import itemgetter
from pathlib import Path
from typing import NamedTuple

from packaging.version import Version
from psycopg import AsyncConnection
from psycopg.sql import SQL, Identifier

from app.config import ENV
from app.db import db
from app.lib.crypto import hash_bytes
from app.models.element import (
    TYPED_ELEMENT_ID_NODE_MIN,
    TYPED_ELEMENT_ID_RELATION_MIN,
    TYPED_ELEMENT_ID_WAY_MIN,
    typed_element_id,
)
from app.queries.element_query import ElementQuery
from app.services.admin_task_service import register_admin_task
from app.utils import calc_num_workers


class _MigrationInfo(NamedTuple):
    version: Version
    hash: bytes


_MIGRATION_HASH_SIZE = 7
_MIGRATIONS_DIR = Path('app/migrations')


class MigrationService:
    @staticmethod
    async def fix_sequence_counters() -> None:
        """Fix the sequence counters."""
        async with db(True, autocommit=True) as conn:
            # For each table, get the correct sequence name and then set its value
            async with await conn.execute("""
                SELECT
                    table_name,
                    column_name,
                    pg_get_serial_sequence(table_name, column_name)
                FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name IN ('user', 'changeset', 'element', 'note', 'note_comment')
                AND identity_generation = 'ALWAYS'
            """) as r:
                sequences: list[tuple[str, str, str]] = await r.fetchall()

            for table, column, sequence in sequences:
                query = SQL('SELECT MAX({}) FROM {}').format(
                    Identifier(column), Identifier(table)
                )
                async with await conn.execute(query) as r:
                    row: tuple[int] | None = await r.fetchone()
                    if row is None:
                        continue

                last_value = row[0]
                logging.debug('Setting sequence counter %r to %d', sequence, last_value)
                await conn.execute('SELECT setval(%s, %s)', (sequence, last_value))

    @staticmethod
    async def deduplicate_elements(
        *,
        parallelism: int | float = 2.0,
        batch_size: int = 1_000_000,
    ) -> None:
        parallelism = calc_num_workers(parallelism)

        batches = _get_element_typed_id_batches(
            await _get_element_typed_id_ranges(), batch_size
        )
        semaphore = Semaphore(parallelism)
        logging.info(
            'Deduplicating elements (batches=%d, parallelism=%d)',
            len(batches),
            parallelism,
        )

        async def process_task(start_id: int, end_id: int):
            async with (
                semaphore,
                db(True, autocommit=True) as conn,
                await conn.execute(
                    """
                    WITH bad AS (
                        SELECT sequence_id
                        FROM (
                            SELECT
                                sequence_id,
                                ROW_NUMBER() OVER (PARTITION BY typed_id, version) AS rn
                            FROM element
                            WHERE typed_id BETWEEN %s AND %s
                        ) sub
                        WHERE rn > 1
                    )
                    DELETE FROM element e USING bad
                    WHERE e.sequence_id = bad.sequence_id
                    RETURNING e.sequence_id, e.typed_id, e.version
                """,
                    (start_id, end_id),
                ) as r,
            ):
                if rows := await r.fetchall():
                    logging.warning(
                        'Deduplicated %d elements in range [%d, %d]',
                        len(rows),
                        start_id,
                        end_id,
                    )

        async with TaskGroup() as tg:
            for start_id, end_id in batches:
                tg.create_task(process_task(start_id, end_id))

    @staticmethod
    async def mark_latest_elements(
        *,
        parallelism: int | float = 2.0,
        batch_size: int = 1_000_000,
    ) -> None:
        parallelism = calc_num_workers(parallelism)

        batches = _get_element_typed_id_batches(
            await _get_element_typed_id_ranges(), batch_size
        )
        semaphore = Semaphore(parallelism)
        logging.info(
            'Marking latest elements (batches=%d, parallelism=%d)',
            len(batches),
            parallelism,
        )

        async def process_task(start_id: int, end_id: int):
            async with semaphore, db(True, autocommit=True) as conn:
                await conn.execute(
                    """
                    WITH bad AS (
                        SELECT * FROM (
                            SELECT DISTINCT ON (typed_id) typed_id, version, latest
                            FROM element
                            WHERE typed_id BETWEEN %s AND %s
                            ORDER BY typed_id, version DESC
                        )
                        WHERE NOT latest
                    )
                    UPDATE element e SET latest = TRUE FROM bad
                    WHERE e.typed_id = bad.typed_id
                    AND e.version = bad.version
                    """,
                    (start_id, end_id),
                )

        async with TaskGroup() as tg:
            for start_id, end_id in batches:
                tg.create_task(process_task(start_id, end_id))

    @staticmethod
    @register_admin_task
    async def delete_notes_without_comments(
        *,
        parallelism: int | float = 2.0,
        batch_size: int = 100_000,
    ) -> None:
        parallelism = calc_num_workers(parallelism)

        async with (
            db() as conn,
            await conn.execute('SELECT COALESCE(MAX(id), 0) FROM note') as r,
        ):
            max_id = (await r.fetchone())[0]  # type: ignore

        semaphore = Semaphore(parallelism)
        logging.info(
            'Deleting notes without comments (batches=%d, parallelism=%d)',
            ceil(max_id / batch_size),
            parallelism,
        )

        async def process_chunk(start_id: int, end_id: int):
            async with semaphore, db(True) as conn:
                await conn.execute(
                    """
                    DELETE FROM note
                    WHERE id BETWEEN %s AND %s
                    AND NOT EXISTS (
                        SELECT 1 FROM note_comment
                        WHERE note_id = note.id
                    )
                    """,
                    (start_id, end_id),
                )

        async with TaskGroup() as tg:
            for start_id in range(1, max_id + 1, batch_size):
                end_id = min(start_id + batch_size - 1, max_id)
                tg.create_task(process_chunk(start_id, end_id))

    @staticmethod
    @register_admin_task
    async def fix_changeset_counts(
        *,
        parallelism: int | float = 2.0,
        batch_size: int = 1_000_000,
    ) -> None:
        """
        Fix changeset counts where size != 0 but num_create = 0, num_modify = 0, and num_delete = 0.
        Calculates the counts based on the actual data in the element table.
        """
        parallelism = calc_num_workers(parallelism)

        async with (
            db() as conn,
            await conn.execute('SELECT COALESCE(MAX(id), 0) FROM changeset') as r,
        ):
            max_id = (await r.fetchone())[0]  # type: ignore

        semaphore = Semaphore(parallelism)
        logging.info(
            'Fixing inconsistent changeset counts (batches=%d, parallelism=%d)',
            ceil(max_id / batch_size),
            parallelism,
        )

        async def process_chunk(start_id: int, end_id: int):
            async with semaphore, db(True) as conn:
                await conn.execute(
                    """
                    WITH good AS (
                        SELECT
                            changeset_id,
                            COUNT(*) AS size,
                            COUNT(*) FILTER (WHERE version = 1) AS num_create,
                            COUNT(*) FILTER (WHERE version > 1 AND visible) AS num_modify,
                            COUNT(*) FILTER (WHERE version > 1 AND NOT visible) AS num_delete
                        FROM element
                        WHERE changeset_id BETWEEN %s AND %s
                        GROUP BY changeset_id
                        HAVING EXISTS (
                            SELECT 1 FROM changeset
                            WHERE id = changeset_id
                            AND size != 0
                            AND num_create = 0 AND num_modify = 0 AND num_delete = 0
                        )
                    )
                    UPDATE changeset SET
                        size = good.size,
                        num_create = good.num_create,
                        num_modify = good.num_modify,
                        num_delete = good.num_delete
                    FROM good
                    WHERE id = changeset_id
                    """,
                    (start_id, end_id),
                )

        async with TaskGroup() as tg:
            for start_id in range(1, max_id + 1, batch_size):
                end_id = min(start_id + batch_size - 1, max_id)
                tg.create_task(process_chunk(start_id, end_id))

    @staticmethod
    async def migrate_database() -> None:
        """
        This function checks the current database version and applies
        any pending migrations in sequential order, identified by files
        named with PEP 440 versions (e.g., 0.sql, 1.sql, 2.sql).
        """
        async with db(True) as conn:
            # Acquire blocking exclusive lock
            await conn.execute(
                'SELECT pg_advisory_xact_lock(4708896507819139515::bigint)'
            )
            await _ensure_db_table(conn)
            current_migration = await _get_current_migration(conn)

            migrations = _find_migrations(current_migration)
            if not migrations:
                logging.debug('No migrations to apply. Database is up to date.')
                return

            logging.info('Applying %d migrations', len(migrations))
            await _apply_migrations(conn, migrations)

            new_version = migrations[-1][0]
            logging.info(
                'Successfully migrated database from %s to %s',
                current_migration,
                new_version,
            )


async def _get_element_typed_id_ranges() -> list[tuple[int, int]]:
    # Define actual data ranges
    current_ids = await ElementQuery.get_current_ids()
    return [
        (
            TYPED_ELEMENT_ID_NODE_MIN,
            typed_element_id('node', current_ids['node']),
        ),
        (
            TYPED_ELEMENT_ID_WAY_MIN,
            typed_element_id('way', current_ids['way']),
        ),
        (
            TYPED_ELEMENT_ID_RELATION_MIN,
            typed_element_id('relation', current_ids['relation']),
        ),
    ]


def _get_element_typed_id_batches(
    ranges: list[tuple[int, int]],
    batch_size: int,
) -> list[tuple[int, int]]:
    # Create balanced batches
    current_chunk_start: int | None = None
    current_chunk_size: int = 0
    chunks: list[tuple[int, int]] = []

    for start, end in ranges:
        pos = start
        while pos <= end:
            if current_chunk_start is None:
                current_chunk_start = pos

            # Determine how many elements to include in this chunk
            remaining_in_range = end - pos + 1
            remaining_in_chunk = batch_size - current_chunk_size
            elements_to_take = min(remaining_in_range, remaining_in_chunk)

            pos += elements_to_take
            current_chunk_size += elements_to_take

            # If chunk is full, add it to the list and reset
            if current_chunk_size >= batch_size:
                chunks.append((current_chunk_start, pos - 1))
                current_chunk_start = None
                current_chunk_size = 0

    # Add the final chunk
    if current_chunk_start is not None:
        chunks.append((current_chunk_start, ranges[-1][1]))

    return chunks


async def _ensure_db_table(conn: AsyncConnection) -> None:
    async with conn.pipeline():
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS migration (
                version text PRIMARY KEY,
                hash bytea NOT NULL,
                applied_at timestamptz NOT NULL DEFAULT statement_timestamp()
            )
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS migration_applied_at_idx ON migration (applied_at)
            """
        )


async def _get_current_migration(conn: AsyncConnection) -> _MigrationInfo | None:
    """Get the current database schema version."""
    async with await conn.execute("""
        SELECT version, hash FROM migration
        ORDER BY applied_at DESC
        LIMIT 1
    """) as r:
        row = await r.fetchone()
        return _MigrationInfo(Version(row[0]), row[1]) if row is not None else None


def _find_migrations(
    current_migration: _MigrationInfo | None,
) -> list[tuple[Version, Path]]:
    migrations = [(Version(p.stem), p) for p in _MIGRATIONS_DIR.glob('*.sql')]
    migrations.sort(key=itemgetter(0))
    assert migrations, 'No migration files found'

    if current_migration is None:
        return migrations

    filtered: list[tuple[Version, Path]] = []
    current_version = current_migration.version
    current_hash = current_migration.hash

    # In dev environment, allow reapplying last migration if its hash changes.
    # This is useful for quick iteration during development.
    allow_reapply = ENV == 'dev'

    for migration in migrations[::-1]:
        if allow_reapply:
            if migration[0] < current_version:
                break
            if migration[0] == current_version:
                if filtered:
                    break
                content = migration[1].read_text()
                new_hash = hash_bytes(content)[:_MIGRATION_HASH_SIZE]
                if new_hash == current_hash:
                    break
                logging.warning(
                    'Current migration %s was modified. Attempting to reapply.',
                    current_version,
                )

        elif migration[0] <= current_version:
            break

        filtered.append(migration)

    return filtered[::-1]


async def _apply_migrations(
    conn: AsyncConnection, migrations: list[tuple[Version, Path]]
) -> None:
    for version, path in migrations:
        try:
            content = path.read_text()
            hash = hash_bytes(content)[:_MIGRATION_HASH_SIZE]
            logging.debug(
                'Applying migration %s from %s (hash=%s)', version, path, hash.hex()
            )

            await conn.cursor(binary=False).execute(content)  # type: ignore
            await conn.execute(
                """
                INSERT INTO migration (version, hash)
                VALUES (%s, %s)
                ON CONFLICT (version) DO UPDATE SET
                    hash = EXCLUDED.hash,
                    applied_at = DEFAULT
                """,
                (str(version), hash),
            )

            logging.debug('Successfully applied migration %s', version)

        except Exception as e:
            raise RuntimeError(f'Migration failed at version {version}: {e}') from e
