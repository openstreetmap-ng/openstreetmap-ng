from db import DB
from lib.auth import auth_user
from lib.exceptions import raise_for
from models.db.trace_ import Trace


class TraceService:
    @staticmethod
    async def update(trace_id: int, new_trace: Trace) -> None:
        async with DB() as session:
            trace = await session.get(Trace, trace_id, with_for_update=True)

            if not trace:
                raise_for().trace_not_found(trace_id)
            if trace.user_id != auth_user().id:
                raise_for().trace_access_denied(trace_id)

            trace.name = new_trace.name
            trace.description = new_trace.description
            trace.visibility = new_trace.visibility
            trace.tags = new_trace.tags

    @staticmethod
    async def delete(trace_id: int) -> None:
        async with DB() as session:
            trace = await session.get(Trace, trace_id, with_for_update=True)

            if not trace:
                raise_for().trace_not_found(trace_id)
            if trace.user_id != auth_user().id:
                raise_for().trace_access_denied(trace_id)

            await session.delete(trace)
