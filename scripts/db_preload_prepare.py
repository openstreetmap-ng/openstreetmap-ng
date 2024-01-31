import csv
import gc
import pathlib
from datetime import datetime
from itertools import batched, islice

import anyio
import lxml.etree as ET
import orjson
from shapely import Point
from tqdm import tqdm

from app.config import PRELOAD_DIR
from app.models.element_member import ElementMemberRef
from app.models.element_type import ElementType


async def main():
    # freeze all gc objects before starting for improved performance
    gc.collect()
    gc.freeze()
    gc.disable()

    input_path = pathlib.Path(PRELOAD_DIR / 'preload.osm')
    if not input_path.is_file():
        raise FileNotFoundError(f'File not found: {input_path}')

    output_user_path = pathlib.Path(PRELOAD_DIR / 'user.csv')
    output_changeset_path = pathlib.Path(PRELOAD_DIR / 'changeset.csv')
    output_element_path = pathlib.Path(PRELOAD_DIR / 'element.csv')

    buffering = 2 * 1024 * 1024  # 2 MB
    batch_size = 100_000
    print('Batch size:', batch_size)

    user_ids: set[int] = set()
    changeset_ids: set[tuple[int, int]] = set()

    with input_path.open('rb') as f_in, output_element_path.open('w', buffering=buffering, newline='') as f_element:
        context = ET.iterparse(f_in)
        elem: ET.ElementBase

        element_writer = csv.writer(f_element)
        element_writer.writerow(
            (
                'user_id',
                'changeset_id',
                'type',
                'typed_id',
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

        for batch in tqdm(islice(batched(context, batch_size), 50), desc='Preparing element data'):
            for _, elem in batch:
                if elem.tag == 'tag':
                    temp_tags[elem.attrib['k']] = elem.attrib['v']
                elif elem.tag == 'nd':
                    temp_members.append(
                        ElementMemberRef(
                            type=ElementType.way,
                            typed_id=int(elem.attrib['ref']),
                            role='',
                        )
                    )
                elif elem.tag == 'member':
                    temp_members.append(
                        ElementMemberRef(
                            type=ElementType.from_str(elem.attrib['type']),
                            typed_id=int(elem.attrib['ref']),
                            role=elem.attrib['role'],
                        )
                    )
                elif elem.tag in ('node', 'way', 'relation'):
                    if (
                        elem.tag == 'node'
                        and (lon := elem.attrib.get('lon')) is not None
                        and (lat := elem.attrib.get('lat')) is not None
                    ):
                        point = Point(float(lon), float(lat))
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
                            elem.attrib['id'],  # typed_id
                            elem.attrib['version'],  # version
                            elem.attrib.get('visible', 'true') == 'true',  # visible
                            orjson.dumps(temp_tags).decode(),  # tags
                            point.wkt if point is not None else None,  # point
                            orjson.dumps(temp_members).decode(),  # members
                            datetime.fromisoformat(elem.attrib['timestamp']),  # created_at
                        )
                    )

                    temp_tags.clear()
                    temp_members.clear()

                elem.clear()

            element_writer.writerows(rows)
            rows.clear()
            gc.collect()

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
                    f'user{user_id}',  # display_name
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
