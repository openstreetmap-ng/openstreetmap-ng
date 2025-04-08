import logging
from asyncio import TaskGroup, sleep
from collections.abc import Callable
from inspect import Parameter, signature
from operator import itemgetter
from typing import Any, NamedTuple

from psycopg.rows import dict_row

from app.config import ADMIN_TASK_HEARTBEAT_INTERVAL, ADMIN_TASK_TIMEOUT
from app.db import db
from app.lib.date_utils import utcnow


class TaskArgument(NamedTuple):
    type: str
    required: bool
    default: str


class TaskDefinition(NamedTuple):
    id: str
    arguments: dict[str, TaskArgument]
    func: Callable


class TaskInfo(NamedTuple):
    id: str
    arguments: dict[str, TaskArgument]
    running: bool


_REGISTRY: dict[str, TaskDefinition] = {}


def register_admin_task(func: Callable):
    """Decorator to register a method as a manageable task."""
    task_id = func.__name__
    if task_id in _REGISTRY:
        raise ValueError(f'Task with {task_id=!r} is already registered')

    sig = signature(func)
    arguments: dict[str, TaskArgument] = {}

    for name, param in sig.parameters.items():
        annotation = param.annotation
        default = param.default
        arguments[name] = TaskArgument(
            type=annotation.__name__ if annotation is not Parameter.empty else 'Any',
            required=default is Parameter.empty,
            default=str(default) if default is not Parameter.empty else '',
        )

    _REGISTRY[task_id] = TaskDefinition(
        id=task_id,
        arguments=arguments,
        func=func,
    )
    logging.info('Registered task %r', task_id)
    return func


class AdminTaskService:
    @staticmethod
    async def list_tasks() -> list[TaskInfo]:
        """List all registered tasks and their current status."""
        if not _REGISTRY:
            return []

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM admin_task
                WHERE id = ANY(%s)
                """,
                (list(_REGISTRY),),
            ) as r,
        ):
            rows = {row['id']: row for row in await r.fetchall()}

        timeout_at = utcnow() - ADMIN_TASK_TIMEOUT
        result: list[TaskInfo] = [
            TaskInfo(
                id=definition.id,
                running=(row := rows.get(id)) is not None and timeout_at < row['heartbeat_at'],
                arguments=definition.arguments,
            )
            for id, definition in _REGISTRY.items()
        ]

        # Sort for consistent ordering
        result.sort(key=itemgetter('id'))
        return result

    @staticmethod
    async def start_task(task_id: str, args: dict[str, Any]) -> None:
        definition = _REGISTRY.get(task_id)
        if definition is None:
            raise ValueError(f'Task with {task_id=!r} not found')

        bound_args = signature(definition.func).bind(**args)
        bound_args.apply_defaults()
        validated_args = bound_args.arguments

        timeout_at = utcnow() - ADMIN_TASK_TIMEOUT

        async with db(True, autocommit=True) as conn, conn.pipeline():
            # Delete timed out tasks
            await conn.execute(
                """
                DELETE FROM admin_task
                WHERE heartbeat_at <= %s
                """,
                (timeout_at,),
            )

            # Register the task
            await conn.execute(
                """
                INSERT INTO admin_task (id)
                VALUES (%s)
                """,
                (task_id,),
            )

        # Start the task and manage its lifecycle
        await _run_task(definition, validated_args)


async def _run_task(definition: TaskDefinition, args: dict[str, Any]) -> None:
    task_id = definition.id
    logging.info('Task %r started with args: %s', task_id, args)

    async with TaskGroup() as tg:
        heartbeat_task = tg.create_task(_heartbeat_loop(task_id))

        try:
            await definition.func(**args)
        finally:
            heartbeat_task.cancel()

            # Delete the task when finished
            async with db(write=True, autocommit=True) as conn:
                await conn.execute(
                    """
                    DELETE FROM admin_task
                    WHERE id = %s
                    """,
                    (task_id,),
                )

        logging.info('Task %r finished successfully', task_id)


async def _heartbeat_loop(task_id: str) -> None:
    while True:
        # Periodically update the heartbeat field
        await sleep(ADMIN_TASK_HEARTBEAT_INTERVAL.total_seconds())

        async with db(write=True, autocommit=True) as conn:
            await conn.execute(
                """
                UPDATE admin_task
                SET heartbeat_at = DEFAULT
                WHERE id = %s
                """,
                (task_id,),
            )

        logging.debug('Task %r heartbeat sent', task_id)
