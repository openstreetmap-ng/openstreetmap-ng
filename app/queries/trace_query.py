from collections.abc import Sequence
from typing import Literal

from sqlalchemy import any_, func, select, text

from app.db import db
from app.lib.auth_context import auth_scopes, auth_user_scopes
from app.lib.exceptions_context import raise_for
from app.lib.options_context import apply_options_context
from app.lib.trace_file import TraceFile
from app.models.db.trace_ import Trace
from app.storage import TRACES_STORAGE


class TraceQuery:
    @staticmethod
    async def get_one_by_id(trace_id: int) -> Trace:
        """
        Get a trace by id.

        Raises if the trace is not visible to the current user.
        """
        async with db() as session:
            stmt = select(Trace).where(Trace.id == trace_id)
            stmt = apply_options_context(stmt)
            trace = await session.scalar(stmt)

        if trace is None:
            raise_for().trace_not_found(trace_id)
        if not trace.visible_to(*auth_user_scopes()):
            raise_for().trace_access_denied(trace_id)

        return trace

    @staticmethod
    async def get_one_data_by_id(trace_id: int) -> bytes:
        """
        Get a trace data file by id.

        Raises if the trace is not visible to the current user.

        Returns a tuple of (filename, file).
        """
        trace = await TraceQuery.get_one_by_id(trace_id)
        file_buffer = await TRACES_STORAGE.load(trace.file_id)
        file_bytes = TraceFile.decompress_if_needed(file_buffer, trace.file_id)
        return file_bytes

    @staticmethod
    async def find_many_by_user_id(
        user_id: int,
        *,
        sort: Literal['asc', 'desc'] = 'desc',
        limit: int | None,
    ) -> Sequence[Trace]:
        """
        Find traces by user id.
        """
        async with db() as session:
            stmt = select(Trace).where(
                Trace.user_id == user_id,
                Trace.visible_to(*auth_user_scopes()),
            )
            stmt = apply_options_context(stmt)
            stmt = stmt.order_by(Trace.id.asc() if (sort == 'asc') else Trace.id.desc())

            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()

    @staticmethod
    async def count_by_user_id(user_id: int) -> int:
        """
        Count traces by user id.
        """
        async with db() as session:
            stmt = select(func.count()).select_from(
                select(text('1'))
                .where(
                    Trace.user_id == user_id,
                    Trace.visible_to(*auth_user_scopes()),
                )
                .subquery()
            )
            return (await session.execute(stmt)).scalar_one()

    @staticmethod
    async def find_many_recent(
        *,
        user_id: int | None = None,
        tag: str | None = None,
        after: int | None = None,
        before: int | None = None,
        limit: int,
    ) -> Sequence[Trace]:
        """
        Find recent traces.
        """
        async with db() as session:
            stmt = select(Trace)
            where_and = []

            if user_id is not None:
                where_and.append(Trace.user_id == user_id)
            else:
                where_and.append(Trace.visible_to(None, auth_scopes()))

            if tag is not None:
                where_and.append(any_(Trace.tags) == tag)

            if after is not None:
                where_and.append(Trace.id > after)
            if before is not None:
                where_and.append(Trace.id < before)

            stmt = stmt.where(*where_and)
            order_desc = (after is None) or (before is not None)
            stmt = stmt.order_by(Trace.id.desc() if order_desc else Trace.id.asc()).limit(limit)

            stmt = apply_options_context(stmt)
            rows = (await session.scalars(stmt)).all()
            return rows if order_desc else rows[::-1]
