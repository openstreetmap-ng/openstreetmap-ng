from collections.abc import Sequence

from sqlalchemy import func, select

from app.db import db
from app.lib.auth_context import auth_scopes, auth_user, auth_user_scopes
from app.lib.exceptions_context import raise_for
from app.lib.statement_context import apply_statement_context
from app.lib.trace_file import TraceFile
from app.models.db.trace_ import Trace
from app.storage import TRACES_STORAGE


class TraceRepository:
    @staticmethod
    async def get_one_by_id(trace_id: int) -> Trace:
        """
        Get a trace by id.

        Raises if the trace is not visible to the current user.
        """
        async with db() as session:
            stmt = select(Trace).where(Trace.id == trace_id)
            stmt = apply_statement_context(stmt)
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
        trace = await TraceRepository.get_one_by_id(trace_id)
        file_buffer = await TRACES_STORAGE.load(trace.file_id)
        file_bytes = TraceFile.decompress_if_needed(file_buffer, trace.file_id)
        return file_bytes

    @staticmethod
    async def find_many_by_user_id(
        user_id: int,
        *,
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
            stmt = apply_statement_context(stmt)

            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()

    @staticmethod
    async def count_by_user_id(user_id: int) -> int:
        """
        Count traces by user id.
        """
        async with db() as session:
            stmt = select(func.count()).select_from(select(Trace).where(Trace.user_id == user_id))

            return await session.scalar(stmt)

    @staticmethod
    async def find_many_recent(
        *,
        personal: bool,
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
            stmt = apply_statement_context(stmt)

            where_and = []

            if personal:
                where_and.append(Trace.user_id == auth_user().id)
            else:
                where_and.append(Trace.visible_to(None, auth_scopes()))

            if tag is not None:
                where_and.append(Trace.tags.any(tag))

            if after is not None:
                where_and.append(Trace.id > after)
            if before is not None:
                where_and.append(Trace.id < before)

            stmt = stmt.where(*where_and)

            if (after is None) or (before is not None):
                stmt = stmt.order_by(Trace.id.desc())
                reverse = False
            else:
                stmt = stmt.order_by(Trace.id.asc())
                reverse = True

            stmt = stmt.limit(limit)
            result = (await session.scalars(stmt)).all()
            if reverse:
                result.reverse()
            return result
