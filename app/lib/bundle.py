from collections import namedtuple
from types import SimpleNamespace

from sqlalchemy import Row
from sqlalchemy.orm import Bundle


class TupleBundle(Bundle):
    def create_row_processor(self, query, procs, labels):
        t = namedtuple('t', labels)  # noqa: PYI024

        def proc(row: Row):
            return t(*row)

        return proc


class NamespaceBundle(Bundle):
    def __init__(self, name: str, *exprs, extra_fields: dict, **kw):
        self._extra_fields = extra_fields
        super().__init__(name, *exprs, **kw)

    def create_row_processor(self, query, procs, labels):
        def proc(row: Row):
            return SimpleNamespace(**dict(zip(labels, row, strict=True)), **self._extra_fields)

        return proc
