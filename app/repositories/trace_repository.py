from collections.abc import Sequence

from sqlalchemy import func, select

from app.db import db
from app.lib.auth_context import auth_user_scopes
from app.lib.exceptions_context import raise_for
from app.lib.joinedload_context import get_joinedload
from app.lib.trace_file import TraceFile
from app.limits import FIND_LIMIT
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
            trace = await session.get(Trace, trace_id, options=(get_joinedload(),))

        if not trace:
            raise_for().trace_not_found(trace_id)
        if not trace.visible_to(*auth_user_scopes()):
            raise_for().trace_access_denied(trace_id)

        return trace

    @staticmethod
    async def get_one_data_by_id(trace_id: int) -> tuple[str, bytes]:
        """
        Get a trace data file by id.

        Raises if the trace is not visible to the current user.

        Returns a tuple of (filename, file).
        """

        trace = await TraceRepository.get_one_by_id(trace_id)
        buffer = await TRACES_STORAGE.load(trace.file_id)
        file = await TraceFile.zstd_decompress_if_needed(buffer, trace.file_id)
        filename = trace.name
        return filename, file

    @staticmethod
    async def find_many_by_user_id(
        user_id: int,
        *,
        limit: int | None = FIND_LIMIT,
    ) -> Sequence[Trace]:
        """
        Find traces by user id.
        """

        async with db() as session:
            stmt = (
                select(Trace)
                .options(get_joinedload())
                .where(
                    Trace.user_id == user_id,
                    Trace.visible_to(*auth_user_scopes()),
                )
            )

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
                select(Trace).where(
                    Trace.user_id == user_id,
                )
            )

            return await session.scalar(stmt)
