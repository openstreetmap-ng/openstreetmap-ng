import asyncio
import logging
from argparse import ArgumentParser
from asyncio.subprocess import PIPE, create_subprocess_exec
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from functools import cache
from pathlib import Path
from shutil import copyfile
from typing import Literal, TypedDict, get_args

import cython
from psycopg import AsyncConnection
from psycopg.rows import dict_row

from app.config import (
    COMPRESS_REPLICATION_GZIP_LEVEL,
    COMPRESS_REPLICATION_GZIP_THREADS,
    PLANET_DIR,
)
from app.db import db
from app.format import Format06
from app.lib.date_utils import utcnow
from app.lib.xmltodict import XMLToDict
from app.models.db.element import Element
from app.utils import calc_num_workers


class _State(TypedDict):
    sequence_number: int
    timestamp: datetime


_TimeSpan = Literal['minute', 'hour', 'day']

_TIMESPAN_DELTA: dict[_TimeSpan, timedelta] = {
    'minute': timedelta(minutes=1),
    'hour': timedelta(hours=1),
    'day': timedelta(days=1),
}

_CHUNK_SIZE = 1_000_000

_NUM_WORKERS_PIGZ = calc_num_workers(COMPRESS_REPLICATION_GZIP_THREADS)
logging.debug('Configured pigz compression: %d workers', _NUM_WORKERS_PIGZ)


def _make_tmp_path(path: Path) -> Path:
    """Create a temporary file path by prefixing filename with dot."""
    return path.with_name(f'.{path.name}.tmp')


def _next_timestamp(delta: timedelta) -> datetime:
    """Calculate timespan-aligned timestamp for next replication."""
    now = utcnow()
    result = now - timedelta(seconds=now.timestamp() % delta.total_seconds())
    return result.replace(microsecond=0)


@cache
def _replication_dir(timespan: _TimeSpan) -> Path:
    """Get the replication directory for the given timespan."""
    return PLANET_DIR.joinpath('replication', timespan)


def _get_sequence_path(
    timespan: _TimeSpan, sequence_number: int, suffix: str = ''
) -> Path:
    """Calculate path with standard DDD/DDD/DDD nesting structure."""
    seq_str = f'{sequence_number:09d}'

    first = seq_str[:-6]
    middle = seq_str[-6:-3]
    last = seq_str[-3:]

    return _replication_dir(timespan).joinpath(first, middle, last + suffix)


def _write_state(path: Path, state: _State) -> None:
    """Write replication state with standard formatting."""
    date_parts = datetime.now(UTC).ctime().split()
    date_parts.insert(-1, 'UTC')
    date_str = ' '.join(date_parts)
    timestamp_str = (
        state['timestamp'].isoformat().replace('+00:00', 'Z', 1).replace(':', '\\:')
    )
    path.write_text(
        '\n'.join((
            f'#{date_str}',
            f'sequenceNumber={state["sequence_number"]}',
            f'timestamp={timestamp_str}',
        ))
    )
    logging.debug('State written: #%d', state['sequence_number'])


def _read_state(path: Path) -> _State:
    """Parse replication state file with validation."""
    sequence_number: int | None = None
    timestamp: datetime | None = None

    content: str = path.read_text()

    line: str
    for line in content.split('\n'):
        if not line or line[:1] == '#':
            continue

        key, value = line.split('=', 1)
        if key == 'sequenceNumber':
            sequence_number = int(value)
        elif key == 'timestamp':
            timestamp = datetime.fromisoformat(value.replace('\\:', ':'))

    # Validate required fields
    assert sequence_number is not None, f'Missing sequence number in {path!r}'
    assert sequence_number > 0, (
        f'Invalid sequence number in {path!r}: {sequence_number} (must be positive)'
    )

    assert timestamp is not None, f'Missing timestamp in {path!r}'
    assert timestamp.tzinfo == UTC, (
        f'Invalid timestamp in {path!r}: {timestamp} (must be UTC)'
    )
    assert timestamp < datetime.now(UTC), (
        f'Invalid timestamp in {path!r}: {timestamp} (must be in the past)'
    )

    logging.debug('State read: #%d', sequence_number)
    return {
        'sequence_number': sequence_number,
        'timestamp': timestamp,
    }


