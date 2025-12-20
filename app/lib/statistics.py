from base64 import urlsafe_b64encode
from datetime import date, timedelta
from typing import TypedDict

import numpy as np

from app.config import USER_ACTIVITY_CHART_WEEKS
from app.lib.date_utils import utcnow
from app.models.proto.shared_pb2 import UserActivityChart
from app.models.types import UserId
from app.queries.changeset_query import ChangesetQuery


class UserActivitySummaryResult(TypedDict):
    activity_chart: str
    """Base64-encoded protobuf payload describing the activity chart."""
    activity_max: int
    """Peak activity count."""
    activity_sum: int
    """Sum of all activity counts."""
    activity_days: int
    """Total mapping days."""


async def user_activity_summary(user_id: UserId) -> UserActivitySummaryResult:
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
        created_since.replace(tzinfo=None),
        today.replace(tzinfo=None) + timedelta(days=1),
        timedelta(days=1),
        'datetime64[D]',
    ).tolist()

    # Map activity counts to each date
    activity = np.array([activity_per_day.get(d, 0) for d in dates_range], np.uint32)

    # Calculate activity intensity levels (0-19 scale)
    activity_positive = activity[activity > 0]
    max_activity_clip = (
        np.percentile(activity_positive, 95)
        if len(activity_positive) > 0  #
        else 1
    )
    activity_levels = (  #
        np.ceil(np.clip(activity / max_activity_clip, 0, 1) * 19).astype(np.uint8)
    )

    chart_proto = UserActivityChart(
        start_date=dates_range[0].isoformat(),
        values=activity.tolist(),
        levels=activity_levels.tobytes(),
    )

    return {
        'activity_chart': urlsafe_b64encode(chart_proto.SerializeToString()).decode(),
        'activity_max': int(activity.max()),
        'activity_sum': int(activity.sum()),
        'activity_days': int((activity > 0).sum()),
    }
