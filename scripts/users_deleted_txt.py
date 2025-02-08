import asyncio
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.config import PLANET_DIR, SENTRY_USERS_DELETED_TXT_MONITOR
from app.queries.user_query import UserQuery

_BUFFER_SIZE = 32 * 1024 * 1024  # 32 MB
_BATCH_SIZE = 100_000

_USERS_DELETED_DIR = PLANET_DIR / 'users_deleted'
_USERS_DELETED_DIR.mkdir(parents=True, exist_ok=True)
_USERS_DELETED_TXT = _USERS_DELETED_DIR / 'users_deleted.txt'


async def main():
    with (
        SENTRY_USERS_DELETED_TXT_MONITOR,
        NamedTemporaryFile(
            'x',
            buffering=_BUFFER_SIZE,
            encoding='ascii',
            prefix='.users_deleted',
            suffix='.txt.tmp',
            dir=_USERS_DELETED_DIR,
            delete=False,
        ) as f,
    ):
        f.write('# user IDs of deleted users.\n')
        after: int = 0
        while True:
            ids = await UserQuery.get_deleted_ids(after=after, sort='asc', limit=_BATCH_SIZE)
            if not ids:
                break
            f.writelines(f'{id}\n' for id in ids)
            new_after = ids[-1]
            print(f'Saved range: {after + 1} - {new_after}')
            after = new_after

        print('Flushing and renaming')
    Path(f.name).rename(_USERS_DELETED_TXT)


if __name__ == '__main__':
    asyncio.run(main())
