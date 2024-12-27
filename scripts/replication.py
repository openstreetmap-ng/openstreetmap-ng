import asyncio
import gzip
from asyncio import sleep
from collections.abc import Callable
from copy import replace
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import click
import cython
import numpy as np
import orjson
import polars as pl
from polars._typing import SchemaDict
from pydantic.dataclasses import dataclass
from sentry_sdk import set_context, set_tag, start_transaction
from shapely import Point
from starlette import status

from app.config import OSM_REPLICATION_URL, REPLICATION_DIR, SENTRY_REPLICATION_MONITOR
from app.lib.compressible_geometry import compressible_geometry
from app.lib.retry import retry
from app.lib.xmltodict import XMLToDict
from app.models.element import ElementType
from app.services.optimistic_diff.prepare import OSMChangeAction
from app.utils import HTTP

_Frequency = Literal['minute', 'hour', 'day']

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

_PARQUET_SCHEMA: SchemaDict = {
    'sequence_id': pl.UInt64,
    'changeset_id': pl.UInt64,
    'type': pl.Enum(('node', 'way', 'relation')),
    'id': pl.UInt64,
    'version': pl.UInt64,
    'visible': pl.Boolean,
    'tags': pl.String,
    'point': pl.String,
    'members': pl.List(
        pl.Struct(
            {
                'order': pl.UInt16,
                'type': pl.Enum(('node', 'way', 'relation')),
                'id': pl.UInt64,
                'role': pl.String,
            }
        )
    ),
    'created_at': pl.Datetime,
    'user_id': pl.UInt64,
    'display_name': pl.String,
}

_APP_STATE_PATH = REPLICATION_DIR / 'state.json'


@dataclass(frozen=True, kw_only=True, slots=True)
class ReplicaState:
    sequence_number: int
    created_at: datetime

    @property
    def path(self) -> Path:
        return REPLICATION_DIR.joinpath(f'replica_{int(self.created_at.timestamp()):020}.parquet')

    @property
    def bundle_path(self) -> Path:
        return REPLICATION_DIR.joinpath(f'bundle_{int(self.created_at.timestamp()):020}.parquet')

    @staticmethod
    def default() -> 'ReplicaState':
        return ReplicaState(sequence_number=0, created_at=datetime.fromtimestamp(0, UTC))


@dataclass(frozen=True, kw_only=True, slots=True)
class AppState:
    frequency: _Frequency
    last_replica: ReplicaState
    last_sequence_id: int

    @property
    def next_replica(self) -> 'ReplicaState':
        return ReplicaState(
            sequence_number=self.last_replica.sequence_number + 1,
            created_at=self.last_replica.created_at + _FREQUENCY_TIMEDELTA[self.frequency],
        )


async def main() -> None:
    state = _load_app_state()
    click.echo(f'Resuming replication after {state.frequency}/{state.last_replica.sequence_number}')
    while True:
        with SENTRY_REPLICATION_MONITOR, start_transaction(op='task', name='replication'):
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
            click.echo(f'Finished replication sequence {state.frequency}/{state.last_replica.sequence_number}')


@retry(timedelta(minutes=30))
async def _iterate(state: AppState) -> AppState:
    while True:
        next_replica = state.next_replica
        if state.frequency == 'minute' or next_replica.created_at <= datetime.now(UTC):
            break
        old_frequency_str = click.style(f'{state.frequency}', fg='cyan')
        state = await _increase_frequency(state)
        new_frequency_str = click.style(f'{state.frequency}', fg='bright_cyan')
        click.echo(f'Increased replication frequency {old_frequency_str} -> {new_frequency_str}')
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
    df, last_sequence_id = _parse_actions(
        XMLToDict.parse(gzip.decompress(r.content), size_limit=None)['osmChange'],
        last_sequence_id=state.last_sequence_id,
    )
    df.write_parquet(remote_replica.path, compression='lz4', statistics=False)
    return replace(state, last_replica=remote_replica, last_sequence_id=last_sequence_id)


