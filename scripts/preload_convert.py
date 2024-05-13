import csv
import gc
import os
import pathlib
from datetime import datetime
from multiprocessing import Pool
from typing import NamedTuple

import anyio
import lxml.etree as ET
from tqdm import tqdm

from app.config import PRELOAD_DIR
from app.utils import JSON_ENCODE

input_path = pathlib.Path(PRELOAD_DIR / 'preload.osm')
if not input_path.is_file():
    raise FileNotFoundError(f'File not found: {input_path}')

output_user_path = pathlib.Path(PRELOAD_DIR / 'user.csv')
output_changeset_path = pathlib.Path(PRELOAD_DIR / 'changeset.csv')
output_element_path = pathlib.Path(PRELOAD_DIR / 'element.csv')

buffering = 32 * 1024 * 1024  # 32 MB
read_memory_limit = 2 * 1024 * 1024 * 1024  # 2 GB => ~50 GB total memory usage

# freeze all gc objects before starting for improved performance
gc.collect()
gc.freeze()
gc.disable()


class ElementSummary(NamedTuple):
    changeset_id: int
    user_id: int | None
    user_display_name: str | None
    timestamp: datetime


def get_output_worker_path(i: int) -> pathlib.Path:
    return output_element_path.with_suffix(f'.csv.{i}')


def element_worker(args: tuple[int, int, int]) -> list[ElementSummary]:
    i, from_seek, to_seek = args  # from_seek(inclusive), to_seek(exclusive)
    result: list[ElementSummary] = []

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

    rows = []

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

        uid = attrib.get('uid')
        if uid is not None:
            user_id = int(uid)
            user_display_name = attrib['user']
        else:
            user_id = None
            user_display_name = None

        changeset_id = int(attrib['changeset'])
        timestamp = datetime.fromisoformat(attrib['timestamp'])

        rows.append(
            (
                changeset_id,  # changeset_id
                tag,  # type
                attrib['id'],  # id
                attrib['version'],  # version
                attrib.get('visible', 'true') == 'true',  # visible
                JSON_ENCODE(tags).decode() if tags else '{}',  # tags
                point,  # point
                JSON_ENCODE(members).decode() if members else '[]',  # members
                timestamp,  # created_at
            )
        )

        result.append(
            ElementSummary(
                changeset_id,
                user_id,
                user_display_name,
                timestamp,
            )
        )

    with get_output_worker_path(i).open('w', buffering=buffering, newline='') as f_out:
        writer = csv.writer(f_out)

        # only write header for the first file
        if i == 0:
            writer.writerow(
                (
                    'changeset_id',
                    'type',
                    'id',
                    'version',
                    'visible',
                    'tags',
                    'point',
                    'members',
                    'created_at',
                )
            )

        writer.writerows(rows)

    gc.collect()
    return result


async def main():
    num_workers = os.cpu_count()

    input_size = input_path.stat().st_size
    task_read_memory_limit = read_memory_limit // num_workers
    num_tasks = input_size // task_read_memory_limit
    task_size = input_size // num_tasks

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

    user_name_map: dict[int, str] = {}
    changeset_user_map: dict[int, int | None] = {}

    with Pool(num_workers) as pool:
        for result_list in tqdm(
            pool.imap_unordered(element_worker, args),
            desc='Preparing element data',
            total=num_tasks,
        ):
            for result in result_list:
                user_id = result.user_id
                changeset_id = result.changeset_id

                if user_id is not None:
                    user_name_map[user_id] = result.user_display_name

                changeset_user_map[changeset_id] = user_id

    get_output_worker_path(0).rename(output_element_path)

    with output_element_path.open('ab', buffering=buffering) as f_out:
        for i in tqdm(range(1, num_tasks), desc='Merging outputs'):
            output_worker_path = get_output_worker_path(i)

            with output_worker_path.open('rb') as f_in:
                while buffer := f_in.read(buffering):
                    f_out.write(buffer)

            output_worker_path.unlink()

    with output_user_path.open('w', buffering=buffering, newline='') as f_user:
        user_writer = csv.writer(f_user)
        user_writer.writerow(
            (
                'id',
                'email',
                'display_name',
                'password_hashed',
                'created_ip',
                'status',
                'auth_provider',
                'auth_uid',
                'language',
                'activity_tracking',
                'crash_reporting',
            )
        )

        for user_id, display_name in tqdm(user_name_map.items(), desc='Preparing user data'):
            user_writer.writerow(
                (
                    user_id,  # id
                    f'{user_id}@localhost.invalid',  # email
                    display_name,  # display_name
                    'x',  # password_hashed
                    '127.0.0.1',  # created_ip
                    'active',  # status
                    None,  # auth_provider
                    None,  # auth_uid
                    'en',  # language
                    1,  # activity_tracking
                    1,  # crash_reporting
                )
            )

    with output_changeset_path.open('w', buffering=buffering, newline='') as f_changeset:
        changeset_writer = csv.writer(f_changeset)
        changeset_writer.writerow(
            (
                'id',
                'user_id',
                'tags',
            )
        )

        for changeset_id, user_id in tqdm(changeset_user_map.items(), desc='Preparing changeset data'):
            changeset_writer.writerow(
                (
                    changeset_id,  # id
                    user_id,  # user_id
                    '{}',  # tags
                )
            )


if __name__ == '__main__':
    anyio.run(main)
