from datetime import date, timedelta

import numpy as np

from app.config import USER_ACTIVITY_CHART_WEEKS
from app.lib.date_utils import utcnow
from app.models.proto.profile_pb2 import Page
from app.models.types import UserId
from app.queries.changeset_query import ChangesetQuery


async def user_activity_summary(user_id: UserId):
    """
    Get activity data for the given user.
    Used to render the activity chart on user profile pages.
    """
    # Configure the date range for the chart
    today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    weekday = (today.weekday() + 1) % 7  # Adjust to put Sunday on top
    created_since = today - timedelta(days=USER_ACTIVITY_CHART_WEEKS * 7 + weekday)

    # Fetch user activity data
    activity_per_day = await ChangesetQuery.count_per_day_by_user(
        user_id, created_since
    )

    # Generate continuous date range
    dates_range: list[date] = np.arange(
        np.datetime64(created_since.date(), 'D'),
        np.datetime64((today + timedelta(days=1)).date(), 'D'),
        np.timedelta64(1, 'D'),
        dtype='datetime64[D]',
    ).tolist()

    # Map activity counts to each date
    activity = np.array([activity_per_day.get(d, 0) for d in dates_range], np.uint32)

    # Calculate the clipping threshold used for deriving intensity levels (0-19)
    activity_positive = activity[activity > 0]
    max_activity_clip = (
        np.percentile(activity_positive, 95).tolist()
        if len(activity_positive) > 0  #
        else 1
    )

    return Page.ActivityChart(
        start_day=(dates_range[0] - date(1970, 1, 1)).days,
        values=activity.tolist(),
        max_activity_clip=max_activity_clip,
    )
