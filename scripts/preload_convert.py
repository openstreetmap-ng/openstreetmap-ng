import gc
import os
from datetime import datetime
from multiprocessing import Pool
from pathlib import Path

import lxml.etree as ET
import numpy as np
import polars as pl
import uvloop
from tqdm import tqdm

from app.config import PRELOAD_DIR
from app.models.db import *  # noqa: F403
from app.utils import json_encodes

PLANET_INPUT_PATH = PRELOAD_DIR.joinpath('preload.osm')
PLANET_PARQUET_PATH = PRELOAD_DIR.joinpath('preload.osm.parquet')
if not PLANET_INPUT_PATH.is_file():
    raise FileNotFoundError(f'Planet data file not found: {PLANET_INPUT_PATH}')

NOTES_INPUT_PATH = PRELOAD_DIR.joinpath('preload.osn')
NOTES_PARQUET_PATH = PRELOAD_DIR.joinpath('preload.osn.parquet')
if not NOTES_INPUT_PATH.is_file():
    raise FileNotFoundError(f'Notes data file not found: {PLANET_INPUT_PATH}')

buffering = 32 * (1024 * 1024)  # 32 MB
read_memory_limit = 2 * (1024 * 1024 * 1024)  # 2 GB => ~50 GB total memory usage

num_workers = os.cpu_count() or 1
task_read_memory_limit = read_memory_limit // num_workers

# freeze all gc objects before starting for improved performance
gc.collect()
gc.freeze()
gc.disable()


def get_csv_path(name: str) -> Path:
    return PRELOAD_DIR.joinpath(f'{name}.csv')


def get_worker_path(base: Path, i: int) -> Path:
    return base.with_suffix(f'{base.suffix}.{i}')


def planet_worker(args: tuple[int, int, int]) -> None:
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
                    'type': pl.String,
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

    root = ET.fromstring(  # noqa: S320
        input_buffer,
        parser=ET.XMLParser(
            ns_clean=True,
            recover=True,
            resolve_entities=False,
            remove_comments=True,
            remove_pis=True,
            collect_ids=False,
            compact=False,
        ),
    )

    # free memory
    del input_buffer

    for element in root:
        tag = element.tag
        attrib = element.attrib
        if tag not in {'node', 'way', 'relation'}:
            continue

        tags_list: list[tuple[str, str]] = []
        members: list[dict] = []

        for child in element:
            child_tag = child.tag
            child_attrib = child.attrib

            if child_tag == 'tag':
                tags_list.append((child_attrib['k'], child_attrib['v']))  # pyright: ignore[reportArgumentType]
            elif child_tag == 'nd':
                members.append(
                    {
                        'order': len(members),
                        'type': 'node',
                        'id': int(child_attrib['ref']),
                        'role': '',
                    }
                )
            elif child_tag == 'member':
                members.append(
                    {
                        'order': len(members),
                        'type': child_attrib['type'],
                        'id': int(child_attrib['ref']),
                        'role': child_attrib['role'],
                    }
                )

        if tag == 'node' and (lon := attrib.get('lon')) is not None and (lat := attrib.get('lat')) is not None:
            point = f'POINT({lon} {lat})'
        else:
            point = None

        if tag == 'node':
            visible = point is not None
        elif tag in {'way', 'relation'}:
            visible = bool(tags_list or members)
        else:
            raise NotImplementedError(f'Unsupported element type {tag!r}')

        uid = attrib.get('uid')
        if uid is not None:
            user_id = int(uid)
            user_display_name = attrib['user']
        else:
            user_id = None
            user_display_name = None

        data.append(
            (
                int(attrib['changeset']),  # changeset_id
                tag,  # type
                int(attrib['id']),  # id
                int(attrib['version']),  # version
                visible,  # visible
                json_encodes(dict(tags_list)) if tags_list else '{}',  # tags
                point,  # point
                members,  # members
                datetime.fromisoformat(attrib['timestamp']),  # created_at  # pyright: ignore[reportArgumentType]
                user_id,  # user_id
                user_display_name,  # display_name
            )
        )

    df = pl.DataFrame(data, schema=schema, orient='row')
    df.write_parquet(get_worker_path(PLANET_PARQUET_PATH, i), compression_level=1, statistics=False)
    gc.collect()


def run_planet_workers() -> None:
    input_size = PLANET_INPUT_PATH.stat().st_size
    num_tasks = input_size // task_read_memory_limit
    from_seek_search = (b'  <node', b'  <way', b'  <relation')
    from_seeks = []

    print(f'Configuring {num_tasks} tasks (using {num_workers} workers)')
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

    args = []
    for i in range(num_tasks):
        from_seek = from_seeks[i]
        to_seek = from_seeks[i + 1] if i + 1 < num_tasks else input_size
        args.append((i, from_seek, to_seek))

    with Pool(num_workers) as pool:
        for _ in tqdm(
            pool.imap_unordered(planet_worker, args),
            desc='Preparing planet data',
            total=num_tasks,
        ):
            ...


