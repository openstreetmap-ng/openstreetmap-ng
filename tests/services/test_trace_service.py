from asyncio import sleep
from pathlib import Path

from app.config import TRACE_FILE_COMPRESS_ZSTD_LEVEL_MAX
from app.db import db_fetchval
from app.lib.auth.context import auth_context
from app.lib.io.trace_file import TraceFile
from app.lib.storage import TRACE_STORAGE
from app.models.types import DisplayName, StorageKey
from app.queries.user_query import UserQuery
from app.services.trace_service import TraceService

_GPX_BYTES = Path('tests/data/8473730.gpx').read_bytes()


async def test_trace_background_recompression(client):
    user = await UserQuery.find_by_display_name(DisplayName('user1'))
    assert user is not None, 'Test user "user1" must exist'

    with auth_context(user):
        trace_id = await TraceService.upload(
            _GPX_BYTES,
            name='recompress.gpx',
            description='Background recompression test',
            tags=[],
            visibility='private',
        )

    # Reference for the heavily-compressed variant produced in the background
    heavy_ref = (
        await TraceFile.compress(_GPX_BYTES, level=TRACE_FILE_COMPRESS_ZSTD_LEVEL_MAX)
    ).data

    # The recompression runs as a background task; poll until it settles
    file_id: StorageKey | None = None
    data: bytes | None = None
    for _ in range(100):
        file_id = await db_fetchval(
            StorageKey, t'SELECT file_id FROM trace WHERE id = {trace_id}'
        )
        assert file_id is not None
        data = await TRACE_STORAGE.load(file_id)
        if len(data) == len(heavy_ref):
            break
        await sleep(0.05)

    assert data is not None and file_id is not None
    # The stored file is the heavily-compressed variant ...
    assert len(data) == len(heavy_ref)
    # ... and it still round-trips back to the original upload
    assert TraceFile.decompress_if_needed(data, file_id) == _GPX_BYTES
