from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.db import DB
from app.lib_cython.auth_context import auth_user
from app.lib_cython.exceptions_context import raise_for
from app.lib_cython.joinedload_context import get_joinedload
from app.models.db.changeset import Changeset
from app.models.db.changeset_comment import ChangesetComment


class ChangesetCommentService:
    @staticmethod
    async def subscribe(changeset_id: int) -> Changeset:
        """
        Subscribe current user to changeset discussion.
        """

        try:
            async with DB() as session:
                changeset = await session.get(
                    Changeset,
                    changeset_id,
                    options=[
                        joinedload(Changeset.changeset_subscription_users),
                        get_joinedload(),
                    ],
                )

                if not changeset:
                    raise_for().changeset_not_found(changeset_id)

                changeset.changeset_subscription_users.append(auth_user())

        except IntegrityError:
            raise_for().changeset_already_subscribed(changeset_id)

        return changeset

    @staticmethod
    async def unsubscribe(changeset_id: int) -> Changeset:
        """
        Unsubscribe current user from changeset discussion.
        """

        async with DB() as session:
            changeset = await session.get(
                Changeset,
                changeset_id,
                options=[
                    joinedload(Changeset.changeset_subscription_users),
                    get_joinedload(),
                ],
            )

            if not changeset:
                raise_for().changeset_not_found(changeset_id)

        # TODO: will this work?
        try:
            changeset.changeset_subscription_users.remove(auth_user())
        except ValueError:
            raise_for().changeset_not_subscribed(changeset_id)

        return changeset

    @staticmethod
    async def comment(changeset_id: int, text: str) -> Changeset:
        """
        Comment on a changeset.
        """

        async with DB() as session:
            changeset = await session.get(
                Changeset,
                changeset_id,
                options=[
                    joinedload(Changeset.comments),
                    get_joinedload(),
                ],
            )

            if not changeset:
                raise_for().changeset_not_found(changeset_id)
            if not changeset.closed_at:
                raise_for().changeset_not_closed(changeset_id)

            changeset.comments.append(
                ChangesetComment(
                    user_id=auth_user().id,
                    changeset_id=changeset_id,
                    body=text,
                )
            )

        return changeset

    @staticmethod
    async def delete_comment_unsafe(comment_id: int) -> Changeset:
        """
        Delete any changeset comment.
        """

        async with DB() as session, session.begin():
            comment = await session.get(
                ChangesetComment,
                comment_id,
                with_for_update=True,
            )

            if not comment:
                raise_for().changeset_comment_not_found(comment_id)

            await session.delete(comment)
            await session.flush()

            changeset = await session.get(
                Changeset,
                comment.changeset_id,
                options=[get_joinedload()],
            )

        return changeset
