import asyncio
import gc
import gzip
from asyncio import sleep
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import click
import cython
import orjson
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic.dataclasses import dataclass
from sentry_sdk import set_context, set_tag, start_transaction
from shapely import Point
from starlette import status

from app.config import OSM_REPLICATION_URL, REPLICATION_DIR
from app.db import duckdb_connect
from app.lib.compressible_geometry import compressible_geometry
from app.lib.retry import retry
from app.lib.sentry import SENTRY_REPLICATION_MONITOR
from app.lib.xmltodict import XMLToDict
from app.models.element import ElementType
from app.utils import HTTP

_Frequency = Literal['minute', 'hour', 'day']


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

    @property
    def next_replica(self) -> 'ReplicaState':
        return ReplicaState(
            sequence_number=self.last_replica.sequence_number + 1,
            created_at=(
                self.last_replica.created_at + _FREQUENCY_TIMEDELTA[self.frequency]
            ),
        )


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
    pa.field('type', pa.string()),
    pa.field('id', pa.uint64()),
    pa.field('version', pa.uint64()),
    pa.field('visible', pa.bool_()),
    pa.field('tags', pa.string()),
    pa.field('point', pa.string()),
    pa.field(
        'members',
        pa.list_(
            pa.struct([
                pa.field('order', pa.uint16()),
                pa.field('type', pa.string()),
                pa.field('id', pa.uint64()),
                pa.field('role', pa.string()),
            ])
        ),
    ),
    pa.field('created_at', pa.timestamp('ms', 'UTC')),
    pa.field('user_id', pa.uint64()),
    pa.field('display_name', pa.string()),
])

_APP_STATE_PATH = REPLICATION_DIR.joinpath('state.json')

# freeze all gc objects before starting for improved performance
gc.collect()
gc.freeze()
gc.disable()


async def main() -> None:
    state = _load_app_state()
    click.echo(
        f'Resuming replication after {state.frequency}/{state.last_replica.sequence_number}'
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
            click.echo(
                f'Finished replication sequence {state.frequency}/{state.last_replica.sequence_number}'
            )
            gc.collect()


@retry(timedelta(minutes=30))
async def _iterate(state: AppState) -> AppState:
    while True:
        next_replica = state.next_replica
        if state.frequency == 'minute' or next_replica.created_at <= datetime.now(UTC):
            break
        old_frequency_str = click.style(f'{state.frequency}', fg='cyan')
        state = await _increase_frequency(state)
        new_frequency_str = click.style(f'{state.frequency}', fg='bright_cyan')
        click.echo(
            f'Increased replication frequency {old_frequency_str} -> {new_frequency_str}'
        )

    url = _get_replication_url(state.frequency, next_replica.sequence_number)

    while True:
        r = await HTTP.get(url + '.state.txt')
        if state.frequency == 'minute' and r.status_code == status.HTTP_404_NOT_FOUND:
            await sleep(60)
            continue
        r.raise_for_status()
        remote_replica = _parse_replica_state(r.text)
        r = await HTTP.get(url + '.osc.gz', timeout=300)
        if state.frequency == 'minute' and r.status_code == status.HTTP_404_NOT_FOUND:
            await sleep(60)
            continue
        r.raise_for_status()
        break

    actions = XMLToDict.parse(gzip.decompress(r.content), size_limit=None)['osmChange']

    if isinstance(actions, dict):
        click.echo('Skipped empty osmChange')
        last_sequence_id = state.last_sequence_id
    else:
        with pq.ParquetWriter(
            remote_replica.path,
            schema=_PARQUET_SCHEMA,
            compression='lz4',
            write_statistics=False,
        ) as writer:
            last_sequence_id = _parse_actions(
                writer,
                actions,
                last_sequence_id=state.last_sequence_id,
            )

    return replace(
        state, last_replica=remote_replica, last_sequence_id=last_sequence_id
    )


@cython.cfunc
def _parse_actions(
    writer: pq.ParquetWriter,
    actions: list[tuple[str, list[tuple[ElementType, dict]]]],
    *,
    last_sequence_id: int,
    # HACK: faster lookup
    orjson_dumps: Callable[[Any], bytes] = orjson.dumps,
) -> int:
    data: list[dict] = []

    def flush():
        if data:
            record_batch = pa.RecordBatch.from_pylist(data, schema=_PARQUET_SCHEMA)
            writer.write_batch(record_batch, row_group_size=len(data))
            data.clear()

    for action, elements_ in actions:
        # skip osmChange attributes
        if action[:1] == '@':
            continue

        elements: list[tuple[ElementType, dict]] = elements_
        element_type: str
        element: dict

        for element_type, element in elements:
            tags = (
                {tag['@k']: tag['@v'] for tag in tags_}
                if (tags_ := element.get('tag')) is not None
                else None
            )
            point: str | None = None
            members: list[dict]

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
                            'order': order,
                            'type': 'node',
                            'id': member['@ref'],
                            'role': '',
                        }
                        for order, member in enumerate(members_)
                    ]
                    if (members_ := element.get('nd')) is not None
                    else []
                )
            elif element_type == 'relation':
                members = (
                    [
                        {
                            'order': order,
                            'type': member['@type'],
                            'id': member['@ref'],
                            'role': member['@role'],
                        }
                        for order, member in enumerate(members_)
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
                'type': element_type,
                'id': element['@id'],
                'version': element['@version'],
                'visible': (tags is not None) or (point is not None) or bool(members),
                'tags': orjson_dumps(tags).decode() if (tags is not None) else '{}',
                'point': point,
                'members': members,
                'created_at': element['@timestamp'],
                'user_id': element.get('@uid'),
                'display_name': element.get('@user'),
            })

        if len(data) >= 1024 * 1024:  # batch size
            flush()

    flush()
    return last_sequence_id


