import logging
from abc import ABC
from collections import defaultdict
from typing import Sequence

import anyio
from motor.core import AgnosticClientSession

from db.transaction import Transaction, retry_transaction
from lib.exceptions import raise_for
from lib.optimistic.exceptions import OptimisticException
from lib.optimistic.prepare import OptimisticPrepare
from models.db.base_sequential import SequentialId
from models.db.changeset import Changeset
from models.db.element import Element
from models.db.element_node import ElementNode
from models.db.element_relation import ElementRelation
from models.db.element_way import ElementWay
from models.db.lock import lock
from models.element_type import ElementType
from models.typed_element_ref import TypedElementRef
from utils import utcnow

_LOCK_TTL = 30

# TODO 0.7 don't reuse placeholder ids for simplicity
# TODO reduce the number of db queries


class OptimisticApply(ABC):
    @retry_transaction()
    @staticmethod
    async def apply(prepare: OptimisticPrepare) -> dict[TypedElementRef, Sequence[Element]]:
        # clone elements for processing
        # this is done early to reduce the lock time
        elements = tuple(e.model_copy(deep=True) for e in prepare.elements)
        old_ref_elements_map: dict[TypedElementRef, Sequence[Element]] = None

        async with (
            anyio.create_task_group() as tg,
            lock(OptimisticApply.__class__.__qualname__, ttl=_LOCK_TTL),
            Transaction() as session,
        ):
            for typed_ref, elements in prepare.state.items():
                if typed_ref.typed_id > 0:
                    tg.start_soon(_check_element_latest, elements[0])  # check the oldest element

            for typed_ref, (element, after) in prepare.reference_checks.items():
                tg.start_soon(_check_element_not_referenced, element, after)

            # check time integrity before updating
            # may sleep to self-correct the time
            await _check_time_integrity()

            async def update_elements_and_store_typed_ids() -> None:
                nonlocal old_ref_elements_map
                old_ref_elements_map = await _update_elements(elements, session)

            tg.start_soon(_update_changesets, prepare.changesets_next, session)
            tg.start_soon(update_elements_and_store_typed_ids)

        return old_ref_elements_map


async def _update_changesets(changesets_next: dict[SequentialId, Changeset], session: AgnosticClientSession) -> None:
    """
    Update the changeset collection.

    Raises `OptimisticException` if any of the changesets changed.
    """

    batch = []
    for changeset in changesets_next.values():
        batch.append(changeset.update_batch())

    result = await Changeset._collection().bulk_write(batch, ordered=False, session=session)
    if result.modified_count != len(batch):
        raise OptimisticException('Changeset was modified')


async def _update_elements(
    self, elements: Sequence[Element], session: AgnosticClientSession
) -> dict[TypedElementRef, Sequence[Element]]:
    """
    Update the element collection by creating new revisions.

    Returns a dict mapping original typed refs to the new elements.

    Raises `OptimisticException` if any of the elements failed to create.
    """

    _set_elements_created_at(elements)

    old_ref_elements_map: dict[TypedElementRef, list[Element]] = defaultdict(list)

    # remember the old refs before assigning new ids
    for element in elements:
        old_ref_elements_map[element.typed_ref].append(element)

    await _set_elements_id(elements, session)

    batch = []
    for element in elements:
        batch.append(element.create_batch())

    result = await Element._collection().bulk_write(batch, ordered=False, session=session)
    if result.inserted_count != len(batch):
        raise OptimisticException('Element failed to create')

    return old_ref_elements_map


async def _check_element_latest(element: Element) -> None:
    """
    Check if the element is the latest version.

    Raises `OptimisticException` if not.
    """

    latest = await Element.find_one_by_typed_ref(element.typed_ref)
    if not latest:
        raise RuntimeError(f'Element {element.typed_ref} does not exist')
    if latest.version != element.version:
        raise OptimisticException(
            f'Element {element.typed_ref} is not the latest version ' f'{latest.version} != {element.version}'
        )


async def _check_element_not_referenced(element: Element, after: SequentialId | None) -> None:
    """
    Check if the element is not referenced by any other element.

    Raises `OptimisticException` if it is.
    """

    if referenced_by_elements := await element.get_referenced_by(after=after, limit=1):
        raise OptimisticException(
            f'Element {element.typed_ref} is referenced by ' f'{referenced_by_elements[0].typed_ref}'
        )


async def _check_time_integrity() -> None:
    """
    Check the time integrity of the database.

    This function may sleep if the latest element was created shortly in the future.
    """

    latest_element = await Element.find_latest()
    if latest_element:
        while (latest_element_age := (utcnow() - latest_element.created_at).total_seconds()) <= 0:
            in_future = -latest_element_age
            if in_future < 1:
                logging.info('Latest element was created %d seconds in the future, sleeping...', in_future)
                await anyio.sleep(in_future)
            else:
                logging.error('Latest element was created %d seconds in the future', in_future)
                raise_for().time_integrity()


def _set_elements_created_at(elements: Sequence[Element]) -> None:
    """
    Set the creation date of the elements.
    """

    created_at = utcnow()
    for element in elements:
        if element.created_at:
            raise RuntimeError(f'Element {element.typed_ref} already has a creation date')
        element.created_at = created_at


async def _set_elements_id(elements: Sequence[Element], session: AgnosticClientSession) -> None:
    """
    Set the ids and typed ids of the elements.

    This function also updates the members of the elements if needed.
    """

    async def assign_ids() -> None:
        # allocate ids
        assign_ids = list(reversed(await Element.get_next_sequence(len(elements), session)))

        # assign ids to elements
        for element in elements:
            if element.id:
                raise RuntimeError(f'Element {element.typed_ref} already has an id')
            element.id = assign_ids.pop()

        # sanity check
        if assign_ids:
            raise RuntimeError('Not all ids were assigned')

    async def assign_typed_ids() -> None:
        assign_typed_ids: dict[ElementType, list[SequentialId]] = {}
        assigned_typed_ids: dict[TypedElementRef, SequentialId] = {}

        async def allocate_typed_ids(type: ElementType) -> None:
            n = sum(1 for e in elements if e.typed_id < 0 and e.type == type)
            if type == ElementType.node:
                cls = ElementNode
            elif type == ElementType.way:
                cls = ElementWay
            elif type == ElementType.relation:
                cls = ElementRelation
            else:
                raise NotImplementedError(f'Unsupported element type {type!r}')
            assign_typed_ids[type] = list(reversed(await cls.get_next_typed_sequence(n, session)))

        async with anyio.create_task_group() as tg:
            for type in ElementType:
                tg.start_soon(allocate_typed_ids, type)

        # do we need to assign typed ids?
        if not any(assign_typed_ids.values()):
            return

        # assign typed ids to elements
        for element in elements:
            if element.typed_id < 0:
                if not (assigned_id := assigned_typed_ids.get(element.typed_ref)):
                    assigned_typed_ids[element.typed_ref] = assigned_id = assign_typed_ids[element.type].pop()
                element.typed_id = assigned_id

        # update element members
        for element in elements:
            element.members = tuple(
                member.model_copy(update={'ref': member.ref.model_copy(update={'id': assigned_typed_ids[member.ref]})})
                if member.ref.id < 0
                else member
                for member in element.members
            )

        # sanity check
        if any(assign_typed_ids.values()):
            raise RuntimeError('Not all typed ids were assigned')

    async with anyio.create_task_group() as tg:
        tg.start_soon(assign_ids)
        tg.start_soon(assign_typed_ids)
