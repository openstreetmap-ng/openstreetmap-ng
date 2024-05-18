from collections import namedtuple
from dataclasses import field, make_dataclass
from typing import Any

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
        ns = make_dataclass(
            self.name,
            (
                *labels,
                *(
                    (k, Any, field(default=v))  #
                    for k, v in self._extra_fields.items()
                ),
            ),
            repr=False,
            eq=False,
            match_args=False,
            slots=True,
        )

        def proc(row: Row):
            return ns(*row)

        return proc
