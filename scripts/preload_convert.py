import gc
import os
from collections.abc import Callable
from datetime import datetime
from multiprocessing import Pool
from pathlib import Path
from typing import Any

import cython
import numpy as np
import orjson
import polars as pl
import uvloop
from shapely import Point
from tqdm import tqdm

from app.config import PRELOAD_DIR
from app.lib.compressible_geometry import compressible_geometry
from app.lib.xmltodict import XMLToDict
from app.models.db import *  # noqa: F403
from app.models.element import ElementType

PLANET_INPUT_PATH = PRELOAD_DIR.joinpath('preload.osm')
PLANET_PARQUET_PATH = PRELOAD_DIR.joinpath('preload.osm.parquet')
if not PLANET_INPUT_PATH.is_file():
    raise FileNotFoundError(f'Planet data file not found: {PLANET_INPUT_PATH}')

NOTES_INPUT_PATH = PRELOAD_DIR.joinpath('preload.osn')
NOTES_PARQUET_PATH = PRELOAD_DIR.joinpath('preload.osn.parquet')
if not NOTES_INPUT_PATH.is_file():
    raise FileNotFoundError(f'Notes data file not found: {PLANET_INPUT_PATH}')

MEMORY_LIMIT = 2 * (1024 * 1024 * 1024)  # 2 GB => ~50 GB total memory usage
NUM_WORKERS = os.process_cpu_count() or 1
WORKER_MEMORY_LIMIT = MEMORY_LIMIT // NUM_WORKERS

# freeze all gc objects before starting for improved performance
gc.collect()
gc.freeze()
gc.disable()


@cython.cfunc
def get_csv_path(name: str):
    return PRELOAD_DIR.joinpath(f'{name}.csv')


@cython.cfunc
def get_worker_path(base: Path, i: int):
    return base.with_suffix(f'{base.suffix}.{i}')


