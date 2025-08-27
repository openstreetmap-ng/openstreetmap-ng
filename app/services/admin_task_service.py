import logging
from asyncio import TaskGroup, sleep
from collections.abc import Callable
from contextlib import asynccontextmanager
from functools import cache
from inspect import Parameter, _empty, signature
from operator import itemgetter
from types import NoneType, UnionType
from typing import (
    Any,
    ForwardRef,
    NewType,
    TypedDict,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from psycopg.rows import dict_row
from pydantic import BaseModel, create_model

from app.config import ADMIN_TASK_HEARTBEAT_INTERVAL, ADMIN_TASK_TIMEOUT, ENV
from app.db import db
from app.lib.date_utils import utcnow
from app.services.audit_service import audit

TaskId = NewType('TaskId', str)


class TaskArgument(TypedDict):
    type: str
    required: bool
    default: str
    numeric: bool


class TaskDefinition(TypedDict):
    id: TaskId
    arguments: dict[str, TaskArgument]
    func: Callable


class TaskInfo(TypedDict):
    id: TaskId
    arguments: dict[str, TaskArgument]
    running: bool


_REGISTRY: dict[TaskId, TaskDefinition] = {}
_TG: TaskGroup


def register_admin_task(func: Callable):
    """Decorator to register a method as a manageable task."""
    task_id: TaskId = func.__name__  # type: ignore
    if task_id in _REGISTRY:
        raise ValueError(f'Task with {task_id=!r} is already registered')

    sig = signature(func)
    arguments: dict[str, TaskArgument] = {}

    for name, param in sig.parameters.items():
        default = param.default
        arguments[name] = {
            'type': _format_annotation(param.annotation),
            'required': default is Parameter.empty,
            'default': str(default) if default is not Parameter.empty else '',
            'numeric': _is_numeric(param.annotation),
        }

    _REGISTRY[task_id] = {
        'id': task_id,
        'arguments': arguments,
        'func': func,
    }
    logging.debug('Registered admin task %r', task_id)
    return func


class AdminTaskService:
    @asynccontextmanager
    @staticmethod
    async def context():
        global _TG
        async with (_TG := TaskGroup()):  # pyright: ignore[reportConstantRedefinition]
            yield
            for t in _TG._tasks:  # noqa: SLF001
                t.cancel()

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
            {
                'id': definition['id'],
                'arguments': definition['arguments'],
                'running': (
                    (row := rows.get(id)) is not None
                    and timeout_at < row['heartbeat_at']
                ),
            }
            for id, definition in _REGISTRY.items()
        ]

        # Sort for consistent ordering
        result.sort(key=itemgetter('id'))
        return result

    @staticmethod
    def start_task(task_id: TaskId, args: dict[str, str]) -> None:
        definition = _REGISTRY.get(task_id)
        if definition is None:
            raise ValueError(f'Task with {task_id=!r} not found')

        # Validate and convert arguments
        validated_args = _func_args_model(definition['func'])(**args).model_dump()

        _TG.create_task(_start_task(definition, validated_args))
        audit('admin_task', extra=f'{task_id}{validated_args}')


async def _start_task(definition: TaskDefinition, args: dict[str, Any]) -> None:
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
            (definition['id'],),
        )

    # Start the task and manage its lifecycle
    await _run_task(definition, args)


@cache
def _func_args_model(func: Callable) -> type[BaseModel]:
    type_hints = get_type_hints(func)
    fields: dict[str, tuple[type, Any]] = {
        name: (
            type_hints.get(name, Any),
            (... if (default := param.default) is Parameter.empty else default),
        )
        for name, param in signature(func).parameters.items()
    }

    return create_model(
        f'{func.__qualname__}_DynamicArgs',
        **fields,  # type: ignore
    )


async def _run_task(definition: TaskDefinition, args: dict[str, Any]) -> None:
    task_id = definition['id']
    logging.info('Task %r started with args: %s', task_id, args)

    async with TaskGroup() as tg:
        heartbeat_task = tg.create_task(_heartbeat_loop(task_id))

        try:
            if ENV != 'test':
                await definition['func'](**args)
            else:
                logging.warning('Skipped running task %r in test environment', task_id)
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


async def _heartbeat_loop(task_id: TaskId) -> None:
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


def _format_annotation(annotation: Any) -> str:
    # Simple cases
    if annotation is _empty:  # missing
        return 'Any'
    if annotation is None:  # None
        return 'None'
    if isinstance(annotation, str):  # string annotations
        return annotation
    if isinstance(annotation, ForwardRef):  # forward references
        return annotation.__forward_arg__
    if isinstance(annotation, type):  # direct types
        return annotation.__name__

    # Unpack origin and args
    origin = get_origin(annotation)
    args = [_format_annotation(arg) for arg in get_args(annotation)]

    # Union types
    if origin in {Union, UnionType}:
        return ' | '.join(args)

    # Generic types (e.g., list[int], dict[str, float])
    name = getattr(origin, '__name__', None) or str(annotation).removeprefix('typing.')
    return f'{name}[{", ".join(args)}]' if args else name


def _is_numeric(annotation: Any) -> bool:
    # Simple cases
    if annotation is _empty:  # missing
        return False
    if annotation is None:  # None
        return True
    if isinstance(annotation, str):  # string annotations
        return annotation in {'int', 'float', 'None'}
    if isinstance(annotation, ForwardRef):  # forward references
        return _is_numeric(annotation.__forward_arg__)
    if isinstance(annotation, type):  # direct types
        return annotation in {int, float, NoneType}

    # Unpack origin and args
    origin = get_origin(annotation)
    args = get_args(annotation)

    # Union types
    if origin in {Union, UnionType}:
        return all(_is_numeric(arg) for arg in args)

    # Generic types
    return False
