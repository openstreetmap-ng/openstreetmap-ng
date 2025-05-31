import asyncio
import gc
import gzip
import logging
from asyncio import sleep
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Literal

import cython
import orjson
import pyarrow as pa
import pyarrow.parquet as pq
from sentry_sdk import set_context, set_tag, start_transaction
from starlette import status

from app.config import OSM_REPLICATION_URL, REPLICATION_DIR
from app.db import duckdb_connect
from app.lib.compressible_geometry import point_to_compressible_wkb
from app.lib.retry import retry
from app.lib.sentry import SENTRY_REPLICATION_MONITOR
from app.lib.xmltodict import XMLToDict
from app.models.element import ElementType, TypedElementId
from app.utils import HTTP
from speedup.element_type import typed_element_id

_Frequency = Literal['minute', 'hour', 'day']

_APP_STATE_PATH = REPLICATION_DIR.joinpath('state.json')

_FREQUENCY_TIMEDELTA: dict[_Frequency, timedelta] = {
    'minute': timedelta(minutes=1),
    'hour': timedelta(hours=1),
    'day': timedelta(days=1),
}

_FREQUENCY_MERGE_EVERY: dict[_Frequency, int] = {
    'minute': 7 * 24 * 60,
    'hour': 7 * 24,
    'day': 7,
}

_PARQUET_TMP_SCHEMA = pa.schema([
    pa.field('parse_order', pa.uint64()),
    pa.field('changeset_id', pa.uint64()),
    pa.field('typed_id', pa.uint64()),
    pa.field('version', pa.uint64()),
    pa.field('visible', pa.bool_()),
    pa.field('tags', pa.map_(pa.string(), pa.string())),
    pa.field('point', pa.binary(21)),
    pa.field(
        'members',
        pa.list_(
            pa.struct([
                pa.field('typed_id', pa.uint64()),
                pa.field('role', pa.string()),
            ])
        ),
    ),
    pa.field('created_at', pa.timestamp('ms', 'UTC')),
    pa.field('user_id', pa.uint64()),
    pa.field('display_name', pa.string()),
])


@dataclass(frozen=True, kw_only=True, slots=True)
class ReplicaState:
    sequence_number: int
    created_at: datetime

    @property
    def path(self) -> Path:
        return REPLICATION_DIR.joinpath(
            f'replica_{int(self.created_at.timestamp()):020}.parquet'
        )

    @property
    def bundle_path(self) -> Path:
        return REPLICATION_DIR.joinpath(
            f'bundle_{int(self.created_at.timestamp()):020}.parquet'
        )

    @staticmethod
    def default() -> 'ReplicaState':
        return ReplicaState(
            sequence_number=0,
            created_at=datetime.fromtimestamp(0, UTC),
        )


@dataclass(frozen=True, kw_only=True, slots=True)
class AppState:
    frequency: _Frequency
    last_replica: ReplicaState
    last_sequence_id: int

    @property
    def next_replica(self) -> 'ReplicaState':
        return ReplicaState(
            sequence_number=self.last_replica.sequence_number + 1,
            created_at=(
                self.last_replica.created_at + _FREQUENCY_TIMEDELTA[self.frequency]
            ),
        )


@cython.cfunc
def _clean_leftover_data(state: AppState):
    """Remove leftover replica files."""
    if state.last_replica.sequence_number % _FREQUENCY_MERGE_EVERY[state.frequency]:
        return

    for path in REPLICATION_DIR.glob('replica_*.parquet'):
        path.unlink()


@cython.cfunc
def _bundle_data_if_needed(state: AppState):
    """Bundle individual replica files into a consolidated parquet file."""
    if state.last_replica.sequence_number % _FREQUENCY_MERGE_EVERY[state.frequency]:
        return

    input_paths = [
        p.as_posix()
        for p in sorted(
            REPLICATION_DIR.glob('replica_*.parquet'),
            key=lambda p: int(p.stem.split('_', 1)[1]),
        )
    ]
    output_path = state.last_replica.bundle_path.as_posix()
    logging.info('Bundling %d replica files', len(input_paths))

    with duckdb_connect() as conn:
        conn.sql(f"""
        COPY (
            SELECT *
            FROM read_parquet({input_paths!r})
            ORDER BY typed_id, version
        ) TO {output_path!r}
        (COMPRESSION ZSTD, COMPRESSION_LEVEL 9)
        """)


@cython.cfunc
def _get_replication_url(frequency: _Frequency, sequence_number: int | None) -> str:
    """Generate the base URL for an OSM replication file."""
    prefix = f'{OSM_REPLICATION_URL}/{frequency}/'
    if sequence_number is None:
        return prefix

    seq_str = f'{sequence_number:09d}'

    first = seq_str[:-6]
    middle = seq_str[-6:-3]
    last = seq_str[-3:]

    return f'{prefix}{first}/{middle}/{last}'