@cython.cfunc
def _clean_leftover_data(state: AppState):
    if state.last_replica.sequence_number % _FREQUENCY_MERGE_EVERY[state.frequency]:
        return
    for path in REPLICATION_DIR.glob('replica_*.parquet'):
        path.unlink()


@cython.cfunc
def _bundle_data_if_needed(state: AppState):
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
    num_paths_str = click.style(f'{len(input_paths)} replica files', fg='green')
    click.echo(f'Bundling {num_paths_str}')

    with duckdb_connect() as conn:
        conn.sql(f"""
        COPY (
            SELECT *
            FROM read_parquet({input_paths!r})
        ) TO {output_path!r}
        (COMPRESSION ZSTD, COMPRESSION_LEVEL 9, ROW_GROUP_SIZE_BYTES '128MB')
        """)


async def _increase_frequency(state: AppState) -> AppState:
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

        if abs(new_replica.created_at - current_created_at) < found_threshold:
            # found
            return replace(state, frequency=new_frequency, last_replica=new_replica)

        if new_replica.created_at > current_created_at:
            # too late
            if direction_forward is None:
                direction_forward = False
            elif direction_forward:
                step >>= 1
            new_sequence_number -= step

        else:
            # too early
            if direction_forward is None:
                direction_forward = True
            elif not direction_forward:
                step >>= 1
            new_sequence_number += step


@cython.cfunc
def _get_replication_url(frequency: _Frequency, sequence_number: int | None) -> str:
    prefix = f'{OSM_REPLICATION_URL}/{frequency}/'
    if sequence_number is None:
        return prefix
    sequence_str = f'{sequence_number:09}'
    return f'{prefix}{sequence_str[:3]}/{sequence_str[3:6]}/{sequence_str[6:]}'


@cython.cfunc
def _parse_replica_state(state: str):
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
    try:
        return AppState(**orjson.loads(_APP_STATE_PATH.read_bytes()))
    except FileNotFoundError:
        return AppState(
            frequency='day',
            last_replica=ReplicaState.default(),
            last_sequence_id=0,
        )


@cython.cfunc
def _save_app_state(state: AppState):
    _APP_STATE_PATH.write_bytes(orjson.dumps(asdict(state)))


if __name__ == '__main__':
    asyncio.run(main())
