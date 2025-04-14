from typing import override

from psycopg import postgres
from psycopg._encodings import conn_encoding
from psycopg.abc import AdaptContext
from psycopg.adapt import Buffer, Loader
from psycopg.pq import Format
from psycopg.types.enum import EnumInfo


def register_string_enum(info: EnumInfo, context: AdaptContext | None = None) -> None:
    """Register the adapters to load an enum type as strings."""
    adapters = context.adapters if context is not None else postgres.adapters
    info.register(context)

    load_map = _make_string_load_map(info, context)

    loader = _make_string_loader(info.name, load_map)
    adapters.register_loader(info.oid, loader)

    loader = _make_string_binary_loader(info.name, load_map)
    adapters.register_loader(info.oid, loader)


class _StringEnumLoader(Loader):
    _load_map: dict[bytes, str]

    @override
    def load(self, data: Buffer) -> str:
        return self._load_map[bytes(data)]


def _make_string_load_map(
    info: EnumInfo, context: AdaptContext | None
) -> dict[bytes, str]:
    encoding = conn_encoding(context.connection if context is not None else None)
    return {label.encode(encoding): label for label in info.labels}


def _make_string_loader(
    name: str, load_map: dict[bytes, str]
) -> type[_StringEnumLoader]:
    attribs = {'_load_map': load_map}
    return type(f'{name.title()}StringLoader', (_StringEnumLoader,), attribs)


def _make_string_binary_loader(
    name: str, load_map: dict[bytes, str]
) -> type[_StringEnumLoader]:
    attribs = {'_load_map': load_map, 'format': Format.BINARY}
    return type(f'{name.title()}StringBinaryLoader', (_StringEnumLoader,), attribs)