async def _read_last_state(timespan: _TimeSpan, no_backfill: bool) -> _State:
    """Load latest state or start fresh."""
    state_path = _replication_dir(timespan).joinpath('state.txt')
    if state_path.is_file():
        return _read_state(state_path)

    if no_backfill:
        async with (
            db() as conn,
            await conn.execute("""
                SELECT COALESCE(
                    (
                        SELECT created_at FROM element
                        ORDER BY sequence_id DESC
                        LIMIT 1
                    ),
                    statement_timestamp()
                )
            """) as r,
        ):
            init_timestamp: datetime = (await r.fetchone())[0]  # type: ignore
    else:
        init_timestamp = datetime.fromtimestamp(0, UTC)

    logging.warning('State file not found, starting fresh')
    return {
        'sequence_number': 0,
        'timestamp': init_timestamp,
    }


async def _wait_db_sync(next_timestamp: datetime) -> None:
    """Ensure database timestamp exceeds replication timestamp."""
    while True:
        async with (
            db() as conn,
            await conn.execute("""SELECT statement_timestamp()""") as r,
        ):
            db_timestamp: datetime = (await r.fetchone())[0]  # type: ignore

        delay = (next_timestamp - db_timestamp).total_seconds()
        if delay >= 0:
            logging.warning('Database lagging: %.1fs, waiting...', delay)
            await asyncio.sleep(delay)
            continue

        # Enforce commit visibility
        async with db(True) as conn:
            await conn.execute('LOCK TABLE element IN EXCLUSIVE MODE')

        logging.debug('Database in sync, proceeding')
        break


async def _find_sequence_range_for_timespan(
    from_timestamp: datetime, to_timestamp: datetime
) -> tuple[int, int] | None:
    """
    Efficiently find sequence_id range that corresponds to the given time range.
    Returns (min_sequence_id, max_sequence_id) or None if no data in range.
    """
    async with db() as conn:
        # Get max sequence_id to establish our search space
        async with await conn.execute('SELECT MAX(sequence_id) FROM element') as r:
            max_seq: int | None = (await r.fetchone())[0]  # type: ignore
            if max_seq is None:
                logging.warning('No elements in the table')
                return None

        # Find the first sequence_id where created_at >= from_timestamp
        start_seq = await _binary_search_boundary(conn, 1, max_seq, from_timestamp)
        if start_seq is None:
            logging.debug(
                'No elements with created_at >= %s',
                from_timestamp.isoformat(),
            )
            return None

        # Find the first sequence_id where created_at >= to_timestamp
        end_seq = await _binary_search_boundary(conn, start_seq, max_seq, to_timestamp)
        # If we found the boundary, adjust it to exclude records >= to_timestamp
        end_seq = end_seq - 1 if end_seq is not None else max_seq

        logging.debug('Sequence range for timespan: [%d, %d]', start_seq, end_seq)
        return start_seq, end_seq


async def _binary_search_boundary(
    conn: AsyncConnection,
    low: cython.ulonglong,
    high: cython.ulonglong,
    timestamp: datetime,
) -> int | None:
    """Binary search helper that finds boundary sequence_id based on timestamp comparison."""
    assert low > 0
    result: cython.ulonglong = 0

    while low <= high:
        mid: cython.ulonglong = (low + high) // 2

        # Find an existing sequence_id at or after mid
        async with await conn.execute(
            """
            SELECT sequence_id, created_at FROM element
            WHERE sequence_id >= %s
            ORDER BY sequence_id
            LIMIT 1
            """,
            (mid,),
        ) as r:
            row = await r.fetchone()

        if row is None:
            high = mid - 1  # No sequence_ids from mid to high, search lower half
            continue

        existing_seq: cython.ulonglong
        mid_time: datetime
        existing_seq, mid_time = row

        if mid_time >= timestamp:
            result = existing_seq
            high = existing_seq - 1  # Keep searching for earlier matches
        else:
            low = existing_seq + 1  # Need a later record

    return result or None


async def _fetch_changes(
    from_timestamp: datetime, to_timestamp: datetime
) -> AsyncGenerator[list[Element]]:
    """Stream database changes between timestamps in chunks using sequence_id."""
    seq_range = await _find_sequence_range_for_timespan(from_timestamp, to_timestamp)
    if seq_range is None:
        return

    num_elements: cython.Py_ssize_t = 0
    num_chunks: cython.ulonglong = 0

    async with (
        db() as conn,
        await conn.cursor(row_factory=dict_row).execute(
            """
            SELECT * FROM element
            WHERE sequence_id BETWEEN %s AND %s
            ORDER BY sequence_id
            """,
            seq_range,
        ) as r,
    ):
        while True:
            rows = await r.fetchmany(_CHUNK_SIZE)
            if not rows:
                break

            num_rows: cython.Py_ssize_t = len(rows)
            num_elements += num_rows
            num_chunks += 1
            logging.debug('Fetched chunk %d: %d elements', num_chunks, num_rows)
            yield rows  # type: ignore

    logging.info('Fetched %d elements in %d chunk(s)', num_elements, num_chunks)


