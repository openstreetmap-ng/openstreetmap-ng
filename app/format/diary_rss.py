import cython
from feedgen.entry import FeedEntry
from feedgen.feed import FeedGenerator
from shapely import get_coordinates

from app.config import APP_URL
from app.models.db.diary import Diary


class DiaryRSSMixin:
    @staticmethod
    def encode_diaries(fg: FeedGenerator, diaries: list[Diary]):
        """Encode diaries into a feed."""
        fg.load_extension('geo')
        for diary in diaries:
            _encode_diary(fg, diary)


@cython.cfunc
def _encode_diary(fg: FeedGenerator, diary: Diary):
    diary_id = diary['id']
    permalink = f'{APP_URL}/diary/{diary_id}'

    fe: FeedEntry = fg.add_entry(order='append')
    fe.guid(permalink, permalink=True)
    fe.link(href=permalink)
    fe.title(diary['title'])
    fe.published(diary['created_at'])
    fe.updated(diary['updated_at'])
    fe.content(
        diary['body_rich'],  # pyright: ignore[reportTypedDictNotRequiredAccess]
        type='CDATA',
    )

    user = diary['user']  # pyright: ignore[reportTypedDictNotRequiredAccess]
    user_permalink = f'{APP_URL}/user-id/{user["id"]}'
    fe.author(name=user['display_name'], uri=user_permalink)

    point = diary['point']
    if point is not None:
        x, y = get_coordinates(point).round(7)[0].tolist()
        fe.geo.point(f'{y} {x}')
