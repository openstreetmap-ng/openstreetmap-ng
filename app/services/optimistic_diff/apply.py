import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime

from anyio import create_task_group
from sqlalchemy import and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import db_autocommit
from app.exceptions.optimistic_diff_error import OptimisticDiffError
from app.lib.date_utils import utcnow
from app.lib.exceptions_context import raise_for
from app.models.db.changeset import Changeset
from app.models.db.element import Element
from app.models.element_ref import ElementRef, VersionedElementRef
from app.models.element_type import ElementType
from app.repositories.changeset_repository import ChangesetRepository
from app.repositories.element_repository import ElementRepository
from app.services.optimistic_diff.prepare import OptimisticDiffPrepare

# TODO 0.7 don't reuse placeholder ids for simplicity


class OptimisticDiffApply:
    __slots__ = ('_now',)

    _now: datetime

    async def apply(self, prepare: OptimisticDiffPrepare) -> dict[ElementRef, Sequence[Element]]:
        """
        Apply the optimistic update.

        Returns a dict, mapping original element refs to the new elements.
        """

        if prepare.applied:
            raise RuntimeError(f'{self.__class__.__qualname__} was reused on the same prepare instance')

        prepare.applied = True
        assigned_ref_map: dict[ElementRef, Sequence[Element]] = None

        async with db_autocommit() as session, create_task_group() as tg:
            # lock the tables, allowing reads but blocking writes
            await session.execute(
                f'LOCK TABLE "{Changeset.__tablename__}", "{Element.__tablename__}" IN EXCLUSIVE MODE'
            )

            # get the current time
            self._now = utcnow()

            # check time integrity
            tg.start_soon(self._check_time_integrity)

            # check if the element state is still valid
            for element_ref, elements in prepare.element_state.items():
                if element_ref.id > 0:
                    tg.start_soon(self._check_element_is_latest, elements[0])  # check the oldest element

            # check if the elements are not referenced by any *new* elements
            if element_refs := prepare.reference_check_element_refs:
                tg.start_soon(
                    self._check_elements_not_referenced,
                    element_refs,
                    prepare.last_sequence_id,
                )

            # update the changesets
            tg.start_soon(self._update_changesets, prepare.changeset_state, session)

            # update the elements
            async def update_elements_task() -> None:
                nonlocal assigned_ref_map
                assigned_ref_map = await self._update_elements(prepare.elements, session)

            tg.start_soon(update_elements_task)

        return assigned_ref_map

    async def _check_time_integrity(self) -> None:
        """
        Check the time integrity of the database.
        """

        element = await ElementRepository.find_one_latest()
        if element is not None and element.created_at > self._now:
            logging.error(
                'Element %r/%r was created in the future: %r > %r',
                element.type,
                element.id,
                element.created_at,
                self._now,
            )
            raise_for().time_integrity()

    async def _check_element_is_latest(self, element: Element) -> None:
        """
        Check if the element is the latest version.

        Raises `OptimisticDiffError` if it is not.
        """

        many_latest = await ElementRepository.get_many_latest_by_element_refs((element.element_ref,), limit=1)

        if not many_latest:
            raise ValueError(f'Element {element.element_ref} does not exist')

        latest = many_latest[0]

        if latest.version != element.version:
            raise OptimisticDiffError(
                f'Element {element.element_ref} is not the latest version ({latest.version} != {element.version})'
            )

    async def _check_elements_not_referenced(self, element_refs: Sequence[ElementRef], after: int) -> None:
        """
        Check if the elements are not referenced by any other elements after the given sequence id.

        Raises `OptimisticDiffError` if they are.
        """

        if parents := await ElementRepository.get_many_parents_by_element_refs(
            element_refs,
            after_sequence_id=after,
            limit=1,
        ):
            raise OptimisticDiffError(f'Element is referenced by {parents[0].element_ref}')

    async def _update_changesets(
        self,
        changesets_next: dict[int, Changeset],
        session: AsyncSession,
    ) -> None:
        """
        Update the changeset table.

        Raises `OptimisticDiffError` if any of the changesets were modified in the meantime.
        """

        for changeset_id, updated_at in (await ChangesetRepository.get_updated_at_by_ids(changesets_next)).items():
            local = changesets_next.pop(changeset_id)

            # ensure the changeset was not modified
            if local.updated_at != updated_at:
                raise OptimisticDiffError(f'Changeset {changeset_id} was modified ({local.updated_at} != {updated_at})')

            # update the changeset
            local.updated_at = self._now
            local.auto_close_on_size(now=self._now)
            session.add(local)

        # sanity check
        if changesets_next:
            raise ValueError(f'Changesets {tuple(changesets_next)!r} were not found in the database')

    async def _update_elements(
        self,
        elements: Sequence[Element],
        session: AsyncSession,
    ) -> dict[ElementRef, Sequence[Element]]:
        """
        Update the element table by creating new revisions.

        Returns a dict, mapping original element refs to the new elements.
        """

        assigned_ref_map: dict[ElementRef, list[Element]] = defaultdict(list)

        # remember old refs before assigning ids
        for element in elements:
            assigned_ref_map[element.element_ref].append(element)

        await self._assign_ids(elements)

        # process superseded elements and update the timestamps
        superseded_refs: set[VersionedElementRef] = set()
        now = self._now  # speed up access

        for element in reversed(elements):
            element_versioned_ref: VersionedElementRef = element.versioned_ref
            element.created_at = now

            # process superseded elements (local)
            if element_versioned_ref in superseded_refs:
                superseded_refs.remove(element_versioned_ref)
                element.superseded_at = now

            # supersede the previous version
            if element.version > 1:
                previous_versioned_ref = replace(element_versioned_ref, version=element_versioned_ref.version - 1)
                superseded_refs.add(previous_versioned_ref)

        # process superseded elements (remote)
        if superseded_refs:
            stmt = (
                update(Element)
                .where(
                    or_(
                        *(
                            and_(
                                Element.type == versioned_ref.type,
                                Element.id == versioned_ref.id,
                                Element.version == versioned_ref.version,
                            )
                            for versioned_ref in superseded_refs
                        )
                    )
                )
                .values({Element.superseded_at: now})
            )

            await session.execute(stmt)

        # create new elements
        # will raise IntegrityError on unique constraint violation
        session.add_all(elements)

        return assigned_ref_map

    async def _assign_ids(self, elements: Sequence[Element]) -> None:
        """
        Assign ids to the elements placeholders and update their members.
        """

        elements_without_id: list[Element] = []
        type_next_id_map: dict[ElementType, int] = {}
        started_type_tasks: set[ElementType] = set()

        async def type_next_id_task(type: ElementType) -> None:
            last_id_by_type = await ElementRepository.get_last_id_by_type(type)
            type_next_id_map[type] = last_id_by_type + 1

        async with create_task_group() as tg:
            for element in elements:
                if element.id > 0:
                    continue

                elements_without_id.append(element)

                element_type = element.type
                if element_type in started_type_tasks:
                    continue

                tg.start_soon(type_next_id_task, element_type)
                started_type_tasks.add(element_type)

        # small optimization, skip if no elements needing assignment
        if not elements_without_id:
            return

        # assign ids
        assigned_id_map: dict[ElementRef, int] = {}

        for element in elements_without_id:
            # check for existing assigned id
            if (assigned_id := assigned_id_map.get(element.element_ref)) is not None:
                element.id = assigned_id
                continue

            # assign new id
            assigned_id = type_next_id_map[element.type]
            type_next_id_map[element.type] += 1
            element.id = assigned_id
            assigned_id_map[element.element_ref] = assigned_id

        # update elements members
        for element in elements:
            if element.members:
                element.members = tuple(
                    replace(member_ref, id=assigned_id_map[member_ref.element_ref])
                    if member_ref.id < 0  #
                    else member_ref
                    for member_ref in element.members
                )
