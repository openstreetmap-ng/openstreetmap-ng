import asyncio
import gc
import gzip
import logging
from asyncio import sleep
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import cython
import orjson
import pyarrow as pa
import pyarrow.parquet as pq
from sentry_sdk import set_context, set_tag, start_transaction
from shapely import Point
from starlette import status

from app.config import OSM_REPLICATION_URL, REPLICATION_DIR
from app.db import duckdb_connect
from app.lib.compressible_geometry import compressible_geometry
from app.lib.retry import retry
from app.lib.sentry import SENTRY_REPLICATION_MONITOR
from app.lib.xmltodict import XMLToDict
from app.models.element import ElementType, TypedElementId, typed_element_id
from app.utils import HTTP

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

_PARQUET_SCHEMA = pa.schema([
    pa.field('sequence_id', pa.uint64()),
    pa.field('changeset_id', pa.uint64()),
    pa.field('typed_id', pa.uint64()),
    pa.field('version', pa.uint64()),
    pa.field('visible', pa.bool_()),
    pa.field('tags', pa.string()),
    pa.field('point', pa.string()),
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
            sequence_number=0, created_at=datetime.fromtimestamp(0, UTC)
        )


@dataclass(frozen=True, kw_only=True, slots=True)
class AppState:
    frequency: _Frequency
    last_replica: ReplicaState
    last_sequence_id: int
    last_versioned_refs: list[tuple[TypedElementId, int]]

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
        ) TO {output_path!r}
        (COMPRESSION ZSTD, COMPRESSION_LEVEL 9, ROW_GROUP_SIZE_BYTES '128MB')
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
            last_versioned_refs=[],
        )

    return AppState(
        **data,
        # Restore nested lists back to tuples
        last_versioned_refs=[
            (typed_id, version) for typed_id, version in data['last_versioned_refs']
        ],
    )


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
    *,
    last_sequence_id: int,
    last_versioned_refs: list[tuple[TypedElementId, int]],
    # HACK: faster lookup
    orjson_dumps: Callable[[Any], bytes] = orjson.dumps,
) -> tuple[int, list[tuple[TypedElementId, int]]]:
    """Parse OSM change actions and write them to parquet."""
    last_versioned_refs_set = set(last_versioned_refs)
    new_versioned_refs: list[tuple[TypedElementId, int]] = []
    skipped_duplicates: cython.ulonglong = 0
    data: list[dict] = []

    def flush():
        """Write accumulated data to parquet and clear buffer."""
        if data:
            record_batch = pa.RecordBatch.from_pylist(data, schema=_PARQUET_SCHEMA)
            writer.write_batch(record_batch, row_group_size=len(data))
            data.clear()

    for action, elements_ in actions:
        # Skip osmChange attributes
        if action[:1] == '@':
            continue

        elements: list[tuple[ElementType, dict]] = elements_
        element_type: str
        element: dict

        for element_type, element in elements:
            typed_id = typed_element_id(element_type, element['@id'])
            version = element['@version']

            # Skip if it's a duplicate
            ref = (typed_id, version)
            if ref in last_versioned_refs_set:
                skipped_duplicates += 1
                continue
            new_versioned_refs.append(ref)

            tags = (
                {tag['@k']: tag['@v'] for tag in tags_}
                if (tags_ := element.get('tag')) is not None
                else None
            )
            point: str | None = None
            members: list[dict]

            # Process by element type
            if element_type == 'node':
                members = []
                if (
                    (lon := element.get('@lon')) is not None  #
                    and (lat := element.get('@lat')) is not None
                ):
                    point = compressible_geometry(Point(lon, lat)).wkb_hex
            elif element_type == 'way':
                members = (
                    [
                        {
                            'typed_id': member['@ref'],
                            'role': '',
                        }
                        for member in members_
                    ]
                    if (members_ := element.get('nd')) is not None
                    else []
                )
            elif element_type == 'relation':
                members = (
                    [
                        {
                            'typed_id': typed_element_id(
                                member['@type'], member['@ref']
                            ),
                            'role': member['@role'],
                        }
                        for member in members_
                    ]
                    if (members_ := element.get('member')) is not None
                    else []
                )
            else:
                raise NotImplementedError(f'Unsupported element type {element_type!r}')

            last_sequence_id += 1
            data.append({
                'sequence_id': last_sequence_id,
                'changeset_id': element['@changeset'],
                'typed_id': typed_id,
                'version': version,
                'visible': (tags is not None) or (point is not None) or bool(members),
                'tags': orjson_dumps(tags).decode() if (tags is not None) else '{}',
                'point': point,
                'members': members,
                'created_at': element['@timestamp'],
                'user_id': element.get('@uid'),
                'display_name': element.get('@user'),
            })

        # Finish batch when we have accumulated enough data
        if len(data) >= 1024 * 1024:
            flush()

    # Write any remaining data
    flush()

    if skipped_duplicates:
        logging.warning('Skipped %d duplicate elements', skipped_duplicates)

    return last_sequence_id, new_versioned_refs


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

    if isinstance(actions, dict):
        logging.info('Skipped empty osmChange')
        last_sequence_id = state.last_sequence_id
        last_versioned_refs = []
    else:
        with pq.ParquetWriter(
            remote_replica.path,
            schema=_PARQUET_SCHEMA,
            compression='lz4',
            write_statistics=False,
        ) as writer:
            last_sequence_id, last_versioned_refs = _parse_actions(
                writer,
                actions,
                last_sequence_id=state.last_sequence_id,
                last_versioned_refs=state.last_versioned_refs,
            )

    return replace(
        state,
        last_replica=remote_replica,
        last_sequence_id=last_sequence_id,
        last_versioned_refs=last_versioned_refs,
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
