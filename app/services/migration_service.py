import logging
from operator import itemgetter
from pathlib import Path
from typing import NamedTuple

from packaging.version import Version
from psycopg import AsyncConnection
from psycopg.sql import SQL, Identifier

from app.config import ENV
from app.db import db
from app.lib.crypto import hash_bytes


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
                query = SQL('SELECT MAX({}) FROM {}').format(Identifier(column), Identifier(table))
                async with await conn.execute(query) as r:
                    row: tuple[int] | None = await r.fetchone()
                    if row is None:
                        continue

                last_value = row[0]
                logging.debug('Setting sequence counter %r to %d', sequence, last_value)
                await conn.execute('SELECT setval(%s, %s)', (sequence, last_value))

    @staticmethod
    async def fix_duplicated_element_version() -> None:
        """Delete duplicated element (typed_id, version) rows."""
        async with (
            db(True, autocommit=True) as conn,
            await conn.execute("""
                WITH dups AS MATERIALIZED (
                    SELECT
                        typed_id, version,
                        ANY_VALUE(sequence_id) AS sequence_id
                    FROM element
                    GROUP BY typed_id, version
                    HAVING COUNT(*) > 1
                )
                DELETE FROM element USING dups
                WHERE element.typed_id = dups.typed_id
                AND element.version = dups.version
                AND element.sequence_id != dups.sequence_id
            """) as r,
        ):
            if rows := await r.fetchall():
                logging.warning(
                    'Deleted %d duplicated element rows (sequence_id, typed_id, version): %s', len(rows), rows
                )

    @staticmethod
    async def fix_next_sequence_id() -> None:
        """Fix the element's next_sequence_id field."""
        async with db(True, autocommit=True) as conn:
            await conn.execute("""
                WITH next_version AS (
                    SELECT
                        e.sequence_id,
                        n.sequence_id AS next_sequence_id
                    FROM element e
                    LEFT JOIN LATERAL (
                        SELECT sequence_id FROM element
                        WHERE typed_id = e.typed_id
                        AND version > e.version
                        ORDER BY version
                        LIMIT 1
                    ) n ON true
                    WHERE next_sequence_id IS NULL
                    AND n.sequence_id IS NOT NULL
                )
                UPDATE element
                SET next_sequence_id = nv.next_sequence_id
                FROM next_version nv
                WHERE element.sequence_id = nv.sequence_id
            """)

    @staticmethod
    async def migrate_database() -> None:
        """
        This function checks the current database version and applies
        any pending migrations in sequential order, identified by files
        named with PEP 440 versions (e.g., 0.sql, 1.sql, 2.sql).
        """
        async with db(True) as conn:
            # Acquire blocking exclusive lock
            await conn.execute('SELECT pg_advisory_xact_lock(4708896507819139515::bigint)')
            await _ensure_db_table(conn)
            current_migration = await _get_current_migration(conn)

            migrations = _find_migrations(current_migration)
            if not migrations:
                logging.debug('No migrations to apply. Database is up to date.')
                return

            logging.info('Applying %d migrations', len(migrations))
            await _apply_migrations(conn, migrations)

            new_version = migrations[-1][0]
            logging.info('Successfully migrated database from %s to %s', current_migration, new_version)


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


def _find_migrations(current_migration: _MigrationInfo | None) -> list[tuple[Version, Path]]:
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


async def _apply_migrations(conn: AsyncConnection, migrations: list[tuple[Version, Path]]) -> None:
    for version, path in migrations:
        try:
            content = path.read_text()
            hash = hash_bytes(content)[:_MIGRATION_HASH_SIZE]
            logging.debug('Applying migration %s from %s (hash=%s)', version, path, hash.hex())

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