@cython.cfunc
def _parse_actions(
    actions: list[tuple[OSMChangeAction, list[tuple[ElementType, dict]]]],
    *,
    last_sequence_id: int,
    # HACK: faster lookup
    orjson_dumps: Callable[[Any], bytes] = orjson.dumps,
) -> tuple[pl.DataFrame, int]:
    data: list[tuple] = []
    action: str
    for action, elements_ in actions:
        # skip osmChange attributes
        if action[0] == '@':
            continue
        elements: list[tuple[ElementType, dict]] = elements_
        element_type: str
        element: dict
        for element_type, element in elements:
            tags = {tag['@k']: tag['@v'] for tag in tags_} if (tags_ := element.get('tag')) is not None else None
            point: str | None = None
            members: tuple[dict, ...]
            if element_type == 'node':
                members = ()
                if (lon := element.get('@lon')) is not None and (lat := element.get('@lat')) is not None:
                    point = compressible_geometry(Point(lon, lat)).wkb_hex
            elif element_type == 'way':
                members = (
                    tuple(
                        {
                            'order': order,
                            'type': 'node',
                            'id': member['@ref'],
                            'role': '',
                        }
                        for order, member in enumerate(members_)
                    )
                    if (members_ := element.get('nd')) is not None
                    else ()
                )
            elif element_type == 'relation':
                members = (
                    tuple(
                        {
                            'order': order,
                            'type': member['@type'],
                            'id': member['@ref'],
                            'role': member['@role'],
                        }
                        for order, member in enumerate(members_)
                    )
                    if (members_ := element.get('member')) is not None
                    else ()
                )
            else:
                raise NotImplementedError(f'Unsupported element type {element_type!r}')
            data.append(
                (
                    element['@changeset'],  # changeset_id
                    element_type,  # type
                    element['@id'],  # id
                    element['@version'],  # version
                    (tags is not None) or (point is not None) or bool(members),  # visible
                    orjson_dumps(tags).decode() if (tags is not None) else '{}',  # tags
                    point,  # point
                    members,  # members
                    element['@timestamp'],  # created_at
                    element.get('@uid'),  # user_id
                    element.get('@user'),  # display_name
                )
            )
    start_sequence_id = last_sequence_id + 1
    last_sequence_id += len(data)
    sequence_ids = np.arange(start_sequence_id, last_sequence_id + 1, dtype=np.uint64)
    schema = dict(_PARQUET_SCHEMA)
    del schema['sequence_id']
    df = (
        pl.LazyFrame(data, schema, orient='row')
        .sort('created_at', maintain_order=True)
        .with_columns_seq(pl.Series('sequence_id', sequence_ids))
        .collect()
    )
    return df, last_sequence_id


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
    paths = sorted(REPLICATION_DIR.glob('replica_*.parquet'))
    num_paths_str = click.style(f'{len(paths)} replica files', fg='green')
    click.echo(f'Bundling {num_paths_str}')
    pl.read_parquet(paths, schema=_PARQUET_SCHEMA).write_parquet(
        state.last_replica.bundle_path,
        compression_level=9,
        statistics=False,
        data_page_size=128 * 1024 * 1024,
    )


async def _increase_frequency(state: AppState) -> AppState:
    current_timedelta = _FREQUENCY_TIMEDELTA[state.frequency]
    current_created_at = state.last_replica.created_at
    new_frequency: _Frequency = 'minute' if state.frequency == 'hour' else 'hour'
    new_timedelta = _FREQUENCY_TIMEDELTA[new_frequency]
    frequency_downscale = new_timedelta.total_seconds() / current_timedelta.total_seconds()

    step: cython.int = 2 << 4
    new_sequence_number: cython.longlong = int(state.last_replica.sequence_number * frequency_downscale)
    direction_forward: bool | None = None
    while True:
        if not step:
            raise ValueError(f"Couldn't find {new_frequency!r} replica at {current_created_at!r}")
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
        if new_replica.created_at > current_created_at:  # too late
            if direction_forward is None:
                direction_forward = False
            elif direction_forward:
                step >>= 1
            new_sequence_number -= step
        elif new_replica.created_at < current_created_at:  # too early
            if direction_forward is None:
                direction_forward = True
            elif not direction_forward:
                step >>= 1
            new_sequence_number += step
        else:  # found
            return replace(state, frequency=new_frequency, last_replica=new_replica)


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
    key: str
    val: str
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


