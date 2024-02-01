import csv
import gc
import os
import pathlib
from datetime import datetime
from io import BytesIO
from itertools import batched
from multiprocessing import Pool
from typing import NamedTuple

import anyio
import lxml.etree as ET
import orjson
from tqdm import tqdm

from app.config import PRELOAD_DIR

input_path = pathlib.Path(PRELOAD_DIR / 'preload.osm')
if not input_path.is_file():
    raise FileNotFoundError(f'File not found: {input_path}')

output_user_path = pathlib.Path(PRELOAD_DIR / 'user.csv')
output_changeset_path = pathlib.Path(PRELOAD_DIR / 'changeset.csv')
output_element_path = pathlib.Path(PRELOAD_DIR / 'element.csv')

buffering = 8 * 1024 * 1024  # 8 MB
batch_size = 100_000

# freeze all gc objects before starting for improved performance
gc.collect()
gc.freeze()
gc.disable()


# fix xml syntax from random file seek
# chains header with the rest of the file
class WorkerInputStream(BytesIO):
    position = 0
    header = b''
    header_finished_pos = 0

    def __init__(self, file_stream: BytesIO, from_seek: int, to_seek: int):
        self.file_stream = file_stream
        self.file_stream_size = to_seek - from_seek

        if from_seek > 0:
            self.file_stream.seek(from_seek)
            self.header = b'<osm>\n'
            self.header_finished_pos = len(self.header)

    def read(self, read_size: int = -1) -> bytes:
        assert read_size >= 0

        max_read_size = self.header_finished_pos + self.file_stream_size - self.position
        read_size = min(read_size, max_read_size)
        if read_size == 0:
            return b''

        new_position = self.position + read_size

        if self.position < self.header_finished_pos:
            header_output = self.header[self.position : new_position]
            file_output = self.file_stream.read(read_size - len(header_output))
            self.position = new_position
            return header_output + file_output

        file_output = self.file_stream.read(read_size)
        self.position = new_position
        return file_output

    def seek(self, position: int, whence: int = 0) -> int:
        raise NotImplementedError

    def tell(self) -> int:
        return self.position


class WorkerResult(NamedTuple):
    user_ids: set[int]
    changeset_ids: set[tuple[int, int]]


def element_worker(
    i: int,
    from_seek: int,  # inclusive
    to_seek: int,  # exclusive
) -> WorkerResult:
    user_ids: set[int] = set()
    changeset_ids: set[tuple[int, int]] = set()
    result = WorkerResult(user_ids, changeset_ids)

    worker_output_path = output_element_path.with_suffix(f'.csv.{i}')

    with input_path.open('rb') as f_in, worker_output_path.open('w', buffering=buffering, newline='') as f_out:
        f_in = WorkerInputStream(f_in, from_seek, to_seek)

        context = ET.iterparse(f_in, recover=True)
        elem: ET.ElementBase
        writer = csv.writer(f_out)

        # only write header for the first file
        if i == 0:
            writer.writerow(
                (
                    'user_id',
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

        rows = []
        temp_tags = {}
        temp_members = []

        for batch in batched(context, batch_size):
            for _, elem in batch:
                if elem.tag == 'tag':
                    temp_tags[elem.attrib['k']] = elem.attrib['v']
                elif elem.tag == 'nd':
                    temp_members.append(
                        {
                            'type': 'way',
                            'id': elem.attrib['ref'],
                            'role': '',
                        }
                    )
                elif elem.tag == 'member':
                    temp_members.append(
                        {
                            'type': elem.attrib['type'],
                            'id': elem.attrib['ref'],
                            'role': elem.attrib['role'],
                        }
                    )
                elif elem.tag in ('node', 'way', 'relation'):
                    if (
                        elem.tag == 'node'
                        and (lon := elem.attrib.get('lon')) is not None
                        and (lat := elem.attrib.get('lat')) is not None
                    ):
                        point = f'POINT ({lon} {lat})'
                    else:
                        point = None

                    user_id = int(uid) if (uid := elem.attrib.get('uid')) is not None else None
                    user_ids.add(user_id)
                    changeset_id = int(elem.attrib['changeset'])
                    changeset_ids.add((user_id, changeset_id))

                    rows.append(
                        (
                            user_id,  # user_id
                            changeset_id,  # changeset_id
                            elem.tag,  # type
                            elem.attrib['id'],  # id
                            elem.attrib['version'],  # version
                            elem.attrib.get('visible', 'true') == 'true',  # visible
                            orjson.dumps(temp_tags).decode(),  # tags
                            point,  # point
                            orjson.dumps(temp_members).decode(),  # members
                            datetime.fromisoformat(elem.attrib['timestamp']),  # created_at
                        )
                    )

                    temp_tags.clear()
                    temp_members.clear()

                elem.clear()

            writer.writerows(rows)
            rows.clear()
            gc.collect()

    return result


async def main():
    user_ids: set[int] = set()
    changeset_ids: set[tuple[int, int]] = set()

    nthreads = os.cpu_count()
    print(f'Configuring {nthreads} workers')

    from_seek_search = (b'  <node', b'  <way', b'  <relation')
    input_size = input_path.stat().st_size
    seek_one = input_size // nthreads
    from_seeks = []

    with input_path.open('rb') as f_in:
        for i in range(nthreads):
            from_seek = seek_one * i

            if i > 0:
                f_in.seek(from_seek)
                lookahead = f_in.read(1024 * 1024)
                min_find = float('inf')

                for search in from_seek_search:
                    if (found := lookahead.find(search)) > -1:
                        min_find = min(min_find, found)

                assert min_find != float('inf')
                from_seek += min_find

            from_seeks.append(from_seek)

    args = []
    for i in range(nthreads):
        from_seek = from_seeks[i]
        to_seek = from_seeks[i + 1] if i + 1 < nthreads else input_size

        args.append((i, from_seek, to_seek))
        print(f'  Worker {i}: {from_seek} - {to_seek}')

    print('Batch size:', batch_size)
    print('🚀 Preparing element data...')
    with Pool(nthreads) as pool:
        for result in pool.starmap(element_worker, args):
            user_ids.update(result.user_ids)
            changeset_ids.update(result.changeset_ids)

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
                'languages',
            )
        )

        user_ids.discard(None)
        for user_id in tqdm(user_ids, desc='Preparing user data'):
            user_writer.writerow(
                (
                    user_id,  # id
                    f'{user_id}@localhost.invalid',  # email
                    f'user_{user_id}',  # display_name
                    'x',  # password_hashed
                    '127.0.0.1',  # created_ip
                    'active',  # status
                    None,  # auth_provider
                    None,  # auth_uid
                    '{"en"}',  # languages
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

        for user_id, changeset_id in tqdm(changeset_ids, desc='Preparing changeset data'):
            changeset_writer.writerow(
                (
                    changeset_id,  # id
                    user_id,  # user_id
                    '{}',  # tags
                )
            )


if __name__ == '__main__':
    anyio.run(main, backend_options={'use_uvloop': True})
