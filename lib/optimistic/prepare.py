import logging
from collections import defaultdict
from typing import Sequence

import anyio
from pymongo import ASCENDING
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from lib.auth import Auth
from lib.exceptions import raise_for
from models.db.base_sequential import SequentialId
from models.db.changeset import Changeset
from models.db.element import Element
from models.db.element_node import ElementNode
from models.db.element_relation import ElementRelation
from models.db.element_way import ElementWay
from models.element_type import ElementType
from models.typed_element_ref import TypedElementRef
from utils import utcnow


class OptimisticPrepare:
    def __init__(self, elements: Sequence[Element]) -> None:
        self.elements = elements
        self.changesets_next: dict[SequentialId, Changeset] = {}
        self.reference_checks: dict[TypedElementRef, tuple[Element, SequentialId | None]] = {}
        self.state: dict[TypedElementRef, list[Element]] = {}

        self._references: dict[tuple[TypedElementRef, bool], set[TypedElementRef]] = defaultdict(set)

    async def prepare(self) -> None:
        if self.state:
            raise RuntimeError(f'{self.__class__.__qualname__} was reused')

        now = utcnow()

        async with anyio.create_task_group() as tg:
            changeset_id_element_map = defaultdict(list)
            for element in self.elements:
                changeset_id_element_map[element.changeset_id].append(element)

            # check if all changesets are valid (exist, belong to current user, and are open)
            for changeset_id, changeset_elements in changeset_id_element_map.items():
                tg.start_soon(self._update_changeset_size, changeset_id, changeset_elements)

            # preload some elements
            for typed_ref in set(e.typed_ref for e in self.elements):
                if typed_ref.id > 0:
                    tg.start_soon(self._get_latest_element, typed_ref)

        for element in self.elements:
            if element.version == 1:
                # action: create
                prev = None

                if element.typed_id >= 0:
                    raise_for().diff_create_bad_id(element.versioned_ref)
            else:
                # action: modify, delete
                prev = await self._get_latest_element(element.typed_ref)

                if prev.version + 1 != element.version:
                    raise_for().element_version_conflict(element.versioned_ref, prev.version)
                if not prev.visible and not element.visible:
                    raise_for().element_already_deleted(element.versioned_ref)

                if prev.created_at and prev.created_at > now:
                    logging.error(
                        'Element %r/%r was created in the future: %r > %r',
                        prev.type,
                        prev.typed_id,
                        prev.created_at,
                        now,
                    )
                    raise_for().time_integrity()

            # update references before performing checks
            # note that elements can self-reference themselves
            self._update_references(prev, element)

            async with anyio.create_task_group() as tg:
                # check if all referenced elements are visible
                for typed_ref in element.references:
                    tg.start_soon(self._check_element_visible, element, typed_ref)

                # if deleted, check if not referenced by other elements
                if not element.visible and prev and prev.visible:
                    tg.start_soon(self._check_element_not_referenced, element)

                # update changeset boundary
                tg.start_soon(self._update_changeset_boundary, prev, element)

            # update the latest element state
            self._set_latest_element(element)

    async def _get_changeset(self, changeset_id: SequentialId) -> Changeset:
        """
        Get the changeset from the local state or the database if not found.
        """

        if not (changeset := self.changesets_next.get(changeset_id)):
            changeset = await Changeset.find_one_by_id(changeset_id)
            if not changeset:
                raise_for().changeset_not_found(changeset_id)
            if changeset.user_id != Auth.user().id:
                raise_for().changeset_access_denied()
            if changeset.closed_at:
                raise_for().changeset_already_closed(changeset_id, changeset.closed_at)
            self.changesets_next[changeset_id] = changeset
        return changeset

    async def _update_changeset_size(self, changeset_id: SequentialId, elements: Sequence[Element]) -> None:
        """
        Update the changeset size and check if it is not too big.
        """

        changeset = await self._get_changeset(changeset_id)
        increase_size = len(elements)
        if not changeset.update_size_without_save(increase_size):
            raise_for().changeset_too_big(changeset.size + increase_size)

    async def _update_changeset_boundary(self, prev: Element | None, element: Element) -> None:
        """
        Update the changeset boundary.
        """

        if boundary := await self._get_boundary(prev, element):
            changeset = await self._get_changeset(element.changeset_id)
            changeset.update_boundary_without_save(boundary)

    async def _get_latest_element(self, typed_ref: TypedElementRef) -> Element:
        """
        Get the latest element from the local state or the database if not found.
        """

        if not (elements := self.state.get(typed_ref)):
            if typed_ref.typed_id < 0:
                raise_for().element_not_found(typed_ref)
            if not (element := await Element.find_one_by_typed_ref(typed_ref)):
                raise_for().element_not_found(typed_ref)
            self.state[typed_ref] = elements = [element]
        return elements[-1]

    def _set_latest_element(self, element: Element) -> None:
        """
        Update the local element state with the new element.
        """

        if elements := self.state.get(element.typed_ref):
            elements.append(element)
        else:
            self.state[element.typed_ref] = [element]

    def _update_references(self, prev: Element | None, element: Element) -> None:
        """
        Update the local references state.
        """

        prev_refs = prev.references if prev else frozenset()
        next_refs = element.references
        typed_ref = element.typed_ref

        # remove old references
        for ref in prev_refs - next_refs:
            self._references[(ref, True)].discard(typed_ref)
            self._references[(ref, False)].add(typed_ref)
        # add new references
        for ref in next_refs - prev_refs:
            self._references[(ref, True)].add(typed_ref)
            self._references[(ref, False)].discard(typed_ref)

    async def _check_element_visible(self, initiator: Element, typed_ref: TypedElementRef) -> None:
        """
        Check if the element exists and is visible.
        """

        try:
            if not (await self._get_latest_element(typed_ref)).visible:
                raise Exception()
        except Exception:
            raise_for().element_member_not_found(initiator.versioned_ref, typed_ref)

    async def _check_element_not_referenced(self, element: Element) -> None:
        """
        Check if the element is not referenced by other elements.
        """

        # check if not referenced by local elements
        if refs := self._references[(element.typed_ref, True)]:
            raise_for().element_in_use(element.versioned_ref, refs)

        # check if not referenced by database elements (only existing elements)
        if element.typed_id > 0:
            negative_refs = self._references[(element.typed_ref, False)]
            referenced_by_elements = await element.get_referenced_by(
                sort={'_id': ASCENDING}, limit=len(negative_refs) + 1
            )
            referenced_by = set(r.typed_ref for r in referenced_by_elements)
            if refs := (referenced_by - negative_refs):
                raise_for().element_in_use(element.versioned_ref, refs)

            # remember the last referenced element for the successful reference check
            self.reference_checks.setdefault(
                element.typed_ref, (element, referenced_by_elements[-1].id if referenced_by_elements else None)
            )

    # TODO: optimize geometry fetch, reduce database calls
    async def _get_boundary(self, prev: Element | None, element: Element) -> BaseGeometry | None:
        """
        Calculate the boundary (if any) of the element.
        """

        if element.type == ElementType.node:
            return self._get_node_boundary(prev, element)
        elif element.type == ElementType.way:
            return await self._get_way_boundary(prev, element)
        elif element.type == ElementType.relation:
            return await self._get_relation_boundary(prev, element)
        else:
            raise NotImplementedError(f'Unsupported element type {element.type!r}')

    def _get_node_boundary(self, prev: ElementNode | None, element: ElementNode) -> BaseGeometry | None:
        if element.point:
            return element.point
        elif prev and prev.point:
            return prev.point
        else:
            return None

    async def _get_way_boundary(self, prev: ElementWay | None, element: ElementWay) -> BaseGeometry | None:
        prev_refs = prev.references if prev else frozenset()
        next_refs = element.references
        geoms = []

        async def update_geoms(typed_ref: TypedElementRef) -> None:
            try:
                node = await self._get_latest_element(typed_ref)
                geoms.append(self._get_node_boundary(None, node))
            except Exception:
                # ignore geometry errors
                pass

        async with anyio.create_task_group() as tg:
            for typed_ref in prev_refs | next_refs:
                tg.start_soon(update_geoms, typed_ref)

        return box(*unary_union(geoms).bounds) if geoms else None

    async def _get_relation_boundary(
        self, prev: ElementRelation | None, element: ElementRelation
    ) -> BaseGeometry | None:
        prev_refs = prev.references if prev else frozenset()
        next_refs = element.references
        changed_refs = prev_refs ^ next_refs
        contains_relation = any(ref.type == ElementType.relation for ref in changed_refs)
        tags_changed = not prev or prev.tags != element.tags
        geoms = []

        async def update_geoms(typed_ref: TypedElementRef) -> None:
            try:
                element = await self._get_latest_element(typed_ref)
                geoms.append(await self._get_boundary(None, element))
            except Exception:
                # ignore geometry errors
                pass

        async with anyio.create_task_group() as tg:
            if tags_changed or contains_relation:
                # get full geometry
                for typed_ref in prev_refs | next_refs:
                    if typed_ref.type != ElementType.relation:
                        tg.start_soon(update_geoms, typed_ref)
            else:
                # get only changed geometry
                for typed_ref in changed_refs:
                    if typed_ref.type != ElementType.relation:
                        tg.start_soon(update_geoms, typed_ref)

        return box(*unary_union(geoms).bounds) if geoms else None
