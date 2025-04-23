import gc
from argparse import ArgumentParser
from datetime import datetime
from multiprocessing import Pool
from pathlib import Path

import cython
import pyarrow as pa
import pyarrow.parquet as pq
from shapely import Point
from tqdm import tqdm

from app.config import PRELOAD_DIR
from app.db import duckdb_connect
from app.lib.compressible_geometry import compressible_geometry
from app.lib.xmltodict import XMLToDict
from app.models.element import (
    TYPED_ELEMENT_ID_RELATION_MAX,
    TYPED_ELEMENT_ID_RELATION_MIN,
    ElementType,
    TypedElementId,
    typed_element_id,
)
from app.utils import calc_num_workers

PLANET_INPUT_PATH = PRELOAD_DIR.joinpath('preload.osm')
PLANET_PARQUET_PATH = PRELOAD_DIR.joinpath('preload.osm.parquet')

_PLANET_SCHEMA = pa.schema([
    pa.field('changeset_id', pa.uint64()),
    pa.field('typed_id', pa.uint64()),
    pa.field('version', pa.uint64()),
    pa.field('visible', pa.bool_()),
    pa.field('tags', pa.map_(pa.string(), pa.string())),
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

NOTES_INPUT_PATH = PRELOAD_DIR.joinpath('preload.osn')
NOTES_PARQUET_PATH = PRELOAD_DIR.joinpath('preload.osn.parquet')

_NOTES_SCHEMA = pa.schema([
    pa.field('id', pa.uint64()),
    pa.field('point', pa.string()),
    pa.field(
        'comments',
        pa.list_(
            pa.struct([
                pa.field('user_id', pa.uint64()),
                pa.field('display_name', pa.string()),
                pa.field('event', pa.string()),
                pa.field('body', pa.string()),
                pa.field('created_at', pa.timestamp('ms', 'UTC')),
            ])
        ),
    ),
    pa.field('created_at', pa.timestamp('ms', 'UTC')),
    pa.field('updated_at', pa.timestamp('ms', 'UTC')),
    pa.field('closed_at', pa.timestamp('ms', 'UTC')),
    pa.field('hidden_at', pa.timestamp('ms', 'UTC')),
])

_NUM_WORKERS = calc_num_workers()
_TASK_SIZE = 64 * 1024 * 1024  # 64MB


@cython.cfunc
def _get_csv_path(name: str):
    return PRELOAD_DIR.joinpath(f'{name}.csv')


@cython.cfunc
def _get_worker_path(base: Path, i: int):
    return base.with_suffix(f'{base.suffix}.{i}')


def planet_worker(args: tuple[int, int, int]) -> None:
    i, from_seek, to_seek = args  # from_seek(inclusive), to_seek(exclusive)
    data: list[dict] = []

    with PLANET_INPUT_PATH.open('rb') as f_in:
        if from_seek > 0:
            f_in.seek(from_seek)
            input_buffer = b'<osm>\n' + f_in.read(to_seek - from_seek)
        else:
            input_buffer = f_in.read(to_seek)

    elements: list[tuple[ElementType, dict]]
    elements = XMLToDict.parse(input_buffer, size_limit=None)['osm']  # type: ignore
    # free memory
    del input_buffer

    type: str
    element: dict

    for type, element in elements:
        tags = (
            {tag['@k']: tag['@v'] for tag in tags_}
            if (tags_ := element.get('tag')) is not None
            else None
        )
        point: str | None = None
        members: list[tuple[TypedElementId, str | None]] | None = None

        if type == 'node':
            if (lon := element.get('@lon')) is not None:
                point = compressible_geometry(Point(lon, element['@lat'])).wkb_hex
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
            'changeset_id': element['@changeset'],
            'typed_id': typed_element_id(type, element['@id']),
            'version': element['@version'],
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

    pq.write_table(
        pa.Table.from_pylist(data, schema=_PLANET_SCHEMA),
        _get_worker_path(PLANET_PARQUET_PATH, i),
        compression='lz4',
        write_statistics=False,
    )
    del data
    gc.collect()


def run_planet_workers() -> None:
    input_size = PLANET_INPUT_PATH.stat().st_size
    num_tasks = input_size // _TASK_SIZE
    from_seek_search = [b'  <node', b'  <way', b'  <relation']
    from_seeks: list[int] = []
    print(f'Configuring {num_tasks} tasks (using {_NUM_WORKERS} workers)')

    with PLANET_INPUT_PATH.open('rb') as f_in:
        for i in range(num_tasks):
            from_seek = (input_size // num_tasks) * i
            f_in.seek(from_seek)
            lookahead = f_in.read(1024 * 1024)  # 1 MB
            lookahead_finds = (lookahead.find(search) for search in from_seek_search)
            min_find = min(find for find in lookahead_finds if find > -1)
            from_seek += min_find
            from_seeks.append(from_seek)

    args: list[tuple[int, int, int]] = [
        (i, from_seek, (from_seeks[i + 1] if i + 1 < num_tasks else input_size))
        for i, from_seek in enumerate(from_seeks)
    ]
    with Pool(_NUM_WORKERS) as pool:
        for _ in tqdm(
            pool.imap_unordered(planet_worker, args),
            desc='Preparing planet data',
            total=num_tasks,
        ):
            pass


def merge_planet_worker_results() -> None:
    input_size = PLANET_INPUT_PATH.stat().st_size
    num_tasks = input_size // _TASK_SIZE
    paths = [_get_worker_path(PLANET_PARQUET_PATH, i) for i in range(num_tasks)]

    with duckdb_connect() as conn:
        print(f'Merging {len(paths)} worker files')
        conn.sql(f"""
        COPY (
            SELECT
                ROW_NUMBER() OVER (ORDER BY created_at) AS sequence_id,
                changeset_id,
                typed_id,
                version,
                version = MAX(version) OVER (PARTITION BY typed_id) AS latest,
                visible,
                tags,
                point,
                members,
                created_at,
                user_id,
                display_name
            FROM read_parquet({[path.as_posix() for path in paths]!r})
        ) TO {PLANET_PARQUET_PATH.as_posix()!r}
        (COMPRESSION ZSTD, COMPRESSION_LEVEL 3, ROW_GROUP_SIZE_BYTES '128MB')
        """)

    for path in paths:
        path.unlink()


def notes_worker(args: tuple[int, int, int]) -> None:
    i, from_seek, to_seek = args  # from_seek(inclusive), to_seek(exclusive)
    data: list[dict] = []

    with NOTES_INPUT_PATH.open('rb') as f_in:
        if from_seek > 0:
            f_in.seek(from_seek)
            input_buffer = b'<osm-notes>\n' + f_in.read(to_seek - from_seek)
        else:
            input_buffer = f_in.read(to_seek)

    notes: list[dict]
    notes = XMLToDict.parse(input_buffer, size_limit=None)['osm-notes']['note']  # type: ignore
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

            comments.append({
                'user_id': comment.get('@uid'),
                'display_name': comment.get('@user'),
                'event': event,
                'body': comment.get('#text', ''),
                'created_at': comment_created_at,
            })

        point = compressible_geometry(Point(note['@lon'], note['@lat'])).wkb_hex
        data.append({
            'id': note['@id'],
            'point': point,
            'comments': comments,
            'created_at': note_created_at,
            'updated_at': note_updated_at,
            'closed_at': note_closed_at,
            'hidden_at': note_hidden_at,
        })

    pq.write_table(
        pa.Table.from_pylist(data, schema=_NOTES_SCHEMA),
        _get_worker_path(NOTES_PARQUET_PATH, i),
        compression='lz4',
        write_statistics=False,
    )
    del data
    gc.collect()


def run_notes_workers() -> None:
    input_size = NOTES_INPUT_PATH.stat().st_size
    num_tasks = input_size // _TASK_SIZE
    from_seek_search = [b'<note']
    from_seeks = []

    print(f'Configuring {num_tasks} tasks (using {_NUM_WORKERS} workers)')
    with NOTES_INPUT_PATH.open('rb') as f_in:
        for i in range(num_tasks):
            from_seek = (input_size // num_tasks) * i
            if i > 0:
                f_in.seek(from_seek)
                lookahead = f_in.read(1024 * 1024)  # 1 MB
                lookahead_finds = (
                    lookahead.find(search) for search in from_seek_search
                )
                min_find = min(find for find in lookahead_finds if find > -1)
                from_seek += min_find
            from_seeks.append(from_seek)

    args: list[tuple[int, int, int]] = [
        (i, from_seek, (from_seeks[i + 1] if i + 1 < num_tasks else input_size))
        for i, from_seek in enumerate(from_seeks)
    ]
    with Pool(_NUM_WORKERS) as pool:
        for _ in tqdm(
            pool.imap_unordered(notes_worker, args),
            desc='Preparing notes data',
            total=num_tasks,
        ):
            pass


def merge_notes_worker_results() -> None:
    input_size = NOTES_INPUT_PATH.stat().st_size
    num_tasks = input_size // _TASK_SIZE
    paths = [_get_worker_path(NOTES_PARQUET_PATH, i) for i in range(num_tasks)]

    with duckdb_connect() as conn:
        print(f'Merging {len(paths)} worker files')
        conn.sql(f"""
        COPY (
            SELECT *
            FROM read_parquet({[path.as_posix() for path in paths]!r})
        ) TO {NOTES_PARQUET_PATH.as_posix()!r}
        (COMPRESSION ZSTD, COMPRESSION_LEVEL 3, ROW_GROUP_SIZE_BYTES '128MB')
        """)

    for path in paths:
        path.unlink()


def _write_changeset() -> None:
    with duckdb_connect() as conn:
        conn.sql(f"""
        COPY (
            SELECT
                changeset_id AS id,
                ARBITRARY(user_id) AS user_id,
                '' AS tags,
                MIN(created_at) AS created_at,
                MAX(created_at) AS updated_at,
                MAX(created_at) AS closed_at,
                COUNT(*) AS size,
                COUNT_IF(version = 1) AS num_create,
                COUNT_IF(version > 1 AND visible) AS num_modify,
                COUNT_IF(version > 1 AND NOT visible) AS num_delete
            FROM read_parquet({PLANET_PARQUET_PATH.as_posix()!r})
            GROUP BY changeset_id
            ORDER BY changeset_id
        ) TO {_get_csv_path('changeset').as_posix()!r}
        """)


def _write_element() -> None:
    with duckdb_connect() as conn:
        # Utility for escaping text
        conn.execute("""
        CREATE MACRO quote(str) AS
        '"' || replace(replace(str, '\\', '\\\\'), '"', '\\"') || '"'
        """)

        # Convert map to Postgres-hstore format
        conn.execute("""
        CREATE MACRO map_to_hstore(m) AS
        array_to_string(
            list_transform(
                map_entries(m),
                entry -> quote(entry.key) || '=>' || quote(entry.value)
            ),
            ','
        )
        """)

        # Encode array in Postgres-compatible format
        conn.execute("""
        CREATE MACRO pg_array(arr) AS
        '{' || array_to_string(arr, ',') || '}'
        """)

        conn.sql(f"""
        COPY (
            SELECT
                sequence_id,
                changeset_id,
                typed_id,
                version,
                latest,
                visible,
                IF(
                    tags IS NOT NULL,
                    map_to_hstore(tags),
                    NULL
                ) AS tags,
                point,
                IF(
                    members IS NOT NULL,
                    pg_array(list_transform(members, x -> x.typed_id)),
                    NULL
                ) AS members,
                IF(
                    members IS NOT NULL
                    AND typed_id BETWEEN {TYPED_ELEMENT_ID_RELATION_MIN} AND {TYPED_ELEMENT_ID_RELATION_MAX},
                    pg_array(list_transform(members, x -> quote(x.role))),
                    NULL
                ) AS members_roles,
                created_at
            FROM read_parquet({PLANET_PARQUET_PATH.as_posix()!r})
            ORDER BY typed_id, version
        ) TO {_get_csv_path('element').as_posix()!r}
        """)


def _write_note() -> None:
    with duckdb_connect() as conn:
        conn.sql(f"""
        COPY (
            SELECT
                id,
                point,
                created_at,
                updated_at,
                closed_at,
                hidden_at
            FROM read_parquet({NOTES_PARQUET_PATH.as_posix()!r})
            ORDER BY id
        ) TO {_get_csv_path('note').as_posix()!r}
        """)


def _write_note_comment() -> None:
    with duckdb_connect() as conn:
        conn.sql(f"""
        COPY (
            SELECT * EXCLUDE (display_name) FROM (
                SELECT
                    id AS note_id,
                    UNNEST(comments, max_depth := 2)
                FROM read_parquet({NOTES_PARQUET_PATH.as_posix()!r})
                ORDER BY id
            )
        ) TO {_get_csv_path('note_comment').as_posix()!r}
        """)


def _write_user(modes: set[str]) -> None:
    with duckdb_connect() as conn:
        sources = []

        if 'planet' in modes:
            sources.append(f"""
                SELECT DISTINCT ON (user_id)
                    user_id,
                    display_name
                FROM read_parquet({PLANET_PARQUET_PATH.as_posix()!r})
                WHERE user_id IS NOT NULL
            """)

        if 'notes' in modes:
            sources.append(f"""
                SELECT DISTINCT ON (user_id)
                    user_id,
                    display_name
                FROM (
                    SELECT UNNEST(comments, max_depth := 2)
                    FROM read_parquet({NOTES_PARQUET_PATH.as_posix()!r})
                )
                WHERE user_id IS NOT NULL
            """)

        conn.sql(f"""
        COPY (
            SELECT DISTINCT ON (user_id)
                user_id AS id,
                (user_id || '@localhost.invalid') AS email,
                TRUE as email_verified,
                IF(
                    COUNT(*) OVER (PARTITION BY display_name) > 1,
                    display_name || '_' || user_id,
                    display_name
                ) AS display_name,
                '' AS password_pb,
                'en' AS language,
                TRUE AS activity_tracking,
                TRUE AS crash_reporting,
                '127.0.0.1' AS created_ip
            FROM ({' UNION ALL '.join(sources)})
            ORDER BY user_id
        ) TO {_get_csv_path('user').as_posix()!r}
        """)


def main() -> None:
    # Freeze all gc objects before starting for improved performance
    gc.collect()
    gc.freeze()
    gc.disable()

    choices = ['planet', 'notes', 'user']
    parser = ArgumentParser()
    parser.add_argument('modes', nargs='*', choices=choices)
    args = parser.parse_args()
    modes = set(args.modes or choices)

    if 'planet' in modes:
        if not PLANET_INPUT_PATH.is_file():
            raise FileNotFoundError(f'Planet data file not found: {PLANET_INPUT_PATH}')

        run_planet_workers()
        merge_planet_worker_results()

        print('Writing changeset')
        _write_changeset()
        print('Writing element')
        _write_element()

    if 'notes' in modes:
        if not NOTES_INPUT_PATH.is_file():
            raise FileNotFoundError(f'Notes data file not found: {PLANET_INPUT_PATH}')

        run_notes_workers()
        merge_notes_worker_results()

        print('Writing note')
        _write_note()
        print('Writing note comment')
        _write_note_comment()

    if 'user' in modes:
        print('Writing user')
        _write_user(modes)

    print('Done! Done! Done!')


if __name__ == '__main__':
    main()
