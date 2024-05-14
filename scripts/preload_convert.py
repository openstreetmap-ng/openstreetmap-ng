import gc
import os
import pathlib
from datetime import datetime
from functools import cache
from multiprocessing import Pool

import anyio
import lxml.etree as ET
import polars as pl
from tqdm import tqdm

from app.config import PRELOAD_DIR
from app.models.db import *  # noqa: F403
from app.utils import JSON_ENCODE

input_path = pathlib.Path(PRELOAD_DIR / 'preload.osm')
if not input_path.is_file():
    raise FileNotFoundError(f'File not found: {input_path}')

data_parquet_path = pathlib.Path(PRELOAD_DIR / 'preload.parquet')

user_csv_path = pathlib.Path(PRELOAD_DIR / 'user.csv')
changeset_csv_path = pathlib.Path(PRELOAD_DIR / 'changeset.csv')
element_csv_path = pathlib.Path(PRELOAD_DIR / 'element.csv')

buffering = 32 * 1024 * 1024  # 32 MB
read_memory_limit = 2 * 1024 * 1024 * 1024  # 2 GB => ~50 GB total memory usage

num_workers = os.cpu_count()

input_size = input_path.stat().st_size
task_read_memory_limit = read_memory_limit // num_workers
num_tasks = input_size // task_read_memory_limit
task_size = input_size // num_tasks

# freeze all gc objects before starting for improved performance
gc.collect()
gc.freeze()
gc.disable()


@cache
def get_worker_output_path(i: int) -> pathlib.Path:
    return data_parquet_path.with_suffix(f'.parquet.{i}')


def worker(args: tuple[int, int, int]) -> None:
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
        'members': pl.String,
        'created_at': pl.Datetime,
        'user_id': pl.UInt64,
        'display_name': pl.String,
    }

    with input_path.open('rb') as f_in:
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
        element: ET.ElementBase
        tag: str = element.tag
        attrib: dict = element.attrib

        if tag not in ('node', 'way', 'relation'):
            continue

        tags = {}
        members = []

        for child in element:
            child: ET.ElementBase
            child_tag: str = child.tag
            child_attrib: dict = child.attrib

            if child_tag == 'tag':
                tags[child_attrib['k']] = child_attrib['v']
            elif child_tag == 'nd':
                members.append(
                    {
                        'type': 'node',
                        'id': int(child_attrib['ref']),
                        'role': '',
                    }
                )
            elif child_tag == 'member':
                members.append(
                    {
                        'type': child_attrib['type'],
                        'id': int(child_attrib['ref']),
                        'role': child_attrib['role'],
                    }
                )

        if tag == 'node' and (lon := attrib.get('lon')) is not None and (lat := attrib.get('lat')) is not None:
            point = f'POINT ({lon} {lat})'
        else:
            point = None

        if tag == 'node':
            visible = point is not None
        elif tag == 'way' or tag == 'relation':
            visible = tags or members

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
                JSON_ENCODE(tags).decode() if tags else '{}',  # tags
                point,  # point
                JSON_ENCODE(members).decode() if members else '[]',  # members
                datetime.fromisoformat(attrib['timestamp']),  # created_at
                user_id,  # user_id
                user_display_name,  # display_name
            )
        )

    df = pl.DataFrame(data, schema=schema)
    df.write_parquet(get_worker_output_path(i), compression='uncompressed', statistics=False)
    gc.collect()


def run_workers() -> None:
    from_seek_search = (b'  <node', b'  <way', b'  <relation')
    from_seeks = []

    print(f'Configuring {num_tasks} tasks (using {num_workers} workers)')

    with input_path.open('rb') as f_in:
        for i in range(num_tasks):
            from_seek = task_size * i

            if i > 0:
                f_in.seek(from_seek)
                lookahead = f_in.read(1024 * 1024)  # 1 MB
                min_find = float('inf')

                for search in from_seek_search:
                    if (found := lookahead.find(search)) > -1:
                        min_find = min(min_find, found)

                assert min_find != float('inf')
                from_seek += min_find

            from_seeks.append(from_seek)

    args = []
    for i in range(num_tasks):
        from_seek = from_seeks[i]
        to_seek = from_seeks[i + 1] if i + 1 < num_tasks else input_size
        args.append((i, from_seek, to_seek))

    with Pool(num_workers) as pool:
        for _ in tqdm(
            pool.imap_unordered(worker, args),
            desc='Preparing data',
            total=num_tasks,
        ):
            ...


def merge_worker_files() -> None:
    paths = [get_worker_output_path(i) for i in range(num_tasks)]

    current_sequence_id = 1
    type_id_sequence_map: dict[tuple[str, int], int] = {}

    for path in tqdm(paths, desc='Assigning sequence IDs'):
        df = pl.read_parquet(path)
        df = df.with_row_index('sequence_id', current_sequence_id)
        df.write_parquet(path, compression='uncompressed', statistics=False)
        current_sequence_id += df.height

    for path in tqdm(reversed(paths), desc='Assigning next sequence IDs', total=len(paths)):
        df = pl.read_parquet(path)
        next_sequence_ids = [None] * df.height

        for i, (type, id, sequence_id) in enumerate(df.select('type', 'id', 'sequence_id').reverse().iter_rows()):
            type_id = (type, id)
            next_sequence_ids[i] = type_id_sequence_map.get(type_id)
            type_id_sequence_map[type_id] = sequence_id

        df = df.with_columns(pl.Series('next_sequence_id', next_sequence_ids, pl.UInt64).reverse())
        df.write_parquet(path, compression='uncompressed', statistics=False)

    print('Saving processed data...')
    df = pl.scan_parquet(paths)
    df.sink_parquet(data_parquet_path)

    for path in paths:
        path.unlink()


def write_element_csv() -> None:
    df: pl.LazyFrame = pl.scan_parquet(data_parquet_path)
    df = df.select(
        'sequence_id',
        'changeset_id',
        'type',
        'id',
        'version',
        'visible',
        'tags',
        'point',
        'members',
        'created_at',
        'next_sequence_id',
    )
    df.sink_csv(element_csv_path)


def write_user_csv() -> None:
    df: pl.LazyFrame = pl.scan_parquet(data_parquet_path)
    df = df.select('user_id', 'display_name').unique()
    df = df.rename({'user_id': 'id'})
    df = df.drop_nulls('id')
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
    df.sink_csv(user_csv_path)


def write_changeset_csv() -> None:
    df = pl.scan_parquet(data_parquet_path)
    df = df.select('changeset_id', 'created_at', 'user_id')
    df = df.rename({'changeset_id': 'id'})
    df = df.group_by('id').agg(
        pl.first('user_id'),
        pl.max('created_at').alias('closed_at'),
        pl.len().alias('size'),
    )
    df = df.with_columns(pl.lit('{}').alias('tags'))
    df.sink_csv(changeset_csv_path)


async def convert_xml2csv() -> None:
    run_workers()
    merge_worker_files()

    print('Writing user CSV...')
    write_user_csv()

    print('Writing changeset CSV...')
    write_changeset_csv()

    print('Writing element CSV...')
    write_element_csv()


async def main():
    await convert_xml2csv()


if __name__ == '__main__':
    anyio.run(main)
    print('Done! Done! Done!')