async def _generate_diff(
    timespan: _TimeSpan, state: _State, next_timestamp: datetime
) -> None:
    """Create osmChange diff between current and next timestamp."""
    assert state['timestamp'] < next_timestamp
    await _wait_db_sync(next_timestamp)

    next_sequence_number = state['sequence_number'] + 1
    logging.info(
        'Generating diff #%d: %s -> %s',
        next_sequence_number,
        state['timestamp'].isoformat(),
        next_timestamp.isoformat(),
    )

    # Set up paths
    diff_path = _get_sequence_path(timespan, next_sequence_number, '.osc.gz')
    state_path = _get_sequence_path(timespan, next_sequence_number, '.state.txt')
    base_state_path = _replication_dir(timespan).joinpath('state.txt')

    diff_path.parent.mkdir(parents=True, exist_ok=True)
    logging.debug('Output directory structure created')

    diff_tmp_path = _make_tmp_path(diff_path)
    state_tmp_path = _make_tmp_path(state_path)
    base_state_tmp_path = _make_tmp_path(base_state_path)
    has_data: cython.bint = False

    with diff_tmp_path.open('wb') as f_out:
        pigz_proc = await create_subprocess_exec(
            'pigz',
            f'-{COMPRESS_REPLICATION_GZIP_LEVEL}',
            '--processes',
            str(_NUM_WORKERS_PIGZ),
            stdin=PIPE,
            stdout=f_out,
        )
        pigz_stdin: asyncio.StreamWriter = pigz_proc.stdin  # type: ignore
        logging.debug('Started pigz compression process')

        async for chunk in _fetch_changes(state['timestamp'], next_timestamp):
            content: bytes = XMLToDict.unparse(
                {'osmChange': Format06.encode_osmchange(chunk)}, raw=True
            )

            # Extract osmChange content (avoid duplication)
            slice_start: cython.Py_ssize_t = (
                0
                if not has_data
                else content.index(b'>', content.index(b'<osmChange')) + 1
            )
            slice_end: cython.Py_ssize_t = content.rindex(b'</osmChange>')
            content = content[slice_start:slice_end]

            pigz_stdin.write(content)
            del content
            await pigz_stdin.drain()
            has_data = True

        if has_data:
            pigz_stdin.write(b'</osmChange>')
            await pigz_stdin.drain()

        pigz_stdin.close()
        exit_code = await pigz_proc.wait()
        if exit_code:
            raise RuntimeError(f'Subprocess failed with exit code {exit_code}')

    if not has_data:
        logging.info('No changes found, skipping diff')
        diff_tmp_path.unlink()
        state['timestamp'] = next_timestamp
        return

    # Update state
    state['timestamp'] = next_timestamp
    state['sequence_number'] = next_sequence_number

    # Persist state files
    _write_state(state_tmp_path, state)
    copyfile(state_tmp_path, base_state_tmp_path)

    # Move temporary files to their final destination
    diff_tmp_path.replace(diff_path)
    state_tmp_path.replace(state_path)
    base_state_tmp_path.replace(base_state_path)

    logging.info('Diff #%d created successfully', next_sequence_number)


async def _run(timespan: _TimeSpan, no_backfill: bool) -> None:
    """Run replication service main loop."""
    delta = _TIMESPAN_DELTA[timespan]
    state = await _read_last_state(timespan, no_backfill)
    logging.info(
        'Starting %r replication from sequence #%d, timestamp %s',
        timespan,
        state['sequence_number'],
        state['timestamp'].isoformat(),
    )

    while True:
        next_timestamp = _next_timestamp(delta)
        if next_timestamp <= state['timestamp']:
            now = utcnow()
            delay = (next_timestamp + delta) - now
            logging.debug('Sleeping until %s', (now + delay).isoformat())
            await asyncio.sleep(delay.total_seconds())
            continue

        await _generate_diff(timespan, state, next_timestamp)


def main() -> None:
    parser = ArgumentParser(description='Generate replication diffs continuously')
    parser.add_argument(
        'timespan',
        choices=get_args(_TimeSpan),
        help='Timespan for replication diffs',
    )
    parser.add_argument(
        '--no-backfill',
        action='store_true',
        help='Skip backfilling diffs with historical data',
    )
    args = parser.parse_args()
    asyncio.run(_run(args.timespan, args.no_backfill))


if __name__ == '__main__':
    main()
