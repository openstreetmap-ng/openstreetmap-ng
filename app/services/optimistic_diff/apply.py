import logging
from collections import defaultdict
from collections.abc import Sequence

from anyio import create_task_group
from sqlalchemy import and_, insert, null, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db import db_commit
from app.exceptions.optimistic_diff_error import OptimisticDiffError
from app.models.db.changeset import Changeset
from app.models.db.element import Element
from app.models.db.element_member import ElementMember
from app.models.element_ref import ElementRef, VersionedElementRef
from app.models.element_type import ElementType
from app.queries.changeset_query import ChangesetQuery
from app.queries.element_query import ElementQuery
from app.services.optimistic_diff.prepare import OptimisticDiffPrepare

# allow reads but prevent writes
_lock_table_sql = text(
    f'LOCK TABLE "{Changeset.__tablename__}","{Element.__tablename__}","{ElementMember.__tablename__}" IN EXCLUSIVE MODE'
)


class OptimisticDiffApply:
    async def apply(self, prepare: OptimisticDiffPrepare) -> dict[ElementRef, Sequence[Element]]:
        """
        Apply the optimistic diff update.

        Returns a dict, mapping original element refs to the new elements.
        """
        assigned_ref_map: dict[ElementRef, list[Element]] = defaultdict(list)
        for element in prepare.elements:
            assigned_ref_map[ElementRef(element.type, element.id)].append(element)

        async with db_commit() as session, create_task_group() as tg:
            # obtain exclusive lock on the tables
            await session.execute(_lock_table_sql)

            # check if the element_state is valid
            tg.start_soon(_check_elements_latest, prepare.element_state)

            # check if the elements have no new references
            if prepare.reference_check_element_refs:
                tg.start_soon(
                    _check_elements_unreferenced,
                    prepare.reference_check_element_refs,
                    prepare.at_sequence_id,
                )

            tg.start_soon(_update_changesets, prepare.changeset_state, session)
            tg.start_soon(_update_elements, prepare.elements, session)

        return assigned_ref_map


async def _check_elements_latest(element_state: dict[ElementRef, Sequence[Element]]) -> None:
    """
    Check if the elements are the current version.

    Raises OptimisticDiffError if they are not.
    """
    versioned_refs = tuple(
        VersionedElementRef(ref.type, ref.id, elements[0].version)
        for ref, elements in element_state.items()
        if ref.id > 0
    )
    if not versioned_refs:
        return
    if not await ElementQuery.is_latest(versioned_refs):
        raise OptimisticDiffError('Element is outdated')


async def _check_elements_unreferenced(element_refs: Sequence[ElementRef], after_sequence_id: int) -> None:
    """
    Check if the elements are currently unreferenced.

    Raises OptimisticDiffError if they are.
    """
    if not await ElementQuery.is_unreferenced(element_refs, after_sequence_id):
        raise OptimisticDiffError(f'Element is referenced after {after_sequence_id}')


async def _update_changesets(changeset_state: dict[int, Changeset], session: AsyncSession) -> None:
    """
    Update the changeset table.

    Raises OptimisticDiffError if any of the changesets were modified in the meantime.
    """
    changeset_id_updated_map = await ChangesetQuery.get_updated_at_by_ids(changeset_state)

    for changeset_id, updated_at in changeset_id_updated_map.items():
        changeset = changeset_state.pop(changeset_id)
        if changeset.updated_at != updated_at:
            raise OptimisticDiffError(f'Changeset {changeset_id} is outdated ({changeset.updated_at} != {updated_at})')

        changeset.auto_close_on_size()
        session.add(changeset)

    # sanity check
    if changeset_state:
        raise ValueError(f'Changesets {tuple(changeset_state)!r} not found')


async def _update_elements(elements: Sequence[Element], session: AsyncSession) -> None:
    """
    Update the element table by creating new revisions.
    """
    current_sequence_id: int | None = None
    current_id_map: dict[ElementType, int] | None = None

    async def sequence_task():
        nonlocal current_sequence_id
        current_sequence_id = await ElementQuery.get_current_sequence_id()

    async def type_id_task():
        nonlocal current_id_map
        current_id_map = await ElementQuery.get_current_ids()

    async with create_task_group() as tg:
        tg.start_soon(sequence_task)
        tg.start_soon(type_id_task)

    update_type_ids: dict[ElementType, list[int]] = defaultdict(list)
    insert_elements: list[dict] = [None] * len(elements)
    insert_members: list[dict] = []

    prev_map: dict[ElementRef, Element] = {}
    assigned_id_map: dict[ElementRef, int] = {}

    # process elements
    for sequence_id, element in enumerate(elements, current_sequence_id + 1):
        # assign sequence_id
        element.sequence_id = sequence_id

        # assign next_sequence_id
        element_type = element.type
        element_id = element.id
        ref = ElementRef(element_type, element_id)
        prev = prev_map.get(ref)
        if prev is not None:
            prev.next_sequence_id = sequence_id  # update locally
        elif element.version > 1:
            update_type_ids[element_type].append(element_id)  # update remotely
        prev_map[ref] = element

        # assign id
        if element_id < 0:
            assigned_id = assigned_id_map.get(ref)
            if assigned_id is None:
                assigned_id = current_id_map[element_type] + 1
                assigned_id_map[ref] = current_id_map[element_type] = assigned_id
            element.id = assigned_id

    # process members, populate insert data
    for i, element in enumerate(elements):
        sequence_id = element.sequence_id
        insert_elements[i] = {
            'sequence_id': sequence_id,
            'changeset_id': element.changeset_id,
            'type': element.type,
            'id': element.id,
            'version': element.version,
            'visible': element.visible,
            'tags': element.tags,
            'point': element.point,
            'next_sequence_id': element.next_sequence_id,
        }

        for member in element.members:
            # assign sequence_id
            member.sequence_id = sequence_id

            # assign id
            if member.id < 0:
                ref = ElementRef(member.type, member.id)
                member.id = assigned_id_map[ref]

            insert_members.append(
                {
                    'sequence_id': sequence_id,
                    'order': member.order,
                    'type': member.type,
                    'id': member.id,
                    'role': member.role,
                }
            )

    await _update_elements_db(current_sequence_id, update_type_ids, insert_elements, insert_members, session)


async def _update_elements_db(
    current_sequence_id: int,
    update_type_ids: dict[ElementType, Sequence[int]],
    insert_elements: Sequence[dict],
    insert_members: Sequence[dict],
    session: AsyncSession,
) -> None:
    """
    Update the element table by creating new revisions - push prepared data to the database.
    """
    async with create_task_group() as tg:
        logging.info('Inserting %d elements and %d members', len(insert_elements), len(insert_members))
        tg.start_soon(session.execute, insert(Element).values(insert_elements).inline())
        tg.start_soon(session.execute, insert(ElementMember).values(insert_members).inline())

    if update_type_ids:
        E = aliased(Element)  # noqa: N806
        stmt = (
            update(Element)
            .where(
                Element.sequence_id <= current_sequence_id,
                Element.next_sequence_id == null(),
                or_(
                    and_(
                        Element.type == type,
                        Element.id.in_(text(','.join(map(str, ids)))),
                    )
                    for type, ids in update_type_ids.items()
                ),
            )
            .values(
                {
                    Element.next_sequence_id: select(E.sequence_id)
                    .where(
                        E.type == Element.type,
                        E.id == Element.id,
                        E.version > Element.version,
                    )
                    .order_by(E.version.asc())
                    .limit(1)
                    .scalar_subquery()
                }
            )
            .inline()
        )
        await session.execute(stmt)