def planet_worker(
    args: tuple[int, int, int],
    *,
    # HACK: faster lookup
    orjson_dumps: Callable[[Any], bytes] = orjson.dumps,
) -> None:
    i, from_seek, to_seek = args  # from_seek(inclusive), to_seek(exclusive)
    data: list[tuple] = []
    schema = {
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

    with PLANET_INPUT_PATH.open('rb') as f_in:
        if from_seek > 0:
            f_in.seek(from_seek)
            input_buffer = b'<osm>\n' + f_in.read(to_seek - from_seek)
        else:
            input_buffer = f_in.read(to_seek)

    elements: list[tuple[ElementType, dict]]
    elements = XMLToDict.parse(input_buffer, size_limit=None)['osm']
    # free memory
    del input_buffer

    element_type: str
    element: dict
    for element_type, element in elements:
        if element_type not in {'node', 'way', 'relation'}:
            continue
        tags = {tag['@k']: tag['@v'] for tag in element.get('tag', ())}
        point: str | None = None
        members: list[dict] = []
        if element_type == 'node':
            if (lon := element.get('@lon')) is not None and (lat := element.get('@lat')) is not None:
                point = compressible_geometry(Point(lon, lat)).wkb_hex
        elif element_type == 'way':
            member: dict
            for member in element.get('nd', ()):
                members.append(
                    {
                        'order': len(members),
                        'type': 'node',
                        'id': member['@ref'],
                        'role': '',
                    }
                )
        elif element_type == 'relation':
            member: dict
            for member in element.get('member', ()):
                members.append(
                    {
                        'order': len(members),
                        'type': member['@type'],
                        'id': member['@ref'],
                        'role': member['@role'],
                    }
                )
        data.append(
            (
                element['@changeset'],  # changeset_id
                element_type,  # type
                element['@id'],  # id
                element['@version'],  # version
                bool(point is not None or tags or members),  # visible
                orjson_dumps(tags).decode() if tags else '{}',  # tags
                point,  # point
                members,  # members
                element['@timestamp'],  # created_at
                element.get('@uid'),  # user_id
                element.get('@user'),  # display_name
            )
        )
    df = pl.DataFrame(data, schema, orient='row')
    df.write_parquet(get_worker_path(PLANET_PARQUET_PATH, i), compression='lz4', statistics=False)
    gc.collect()


def run_planet_workers() -> None:
    input_size = PLANET_INPUT_PATH.stat().st_size
    num_tasks = input_size // WORKER_MEMORY_LIMIT
    from_seek_search = (b'  <node', b'  <way', b'  <relation')
    from_seeks: list[int] = []
    print(f'Configuring {num_tasks} tasks (using {NUM_WORKERS} workers)')

    with PLANET_INPUT_PATH.open('rb') as f_in:
        for i in range(num_tasks):
            from_seek = (input_size // num_tasks) * i
            if i > 0:
                f_in.seek(from_seek)
                lookahead = f_in.read(1024 * 1024)  # 1 MB
                lookahead_finds = (lookahead.find(search) for search in from_seek_search)
                min_find = min(find for find in lookahead_finds if find > -1)
                from_seek += min_find
            from_seeks.append(from_seek)

    args: tuple[tuple[int, int, int], ...] = tuple(
        (i, from_seek, (from_seeks[i + 1] if i + 1 < num_tasks else input_size))
        for i, from_seek in enumerate(from_seeks)
    )
    with Pool(NUM_WORKERS) as pool:
        for _ in tqdm(
            pool.imap_unordered(planet_worker, args),
            desc='Preparing planet data',
            total=num_tasks,
        ):
            ...


def merge_planet_worker_results() -> None:
    input_size = PLANET_INPUT_PATH.stat().st_size
    num_tasks = input_size // WORKER_MEMORY_LIMIT
    paths = [get_worker_path(PLANET_PARQUET_PATH, i) for i in range(num_tasks)]
    created_at_all: list[int] = []

    for path in tqdm(paths, desc='Assigning sequence IDs (step 1/2)'):
        df = pl.read_parquet(path, columns=['created_at'])
        created_at = df.to_series().dt.epoch('s').to_numpy(allow_copy=False)
        created_at_all.extend(created_at)

    print('Assigning sequence IDs (step 2/2)')
    created_at_argsort = np.argsort(created_at_all).astype(np.uint64)

    # free memory
    del created_at_all

    sequence_ids_all = np.empty_like(created_at_argsort, dtype=np.uint64)
    sequence_ids_all[created_at_argsort] = np.arange(1, len(created_at_argsort) + 1, dtype=np.uint64)
    last_sequence_id_index = len(sequence_ids_all)
    type_id_sequence_map: dict[tuple[str, int], int] = {}

    # free memory
    del created_at_argsort

    for path in tqdm(reversed(paths), desc='Assigning next sequence IDs', total=len(paths)):
        df = pl.read_parquet(path)

        sequence_ids = sequence_ids_all[last_sequence_id_index - df.height : last_sequence_id_index]
        last_sequence_id_index -= df.height
        df = df.with_columns_seq(pl.Series('sequence_id', sequence_ids))

        next_sequence_ids = np.empty(df.height, dtype=np.float64)

        i: cython.int
        for i, (type, id, sequence_id) in enumerate(df.select('type', 'id', 'sequence_id').reverse().iter_rows()):
            type_id = (type, id)
            next_sequence_ids[i] = type_id_sequence_map.get(type_id)
            type_id_sequence_map[type_id] = sequence_id

        next_sequence_ids = np.flip(next_sequence_ids)
        df = df.with_columns_seq(pl.Series('next_sequence_id', next_sequence_ids, pl.UInt64, nan_to_null=True))
        df.write_parquet(path, compression='lz4', statistics=False)

    # free memory
    del sequence_ids_all
    del type_id_sequence_map

    print(f'Merging {len(paths)} worker files')
    lf = pl.scan_parquet(paths)
    lf.sink_parquet(
        PLANET_PARQUET_PATH,
        compression_level=3,
        statistics=False,
        row_group_size=100_000,
        maintain_order=False,
    )
    for path in paths:
        path.unlink()


def notes_worker(args: tuple[int, int, int]) -> None:
    i, from_seek, to_seek = args  # from_seek(inclusive), to_seek(exclusive)
    data: list[tuple] = []
    schema = {
        'id': pl.UInt64,
        'point': pl.String,
        'comments': pl.List(
            pl.Struct(
                {
                    'user_id': pl.UInt64,
                    'display_name': pl.String,
                    'event': pl.Enum(('opened', 'closed', 'reopened', 'commented', 'hidden')),
                    'body': pl.String,
                    'created_at': pl.Datetime,
                }
            )
        ),
        'created_at': pl.Datetime,
        'updated_at': pl.Datetime,
        'closed_at': pl.Datetime,
        'hidden_at': pl.Datetime,
    }

    with NOTES_INPUT_PATH.open('rb') as f_in:
        if from_seek > 0:
            f_in.seek(from_seek)
            input_buffer = b'<osm-notes>\n' + f_in.read(to_seek - from_seek)
        else:
            input_buffer = f_in.read(to_seek)

    notes: list[dict]
    notes = XMLToDict.parse(input_buffer, size_limit=None)['osm-notes']['note']
    # free memory
    del input_buffer

    note: dict
    for note in notes:
        note_created_at: datetime | None = None
        note_updated_at: datetime | None = None
        note_closed_at: datetime | None = None
        note_hidden_at: datetime | None = None
        comments: list[dict] = []
        comment: dict
        for comment in note.get('comment', ()):
            comment_created_at = comment['@timestamp']
            if note_created_at is None:
                note_created_at = comment_created_at
            note_updated_at = comment_created_at
            event: str = comment['@action']
            if event == 'closed':
                note_closed_at = comment_created_at
            elif event == 'hidden':
                note_hidden_at = comment_created_at
            elif event == 'reopened':
                note_closed_at = None
                note_hidden_at = None
            comments.append(
                {
                    'user_id': comment.get('@uid'),
                    'display_name': comment.get('@user'),
                    'event': event,
                    'body': comment.get('#text', ''),
                    'created_at': comment_created_at,
                }
            )
        point = compressible_geometry(Point(note['@lon'], note['@lat'])).wkb_hex
        data.append(
            (
                note['@id'],  # note_id
                point,  # point
                comments,  # comments
                note_created_at,  # created_at
                note_updated_at,  # updated_at
                note_closed_at,  # closed_at
                note_hidden_at,  # hidden_at
            )
        )

    df = pl.DataFrame(data, schema, orient='row')
    df.write_parquet(get_worker_path(NOTES_PARQUET_PATH, i), compression='lz4', statistics=False)
    gc.collect()


def run_notes_workers() -> None:
    input_size = NOTES_INPUT_PATH.stat().st_size
    num_tasks = input_size // WORKER_MEMORY_LIMIT
    from_seek_search = (b'<note',)
    from_seeks = []

    print(f'Configuring {num_tasks} tasks (using {NUM_WORKERS} workers)')
    with NOTES_INPUT_PATH.open('rb') as f_in:
        for i in range(num_tasks):
            from_seek = (input_size // num_tasks) * i
            if i > 0:
                f_in.seek(from_seek)
                lookahead = f_in.read(1024 * 1024)  # 1 MB
                lookahead_finds = (lookahead.find(search) for search in from_seek_search)
                min_find = min(find for find in lookahead_finds if find > -1)
                from_seek += min_find
            from_seeks.append(from_seek)

    args: tuple[tuple[int, int, int], ...] = tuple(
        (i, from_seek, (from_seeks[i + 1] if i + 1 < num_tasks else input_size))
        for i, from_seek in enumerate(from_seeks)
    )
    with Pool(NUM_WORKERS) as pool:
        for _ in tqdm(
            pool.imap_unordered(notes_worker, args),
            desc='Preparing notes data',
            total=num_tasks,
        ):
            ...


def merge_notes_worker_results() -> None:
    input_size = NOTES_INPUT_PATH.stat().st_size
    num_tasks = input_size // WORKER_MEMORY_LIMIT
    paths = [get_worker_path(NOTES_PARQUET_PATH, i) for i in range(num_tasks)]

    print(f'Merging {len(paths)} worker files')
    lf = pl.scan_parquet(paths)
    lf.sink_parquet(
        NOTES_PARQUET_PATH,
        compression_level=3,
        statistics=False,
        row_group_size=100_000,
        maintain_order=False,
    )
    for path in paths:
        path.unlink()


def write_changeset_csv() -> None:
    df = pl.scan_parquet(PLANET_PARQUET_PATH)
    df = df.select('changeset_id', 'created_at', 'user_id')
    df = df.rename({'changeset_id': 'id'})
    df = df.group_by('id').agg(
        pl.first('user_id'),
        pl.max('created_at').alias('closed_at'),
        pl.len().alias('size'),
    )
    df = df.with_columns_seq(pl.lit('{}').alias('tags'))
    df.sink_csv(get_csv_path('changeset'))


def write_element_csv() -> None:
    df: pl.LazyFrame = pl.scan_parquet(PLANET_PARQUET_PATH)
    df = df.select(
        'sequence_id',
        'changeset_id',
        'type',
        'id',
        'version',
        'visible',
        'tags',
        'point',
        'created_at',
        'next_sequence_id',
    )
    df.sink_csv(get_csv_path('element'))


def write_element_member_csv() -> None:
    df: pl.LazyFrame = pl.scan_parquet(PLANET_PARQUET_PATH)
    df = df.select('sequence_id', 'members')
    df = df.filter(pl.col('members').list.len() > 0)
    df = df.explode('members')
    df = df.unnest('members')
    df.sink_csv(get_csv_path('element_member'))


def write_note_csv() -> None:
    df: pl.LazyFrame = pl.scan_parquet(NOTES_PARQUET_PATH)
    df = df.select(
        'id',
        'point',
        'created_at',
        'updated_at',
        'closed_at',
        'hidden_at',
    )
    df.sink_csv(get_csv_path('note'))


def write_note_comment_csv() -> None:
    df: pl.LazyFrame = pl.scan_parquet(NOTES_PARQUET_PATH)
    df = df.select('id', 'comments')
    df = df.rename({'id': 'note_id'})
    df = df.with_columns_seq(pl.lit(None).alias('user_ip'))
    df = df.explode('comments')
    df = df.unnest('comments')
    df = df.drop('display_name')
    df.sink_csv(get_csv_path('note_comment'))


def write_user_csv() -> None:
    planet_df = pl.scan_parquet(PLANET_PARQUET_PATH)
    planet_df = planet_df.select('user_id', 'display_name')

    notes_df = pl.scan_parquet(NOTES_PARQUET_PATH)
    notes_df = notes_df.select('comments')
    notes_df = notes_df.explode('comments')
    notes_df = notes_df.unnest('comments')
    notes_df = notes_df.select('user_id', 'display_name')

    df = pl.concat((planet_df, notes_df))
    df = df.rename({'user_id': 'id'})
    df = df.unique('id').drop_nulls('id')
    df = df.with_columns_seq(
        pl.concat_str('id', pl.lit('@localhost.invalid')).alias('email'),
        pl.lit('').alias('password_pb'),
        pl.lit('127.0.0.1').alias('created_ip'),
        pl.lit('active').alias('status'),
        pl.lit('en').alias('language'),
        pl.lit(True).alias('activity_tracking'),
        pl.lit(True).alias('crash_reporting'),
    )
    df.sink_csv(get_csv_path('user'))


async def main() -> None:
    run_planet_workers()
    merge_planet_worker_results()
    run_notes_workers()
    merge_notes_worker_results()

    print('Writing changeset CSV..')
    write_changeset_csv()
    print('Writing element CSV..')
    write_element_csv()
    print('Writing element member CSV')
    write_element_member_csv()
    print('Writing note CSV')
    write_note_csv()
    print('Writing note comment CSV')
    write_note_comment_csv()
    print('Writing user CSV')
    write_user_csv()


if __name__ == '__main__':
    uvloop.run(main())
    print('Done! Done! Done!')
