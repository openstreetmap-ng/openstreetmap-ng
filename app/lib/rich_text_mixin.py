from collections.abc import Sequence

import anyio
from sqlalchemy import update

from app.db import db_autocommit
from app.lib.rich_text import rich_text
from app.models.text_format import TextFormat


class RichTextMixin:
    __rich_text_fields__: Sequence[tuple[str, TextFormat]] = ()

    async def resolve_rich_text(self) -> None:
        """
        Resolve rich text fields.
        """

        async def resolve_task(field_name: str, text_format: TextFormat) -> None:
            rich_field_name = field_name + '_rich'

            # skip if already resolved
            if getattr(self, rich_field_name) is not None:
                return

            rich_hash_field_name = field_name + '_rich_hash'

            text: str = getattr(self, field_name)
            text_rich_hash: bytes | None = getattr(self, rich_hash_field_name)
            cache_entry = await rich_text(text, text_rich_hash, text_format)

            # assign new hash if changed
            if text_rich_hash != cache_entry.id:
                async with db_autocommit() as session:
                    cls = type(self)
                    stmt = (
                        update(cls)
                        .where(cls.id == self.id, getattr(cls, rich_hash_field_name) == text_rich_hash)
                        .values({rich_hash_field_name: cache_entry.id})
                    )

                    await session.execute(stmt)
                setattr(self, rich_hash_field_name, cache_entry.id)

            # assign value to instance
            setattr(self, rich_field_name, cache_entry)

        # small optimization, don't create task group if at most one field
        if len(self.__rich_text_fields__) <= 1:
            for field_name, text_format in self.__rich_text_fields__:
                await resolve_task(field_name, text_format)
        else:
            async with anyio.create_task_group() as tg:
                for field_name, text_format in self.__rich_text_fields__:
                    tg.start_soon(resolve_task, field_name, text_format)
