from functools import cache
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
        if suffix == '.scss':
            lines.append(
                f'<link rel="stylesheet" href="http://127.0.0.1:49568/{path}">'
            )

        if suffix == '.ts':
            if path == 'app/views/test-site.ts':
                scss_path = 'app/views/main.scss'
            else:
                scss_path = path[:-3] + '.scss'

            lines.append(
                f'<link rel="stylesheet" href="http://127.0.0.1:49568/{scss_path}">'
            )

        lines.append(
            '<script src="http://127.0.0.1:49568/@vite/client" type="module"></script>'
        )

        if path == 'app/views/main.ts':
            lines.append(
                '<script src="http://127.0.0.1:49568/app/views/main-sync.ts"></script>'
            )

        if suffix == '.ts':
            lines.append(
                f'<script src="http://127.0.0.1:49568/{path}" type="module" defer></script>'
            )

    else:
        if suffix == '.scss':
            ts_path = path[:-5] + '.ts'
            data = _MANIFEST[ts_path]
        else:
            data = _MANIFEST[path]

        lines.extend(
            f'<link rel="stylesheet" href="/static/vite/{css}">'
            for css in data.get('css', ())
        )
        lines.extend(
            f'<link rel="stylesheet" href="/static/vite/{css}">'
            for chunk in data.get('imports', ())
            for css in _MANIFEST[chunk].get('css', ())
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
            for chunk in data.get('imports', ())
        )

    return ''.join(lines)