@cython.cfunc
def _parse_replica_state(state: str):
    """Parse the OSM replication state file."""
    data: dict[str, str] = {}
    line: str
    for line in state.splitlines():
        if not line or line[0] == '#':
            continue
        key, _, val = line.partition('=')
        data[key] = val.replace('\\', '')

    return ReplicaState(
        sequence_number=int(data['sequenceNumber']),
        created_at=datetime.fromisoformat(data['timestamp']),
    )


@cython.cfunc
def _load_app_state():
    """Load the application state from disk or create default state."""
    try:
        data = orjson.loads(_APP_STATE_PATH.read_bytes())
    except FileNotFoundError:
        return AppState(
            frequency='day',
            last_replica=ReplicaState.default(),
            last_sequence_id=0,
        )

    # Fixup types
    data['last_replica']['created_at'] = datetime.fromisoformat(
        data['last_replica']['created_at']
    )
    data['last_replica'] = ReplicaState(**data['last_replica'])
    return AppState(**data)


@cython.cfunc
def _save_app_state(state: AppState):
    """Save the current application state to disk."""
    tmp = _APP_STATE_PATH.with_name(f'.{_APP_STATE_PATH.name}.tmp')
    tmp.write_bytes(orjson.dumps(asdict(state)))
    tmp.replace(_APP_STATE_PATH)


@cython.cfunc
def _parse_actions(
    writer: pq.ParquetWriter,
    actions: list[tuple[str, list[tuple[ElementType, dict]]]],
) -> int:
    """Parse OSM change actions and write them to parquet."""
    parse_order: cython.Py_ssize_t = -1
    data: list[dict] = []

    def flush():
        """Write accumulated data to parquet and clear the buffer."""
        if data:
            record_batch = pa.RecordBatch.from_pylist(data, schema=_PARQUET_TMP_SCHEMA)
            writer.write_batch(record_batch, row_group_size=len(data))
            data.clear()

    for action, action_value in actions:
        # Skip osmChange attributes
        if action[:1] == '@':
            continue

        elements: list[tuple[ElementType, dict]] = action_value
        type: str
        element: dict

        for parse_order, (type, element) in enumerate(elements, parse_order + 1):  # noqa: B020
            typed_id = typed_element_id(type, element['@id'])
            version = element['@version']

            tags = (
                {tag['@k']: tag['@v'] for tag in tags_}
                if (tags_ := element.get('tag')) is not None
                else None
            )
            point: bytes | None = None
            members: list[tuple[TypedElementId, str | None]] | None = None

            if type == 'node':
                if (lon := element.get('@lon')) is not None:
                    point = point_to_compressible_wkb(lon, element['@lat'])
            elif type == 'way':
                if (members_ := element.get('nd')) is not None:
                    members = [(member['@ref'], None) for member in members_]
            elif type == 'relation':
                if (members_ := element.get('member')) is not None:
                    members = [
                        (
                            typed_element_id(member['@type'], member['@ref']),
                            member['@role'],
                        )
                        for member in members_
                    ]
            else:
                raise NotImplementedError(f'Unsupported element type {type!r}')

            data.append({
                'parse_order': parse_order,
                'changeset_id': element['@changeset'],
                'typed_id': typed_id,
                'version': version,
                'visible': (
                    (tags is not None) or (point is not None) or (members is not None)
                ),
                'tags': tags,
                'point': point,
                'members': members,
                'created_at': element['@timestamp'],
                'user_id': element.get('@uid'),
                'display_name': element.get('@user'),
            })

            # Flush batch when we have accumulated enough data
            if len(data) >= 122880:
                flush()

    # Flush any remaining data
    flush()

    return parse_order + 1


