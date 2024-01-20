import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime

import anyio
from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.db import DB
from app.exceptions.optimistic_diff_error import OptimisticDiffError
from app.libc.exceptions_context import raise_for
from app.models.db.changeset import Changeset
from app.models.db.element import Element
from app.models.element_type import ElementType
from app.models.typed_element_ref import TypedElementRef
from app.models.versioned_element_ref import VersionedElementRef
from app.repositories.element_repository import ElementRepository
from app.services.optimistic_diff.prepare import OptimisticDiffPrepare
from app.utils import utcnow

# TODO 0.7 don't reuse placeholder ids for simplicity


class OptimisticDiffApply:
    _now: datetime

    async def apply(self, prepare: OptimisticDiffPrepare) -> dict[TypedElementRef, Sequence[Element]]:
        """
        Apply the optimistic update.

        Returns a dict, mapping original typed refs to the new elements.
        """

        if prepare.applied:
            raise RuntimeError(f'{self.__class__.__qualname__} was reused on the same prepare instance')

        prepare.applied = True
        assigned_ref_map: dict[TypedElementRef, Sequence[Element]] = None

        async with DB() as session, session.begin(), anyio.create_task_group() as tg:
            # lock the tables, allowing reads but blocking writes
            await session.execute(f'LOCK TABLE {Changeset.__tablename__}, {Element.__tablename__} IN EXCLUSIVE MODE')

            # get the current time
            self._now = utcnow()

            # check time integrity
            tg.start_soon(self._check_time_integrity)

            # check if the elements are still the latest version
            for typed_ref, elements in prepare.element_state.items():
                if typed_ref.typed_id > 0:
                    tg.start_soon(self._check_element_is_latest, elements[0])  # check the oldest element

            # check if the elements are not referenced by any *new* elements
            # TODO: single db call (already implemented)
            for element, after in prepare.reference_check_state.values():
                tg.start_soon(self._check_element_not_referenced, element, after)

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
        if not element:
            return
        if element.created_at > self._now:
            logging.error(
                'Element %r/%r was created in the future: %r > %r',
                element.type,
                element.typed_id,
                element.created_at,
                self._now,
            )
            raise_for().time_integrity()

    async def _check_element_is_latest(self, element: Element) -> None:
        """
        Check if the element is the latest version.

        Raises `OptimisticDiffError` if it is not.
        """

        latest = await Element.find_one_by_typed_ref(element.typed_ref)
        if not latest:
            raise RuntimeError(f'Element {element.typed_ref} does not exist')
        if latest.version != element.version:
            raise OptimisticDiffError(
                f'Element {element.typed_ref} is not the latest version ({latest.version} != {element.version})'
            )

    async def _check_element_not_referenced(self, element: Element, after: int) -> None:
        """
        Check if the element is not referenced by any other element.

        Raises `OptimisticDiffError` if it is.
        """

        if parents := await ElementRepository.get_many_parents_by_typed_refs([element.typed_ref], after=after, limit=1):
            raise OptimisticDiffError(f'Element {element.typed_ref} is referenced by {parents[0].typed_ref}')

    async def _update_changesets(
        self,
        changesets_next: dict[int, Changeset],
        session: AsyncSession,
    ) -> None:
        """
        Update the changeset table.

        Raises `OptimisticDiffError` if any of the changesets were modified in the meantime.
        """

        stmt = (
            select(Changeset)
            .options(load_only(Changeset.id, Changeset.updated_at, raiseload=True))
            .where(Changeset.id.in_(changesets_next))
        )

        async for remote in await session.stream_scalars(stmt):
            local = changesets_next.pop(remote.id)

            # check if the changeset was modified in the meantime
            if remote.updated_at != local.updated_at:
                raise OptimisticDiffError(
                    f'Changeset {remote.id} was modified ({remote.updated_at} != {local.updated_at})'
                )

            # update the changeset
            local.updated_at = self._now
            local.auto_close_on_size(now=self._now)
            session.add(local)

        # sanity check
        if changesets_next:
            raise RuntimeError(f'Changesets {tuple(changesets_next)!r} do not exist')

    async def _update_elements(
        self,
        elements: Sequence[Element],
        session: AsyncSession,
    ) -> dict[TypedElementRef, Sequence[Element]]:
        """
        Update the element table by creating new revisions.

        Returns a dict, mapping original typed refs to the new elements.
        """

        assigned_ref_map: dict[TypedElementRef, list[Element]] = defaultdict(list)

        # remember old refs before assigning ids
        for element in elements:
            assigned_ref_map[element.typed_ref].append(element)

        await self._assign_typed_ids(elements)

        # process superseded elements and update the timestamps
        superseded_refs: set[VersionedElementRef] = set()
        now = self._now  # speed up access

        for element in reversed(elements):
            element_versioned_ref: VersionedElementRef = element.versioned_ref
            element.created_at = now
            element.updated_at = now

            # process superseded elements (local)
            try:
                superseded_refs.remove(element_versioned_ref)
                element.superseded_at = now
            except KeyError:
                pass

            # supersede the previous version
            if element.version > 1:
                superseded_refs.add(replace(element_versioned_ref, version=element_versioned_ref.version - 1))

        # process superseded elements (remote)
        if superseded_refs:
            stmt = (
                update(Element)
                .where(
                    or_(
                        and_(
                            Element.type == versioned_ref.type,
                            Element.typed_id == versioned_ref.typed_id,
                            Element.version == versioned_ref.version,
                        )
                        for versioned_ref in superseded_refs
                    )
                )
                .values(superseded_at=now)
            )

            await session.execute(stmt)

        # create new elements
        # will raise IntegrityError on unique constraint violation
        session.add_all(elements)

        return assigned_ref_map

    async def _assign_typed_ids(self, elements: Sequence[Element]) -> None:
        """
        Assign typed ids to the elements and update their members.
        """

        next_typed_id_map: dict[ElementType, int] = {}
        assigned_typed_id_map: dict[TypedElementRef, int] = {}

        async def assign_last_typed_id(type: ElementType) -> None:
            if any(e.typed_id < 0 and e.type == type for e in elements):
                next_typed_id_map[type] = (await ElementRepository.get_last_typed_id_by_type(type)) + 1

        async with anyio.create_task_group() as tg:
            for type in ElementType:
                tg.start_soon(assign_last_typed_id, type)

        # small optimization, skip if no elements needing assignment
        if not next_typed_id_map:
            return

        # assign typed ids
        for element in elements:
            if element.typed_id > 0:
                continue

            # check for existing assigned id
            if assigned_id := assigned_typed_id_map.get(element.typed_ref):
                element.typed_id = assigned_id
                continue

            # assign new id
            assigned_id = next_typed_id_map[element.type]
            next_typed_id_map[element.type] += 1
            element.typed_id = assigned_id
            assigned_typed_id_map[element.typed_ref] = assigned_id

        # update element members
        for element in elements:
            element.members = tuple(
                replace(member, typed_id=assigned_typed_id_map[member.typed_ref]) if member.typed_id < 0 else member
                for member in element.members
            )
