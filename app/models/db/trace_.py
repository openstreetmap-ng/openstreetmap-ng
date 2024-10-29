from collections.abc import Collection, Container
from typing import Literal, get_args

import numpy as np
from numpy.typing import NDArray
from sqlalchemy import ARRAY, ColumnElement, Enum, ForeignKey, Integer, Unicode, true
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.limits import STORAGE_KEY_MAX_LENGTH, TRACE_TAG_MAX_LENGTH, TRACE_TAGS_LIMIT
from app.models.db.base import Base
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.updated_at_mixin import UpdatedAtMixin
from app.models.db.user import User
from app.models.scope import Scope
from app.models.types import StorageKey

TraceVisibility = Literal['identifiable', 'public', 'trackable', 'private']


class Trace(Base.Sequential, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = 'trace'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(init=False, lazy='raise', innerjoin=True)
    name: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    description: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    visibility: Mapped[TraceVisibility] = mapped_column(
        Enum(*get_args(TraceVisibility), name='trace_visibility'),
        nullable=False,
    )

    size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_id: Mapped[StorageKey] = mapped_column(Unicode(STORAGE_KEY_MAX_LENGTH), init=False, nullable=False)

    # defaults
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Unicode(TRACE_TAG_MAX_LENGTH), dimensions=1),
        nullable=False,
        server_default='{}',
    )

    # runtime
    coords: NDArray[np.number] = None  # pyright: ignore[reportAssignmentType]

    @validates('tags')
    def validate_tags(self, _: str, value: Collection[str]):
        if len(value) > TRACE_TAGS_LIMIT:
            raise ValueError(f'Too many trace tags ({len(value)} > {TRACE_TAGS_LIMIT})')
        return value

    @property
    def tag_string(self) -> str:
        return ', '.join(self.tags)

    @tag_string.setter
    def tag_string(self, s: str) -> None:
        if ',' in s:
            sep = ','
        else:
            # do as before for backwards compatibility
            # BUG: this produces weird behavior: 'a b, c' -> ['a b', 'c']; 'a b' -> ['a', 'b']
            sep = None

        # remove duplicates and preserve order
        result_set: set[str] = set()
        result: list[str] = []
        for tag in s.split(sep):
            tag = tag.strip()[:TRACE_TAG_MAX_LENGTH].strip()
            if tag and (tag not in result_set):
                result_set.add(tag)
                result.append(tag)

        self.tags = result

    @hybrid_property
    def linked_to_user_in_api(self) -> bool:
        return self.visibility == 'identifiable'

    @linked_to_user_in_api.inplace.expression
    @classmethod
    def _linked_to_user_in_api(cls) -> ColumnElement[bool]:
        return cls.visibility == 'identifiable'

    @hybrid_property
    def linked_to_user_on_site(self) -> bool:
        return self.visibility in {'identifiable', 'public'}

    @linked_to_user_on_site.inplace.expression
    @classmethod
    def _linked_to_user_on_site(cls) -> ColumnElement[bool]:
        return cls.visibility.in_(('identifiable', 'public'))

    @hybrid_property
    def timestamps_via_api(self) -> bool:
        return self.visibility in {'identifiable', 'trackable'}

    @timestamps_via_api.inplace.expression
    @classmethod
    def _timestamps_via_api(cls) -> ColumnElement[bool]:
        return cls.visibility.in_(('identifiable', 'trackable'))

    @hybrid_method
    def visible_to(self, user: User | None, scopes: Container[Scope]) -> bool:  # pyright: ignore[reportRedeclaration]
        if (user is not None) and Scope.read_gpx in scopes:
            return self.linked_to_user_on_site or (self.user_id == user.id)
        else:
            return self.linked_to_user_on_site

    @visible_to.expression
    @classmethod
    def visible_to(cls, user: User | None, scopes: Container[Scope]) -> ColumnElement[bool]:
        if (user is not None) and Scope.read_gpx in scopes:
            return cls.linked_to_user_on_site | (cls.user_id == user.id)
        else:
            return cls.linked_to_user_on_site == true()
