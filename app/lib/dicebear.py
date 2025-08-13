import logging
import re
from asyncio import create_subprocess_exec
from asyncio.subprocess import PIPE
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from pydantic import SecretStr

from app.config import DYNAMIC_AVATAR_CACHE_EXPIRE
from app.lib.crypto import hash_storage_key
from app.models.types import StorageKey
from app.services.cache_service import CacheContext, CacheService

_DicebearStyle = Literal['identicon', 'initials', 'shapes']

_CTX = CacheContext('Dicebear')
_WORD_BOUNDARY_RE = re.compile(r'[\s\-_.,;:!?@/\\()\[\]{}0-9]+')
_CAMEL_CASE_RE = re.compile(r'(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])')


async def generate_avatar(style: _DicebearStyle, text: str | SecretStr, /) -> bytes:
    """Generate a random avatar using dicebear."""
    cache_key = hash_storage_key(
        f'{style}/{text.get_secret_value() if isinstance(text, SecretStr) else text}',
        '.svg',
    )

    async def factory() -> bytes:
        return await _generate_avatar_impl(style, text, cache_key)

    return await CacheService.get(
        cache_key, _CTX, factory, ttl=DYNAMIC_AVATAR_CACHE_EXPIRE
    )


async def _generate_avatar_impl(
    style: _DicebearStyle, text: str | SecretStr, cache_key: StorageKey, /
) -> bytes:
    with TemporaryDirectory(prefix='osm-ng-dicebear-') as tmpdir:
        if style == 'initials':
            assert not isinstance(text, SecretStr), (
                'initials style must not be used with SecretStr'
            )
            initials = _extract_initials(text)
            seed = f'{initials[0]}/{cache_key}/{initials[1]}'
        else:
            seed = cache_key

        proc = await create_subprocess_exec(
            'dicebear',
            style,
            tmpdir,
            '--seed',
            seed,
            stdout=PIPE,
            stderr=PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode:
            raise RuntimeError(f'Dicebear failed: {stderr.decode()}')

        data = Path(tmpdir, f'{style}-0.svg').read_bytes()
        logging.debug('Dicebear avatar generated successfully: style=%r', style)
        return data


def _extract_initials(text: str) -> str:
    """
    Extract initials from text.

    Rules:
    1. Split by word boundaries (spaces, hyphens, underscores, etc.)
    2. If no word boundaries, check for camelCase
    3. Take first alphabetic character from each part (ignoring numbers)
    4. If no boundaries found, take first 2 alphabetic characters
    5. Always return exactly 2 uppercase characters
    6. If only 1 character extracted, double it
    """
    if not text:
        return 'XX'

    # First, try to split by word boundaries
    parts: list[str] = [p for p in _WORD_BOUNDARY_RE.split(text) if p]
    part: str
    char: str

    initials: list[str] = []

    if len(parts) >= 2:
        # Multiple parts found - take first alphabetic from each
        for part in parts:
            if len(initials) >= 2:
                break
            for char in part:
                if char.isalpha():
                    initials.append(char)
                    break
    elif parts:
        # Single part - check for camelCase
        part = parts[0]
        camel_parts: list[str] = _CAMEL_CASE_RE.split(part)

        if len(camel_parts) >= 2:
            # CamelCase detected - take first alpha from each part
            for part in camel_parts:
                if len(initials) >= 2:
                    break
                for char in part:
                    if char.isalpha():
                        initials.append(char)
                        break
        else:
            # No boundaries - take first 2 alphabetic chars
            for char in part:
                if char.isalpha():
                    initials.append(char)
                    if len(initials) >= 2:
                        break
    else:
        # No parts after splitting - process original text
        for char in text:
            if char.isalpha():
                initials.append(char)
                if len(initials) >= 2:
                    break

    if not initials:
        return 'XX'

    return (
        initials[0] + initials[1]  #
        if len(initials) >= 2
        else initials[0] + initials[0]
    ).upper()