@retry(timedelta(minutes=30))
async def _iterate(state: AppState) -> AppState:
    """Process the next replication sequence."""
    while True:
        next_replica = state.next_replica
        if state.frequency == 'minute' or next_replica.created_at <= datetime.now(UTC):
            break

        old_frequency = state.frequency
        state = await _increase_frequency(state)
        logging.info(
            'Increased replication frequency %r -> %r',
            old_frequency,
            state.frequency,
        )

    url = _get_replication_url(state.frequency, next_replica.sequence_number)

    # Attempt to fetch the replication data
    while True:
        r = await HTTP.get(url + '.state.txt')
        if state.frequency == 'minute' and r.status_code == status.HTTP_404_NOT_FOUND:
            logging.debug('Minute state not yet available, waiting...')
            await sleep(60)
            continue
        r.raise_for_status()
        remote_replica = _parse_replica_state(r.text)

        r = await HTTP.get(url + '.osc.gz', timeout=300)
        if state.frequency == 'minute' and r.status_code == status.HTTP_404_NOT_FOUND:
            logging.debug('Minute data not yet available, waiting...')
            await sleep(60)
            continue
        r.raise_for_status()
        break

    actions = XMLToDict.parse(gzip.decompress(r.content), size_limit=None)['osmChange']
    del r  # free memory

    if isinstance(actions, dict):
        logging.info('Skipped empty osmChange')
        num_rows = 0
    else:
        ts = monotonic()
        tmp_path = remote_replica.path.with_name(f'.{remote_replica.path.name}.tmp')

        # Parse actions and write to temporary file
        with pq.ParquetWriter(
            tmp_path,
            schema=_PARQUET_TMP_SCHEMA,
            compression='lz4',
            write_statistics=False,
            sorting_columns=pq.SortingColumn.from_ordering(
                _PARQUET_TMP_SCHEMA, [('parse_order', 'ascending')]
            ),
        ) as writer:
            num_rows = _parse_actions(writer, actions)
            assert num_rows > 0
            del actions  # free memory

        tt = monotonic() - ts
        logging.info('Processed %d elements in %.1fs', num_rows, tt)
        ts = monotonic()

        # Use DuckDB to sort and assign sequence IDs
        with duckdb_connect() as conn:
            conn.sql(f"""
            COPY (
                SELECT
                    {state.last_sequence_id} + ROW_NUMBER() OVER (
                        ORDER BY created_at, parse_order
                    )::UBIGINT AS sequence_id,
                    * EXCLUDE (parse_order)
                FROM read_parquet({tmp_path.as_posix()!r})
                ORDER BY typed_id, version
            ) TO {remote_replica.path.as_posix()!r}
            (COMPRESSION lz4_raw)
            """)

        tmp_path.unlink()
        tt = monotonic() - ts
        logging.info('Assigned sequence IDs in %.1fs', tt)

    return replace(
        state,
        last_replica=remote_replica,
        last_sequence_id=state.last_sequence_id + num_rows,
    )


async def _increase_frequency(state: AppState) -> AppState:
    """Find an appropriate higher frequency replication state."""
    current_timedelta = _FREQUENCY_TIMEDELTA[state.frequency]
    current_created_at = state.last_replica.created_at
    new_frequency: _Frequency = 'minute' if state.frequency == 'hour' else 'hour'
    new_timedelta = _FREQUENCY_TIMEDELTA[new_frequency]
    found_threshold = new_timedelta / 2
    frequency_downscale = (
        current_timedelta.total_seconds() / new_timedelta.total_seconds()
    )

    step: cython.int = 2 << 4
    new_sequence_number: cython.longlong = int(
        state.last_replica.sequence_number * frequency_downscale
    )
    direction_forward: bool | None = None

    # Binary search for closest replica at new frequency
    while True:
        if not step:
            raise ValueError(
                f"Couldn't find {new_frequency!r} replica at {current_created_at!r}"
            )

        url = _get_replication_url(new_frequency, new_sequence_number)
        r = await HTTP.get(url + '.state.txt')

        if r.status_code == status.HTTP_404_NOT_FOUND:
            if direction_forward is None:
                direction_forward = False
            elif direction_forward:
                step >>= 1
            new_sequence_number -= step
            continue

        r.raise_for_status()
        new_replica = _parse_replica_state(r.text)

        # Check if we're close enough to the target time
        if abs(new_replica.created_at - current_created_at) < found_threshold:
            # Found matching replica
            return replace(
                state,
                frequency=new_frequency,
                last_replica=new_replica,
            )

        if new_replica.created_at > current_created_at:
            # Too late, move backward
            if direction_forward is None:
                direction_forward = False
            elif direction_forward:
                step >>= 1
            new_sequence_number -= step
        else:
            # Too early, move forward
            if direction_forward is None:
                direction_forward = True
            elif not direction_forward:
                step >>= 1
            new_sequence_number += step


async def main() -> None:
    # Freeze all gc objects before starting for improved performance
    gc.collect()
    gc.freeze()
    gc.disable()

    state = _load_app_state()
    logging.info(
        'Resuming replication after %s/%d',
        state.frequency,
        state.last_replica.sequence_number,
    )

    while True:
        with (
            SENTRY_REPLICATION_MONITOR,
            start_transaction(op='task', name='replication'),
        ):
            set_tag('state.frequency', state.frequency)
            set_context(
                'state',
                {
                    'last_replica_sequence_number': state.last_replica.sequence_number,
                    'last_replica_created_at': state.last_replica.created_at,
                    'last_sequence_id': state.last_sequence_id,
                },
            )
            _clean_leftover_data(state)
            state = await _iterate(state)
            _bundle_data_if_needed(state)
            _save_app_state(state)
            logging.info(
                'Finished replication sequence %s/%d',
                state.frequency,
                state.last_replica.sequence_number,
            )
            gc.collect()


if __name__ == '__main__':
    asyncio.run(main())