async def migrate():
    paths = sorted(REPLICATION_DIR.glob('bundle_*.parquet'))
    for i, path in enumerate(paths):
        ts = int(path.stem.split('_', 1)[1])
        if ts <= 1608681600:
            continue
        print(f'Migrating {ts}')
        lf = pl.scan_parquet(path)

        start_sequence_id = lf.select('sequence_id').head(1).collect()['sequence_id'][0]
        end_sequence_id = lf.select('sequence_id').tail(1).collect()['sequence_id'][0]
        print(f'[{ts}] Sequence range: {start_sequence_id} - {end_sequence_id}')
        actual_data_size = lf.select('sequence_id').unique().collect().height
        expected_data_size = end_sequence_id - start_sequence_id + 1
        if actual_data_size != expected_data_size:
            del lf
            print(f'[{ts}] Corrupted at {datetime.fromtimestamp(ts, UTC)}, regenerating...')
            app_state = AppState(
                frequency='day',
                last_replica=ReplicaState(
                    sequence_number=i * 7,
                    created_at=datetime.fromtimestamp(int(paths[i - 1].stem.split('_', 1)[1]), UTC),
                ),
                last_sequence_id=pl.scan_parquet(paths[i - 1])
                .select('sequence_id')
                .tail(1)
                .collect()['sequence_id'][0],
            )
            for ii in range(7):
                print(f'{ii + 1}/{7} ...')
                app_state = await _iterate(app_state)
            _bundle_data_if_needed(app_state)
            lf = pl.scan_parquet(path)
            seq_sorted = lf.select('sequence_id').collect()['sequence_id'].is_sorted()
            print(f'[{ts}] Is sequence sorted: {seq_sorted}')
            assert seq_sorted
            _clean_leftover_data(app_state)
            start_sequence_id = lf.select('sequence_id').head(1).collect()['sequence_id'][0]
            end_sequence_id = lf.select('sequence_id').tail(1).collect()['sequence_id'][0]
            print(f'[{ts}] Sequence range: {start_sequence_id} - {end_sequence_id}')

        seq_sorted = lf.select('sequence_id').collect()['sequence_id'].is_sorted()
        print(f'[{ts}] Is sequence sorted: {seq_sorted}')
        time_sorted = lf.select('created_at').collect()['created_at'].is_sorted()
        print(f'[{ts}] Is time sorted: {time_sorted}')

        prev_end_sequence_id = 0
        if i > 0:
            prev_end_sequence_id = (
                pl.scan_parquet(paths[i - 1]).select('sequence_id').tail(1).collect()['sequence_id'][0]
            )
        if seq_sorted and time_sorted and start_sequence_id == prev_end_sequence_id + 1:
            print(f'[{ts}] Skipping')
            continue
        start_sequence_id = max(start_sequence_id, prev_end_sequence_id + 1)
        end_sequence_id = start_sequence_id + actual_data_size - 1

        print(f'[{ts}] New sequence range: {start_sequence_id} - {end_sequence_id}')
        print(f'[{ts}] Sorting...')
        tmp_path = path.with_name(f'{path.name}.tmp')
        sequence_ids = np.arange(start_sequence_id, end_sequence_id + 1, dtype=np.uint64)
        pl.DataFrame(
            lf.sort('created_at', maintain_order=True)
            .with_columns_seq(pl.Series('sequence_id', sequence_ids))
            .select(_PARQUET_SCHEMA.keys())
            .collect(),
            schema=_PARQUET_SCHEMA,
            orient='row',
        ).write_parquet(
            tmp_path,
            compression_level=9,
            statistics=False,
            data_page_size=128 * 1024 * 1024,
        )
        tmp_path.rename(path)


if __name__ == '__main__':
    asyncio.run(migrate())