def merge_planet_worker_results() -> None:
    input_size = PLANET_INPUT_PATH.stat().st_size
    num_tasks = input_size // task_read_memory_limit
    paths = [get_worker_path(PLANET_PARQUET_PATH, i) for i in range(num_tasks)]
    created_at_all: list[int] = []

    for path in tqdm(paths, desc='Assigning sequence IDs (step 1/2)'):
        df = pl.read_parquet(path, columns=['created_at'], use_statistics=False)
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
        df = pl.read_parquet(path, use_statistics=False)

        sequence_ids = sequence_ids_all[last_sequence_id_index - df.height : last_sequence_id_index]
        last_sequence_id_index -= df.height
        df = df.with_columns(pl.Series('sequence_id', sequence_ids))

        next_sequence_ids = np.empty(df.height, dtype=np.float64)

        for i, (type, id, sequence_id) in enumerate(df.select('type', 'id', 'sequence_id').reverse().iter_rows()):
            type_id = (type, id)
            next_sequence_ids[i] = type_id_sequence_map.get(type_id)
            type_id_sequence_map[type_id] = sequence_id

        next_sequence_ids = np.flip(next_sequence_ids)
        df = df.with_columns(pl.Series('next_sequence_id', next_sequence_ids, pl.UInt64, nan_to_null=True))
        df.write_parquet(path, compression_level=1, statistics=False)

    # free memory
    del sequence_ids_all
    del type_id_sequence_map

    print(f'Merging {len(paths)} worker files')
    lf = pl.scan_parquet(paths)
    lf.sink_parquet(PLANET_PARQUET_PATH, compression_level=3, row_group_size=50_000, maintain_order=False)

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

    root = ET.fromstring(  # noqa: S320
        input_buffer,
        parser=ET.XMLParser(
            ns_clean=True,
            recover=True,
            resolve_entities=False,
            remove_comments=True,
            remove_pis=True,
            collect_ids=False,
            compact=False,
        ),
    )

    # free memory
    del input_buffer

    for element in root:
        tag = element.tag
        attrib = element.attrib
        if tag != 'note':
            continue

        comments: list[dict] = []
        note_created_at: datetime | None = None
        note_updated_at: datetime | None = None
        note_closed_at: datetime | None = None
        note_hidden_at: datetime | None = None

        for child in element:
            child_tag = child.tag
            child_attrib = child.attrib
            if child_tag != 'comment':
                continue

            user_id = child_attrib.get('uid')
            if user_id is not None:
                user_id = int(user_id)

            event = child_attrib['action']
            created_at = datetime.fromisoformat(child_attrib['timestamp'])  # pyright: ignore[reportArgumentType]
            if note_created_at is None:
                note_created_at = created_at
            note_updated_at = created_at
            if event == 'closed':
                note_closed_at = created_at
            elif event == 'hidden':
                note_hidden_at = created_at
            elif event == 'reopened':
                note_closed_at = None
                note_hidden_at = None

            comments.append(
                {
                    'user_id': user_id,
                    'display_name': child_attrib.get('user'),
                    'event': event,
                    'body': child.text or '',
                    'created_at': created_at,
                }
            )

        data.append(
            (
                int(attrib['id']),  # note_id
                f'POINT({attrib['lon']} {attrib['lat']})',  # point
                comments,  # comments
                note_created_at,  # created_at
                note_updated_at,  # updated_at
                note_closed_at,  # closed_at
                note_hidden_at,  # hidden_at
            )
        )

    df = pl.DataFrame(data, schema=schema, orient='row')
    df.write_parquet(get_worker_path(NOTES_PARQUET_PATH, i), compression_level=1, statistics=False)
    gc.collect()


def run_notes_workers() -> None:
    input_size = NOTES_INPUT_PATH.stat().st_size
    num_tasks = input_size // task_read_memory_limit
    from_seek_search = (b'<note',)
    from_seeks = []

    print(f'Configuring {num_tasks} tasks (using {num_workers} workers)')
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

    args = []
    for i in range(num_tasks):
        from_seek = from_seeks[i]
        to_seek = from_seeks[i + 1] if i + 1 < num_tasks else input_size
        args.append((i, from_seek, to_seek))

    with Pool(num_workers) as pool:
        for _ in tqdm(
            pool.imap_unordered(notes_worker, args),
            desc='Preparing notes data',
            total=num_tasks,
        ):
            ...


def merge_notes_worker_results() -> None:
    input_size = NOTES_INPUT_PATH.stat().st_size
    num_tasks = input_size // task_read_memory_limit
    paths = [get_worker_path(NOTES_PARQUET_PATH, i) for i in range(num_tasks)]

    print(f'Merging {len(paths)} worker files')
    lf = pl.scan_parquet(paths)
    lf.sink_parquet(NOTES_PARQUET_PATH, compression_level=3, row_group_size=50_000, maintain_order=False)

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
    df = df.with_columns(pl.lit('{}').alias('tags'))
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
    df = df.with_columns(
        pl.lit(None).alias('user_ip'),
    )
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
    df = df.with_columns(
        pl.concat_str('id', pl.lit('@localhost.invalid')).alias('email'),
        pl.lit('x').alias('password_hashed'),
        pl.lit('127.0.0.1').alias('created_ip'),
        pl.lit('active').alias('status'),
        pl.lit(None).alias('auth_provider'),
        pl.lit(None).alias('auth_uid'),
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
