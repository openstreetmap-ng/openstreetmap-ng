from psycopg.sql import SQL, Identifier

from app.db import db2


class MigrationService:
    @staticmethod
    async def fix_sequence_counters() -> None:
        """Fix the sequence counters."""
        async with db2(True, autocommit=True) as conn:
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

            for table_name, column_name, sequence_name in sequences:
                await conn.execute(
                    SQL(
                        'SELECT setval({sequence_name}, COALESCE((SELECT MAX({column_name}) FROM {table_name}), 1))'
                    ).format(
                        sequence_name=Identifier(sequence_name),
                        column_name=Identifier(column_name),
                        table_name=Identifier(table_name),
                    )
                )

    @staticmethod
    async def fix_next_sequence_id() -> None:
        """Fix the element's next_sequence_id field."""
        async with db2(True, autocommit=True) as conn:
            await conn.execute("""
                WITH next_version AS (
                    SELECT
                        e1.sequence_id,
                        e2.sequence_id AS next_sequence_id
                    FROM element e1
                    LEFT JOIN LATERAL (
                        SELECT sequence_id
                        FROM element e2
                        WHERE e2.typed_id = e1.typed_id
                        AND e2.version > e1.version
                        ORDER BY e2.version
                        LIMIT 1
                    ) e2 ON true
                    WHERE e1.next_sequence_id IS NULL
                )
                UPDATE element
                SET next_sequence_id = nv.next_sequence_id
                FROM next_version nv
                WHERE sequence_id = nv.sequence_id;
            """)
