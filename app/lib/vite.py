from collections import deque
from fnmatch import fnmatchcase
from functools import cache
from itertools import chain
from pathlib import Path
from typing import Any

import orjson

from app.config import ENV

_MANIFEST: dict[str, dict[str, Any]] | None = (
    orjson.loads(Path('app/static/vite/.vite/manifest.json').read_bytes())
    if ENV != 'dev'
    else None
)


@cache
def vite_render_asset(path: str) -> str:
    suffix = Path(path).suffix
    lines: list[str] = []

    if _MANIFEST is None:
        # Development environment:
        # Use Vite dev server
        base = 'http://127.0.0.1:49568/static/vite/'

        if suffix == '.scss':
            lines.append(f'<link rel="stylesheet" href="{base}{path}">')

        if suffix == '.ts':
            if path == 'app/views/test-site.ts':
                scss_path = 'app/views/main.scss'
            else:
                scss_path = path[:-3] + '.scss'

            lines.append(f'<link rel="stylesheet" href="{base}{scss_path}">')

        lines.append(f'<script src="{base}@vite/client" type="module"></script>')

        if path == 'app/views/main.ts':
            lines.append(f'<script src="{base}app/views/main-sync.ts"></script>')

        if suffix == '.ts':
            lines.append(f'<script src="{base}{path}" type="module" defer></script>')

    else:
        # Production and test environments:
        # Use built assets
        imports: dict[str, dict[str, Any]] = {}

        if suffix == '.scss':
            ts_path = path[:-5] + '.ts'
            data = _MANIFEST[ts_path]
        else:
            data = _MANIFEST[path]

            # Recursively collect all imports
            stack = deque[str](data.get('imports', ()))
            while stack:
                chunk = stack.popleft()
                chunk_data = imports[chunk] = _MANIFEST[chunk]
                stack.extend(chunk_data.get('imports', ()))

        lines.extend(
            f'<link rel="stylesheet" href="/static/vite/{css}">'
            for chunk in chain((data,), imports.values())
            for css in chunk.get('css', ())
        )

        if path == 'app/views/main.ts':
            lines.append(
                f'<script src="/static/vite/{_MANIFEST["app/views/main-sync.ts"]["file"]}"></script>'
            )

        if suffix == '.ts':
            lines.append(
                f'<script src="/static/vite/{data["file"]}" type="module" defer></script>'
            )
            lines.extend(
                f'<link rel="modulepreload" href="/static/vite/{chunk["file"]}">'
                for chunk in imports.values()
            )

        lines.extend(
            f'<link rel="preload" href="/static/vite/{asset}?" as="font" type="font/woff2" crossorigin>'
            for chunk in chain((data,), imports.values())
            for asset in chunk.get('assets', ())
            if fnmatchcase(asset, 'assets/bootstrap-icons.*.woff2')
        )

    return ''.join(lines)
