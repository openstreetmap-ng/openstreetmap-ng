from datetime import UTC, datetime, timedelta
from itertools import cycle
from typing import TypedDict

import cython
import numpy as np

from app.lib.date_utils import format_short_date, get_month_name, get_weekday_name, utcnow
from app.limits import USER_ACTIVITY_CHART_WEEKS
from app.models.db.user import UserId
from app.queries.changeset_query import ChangesetQuery


class UserActivitySummaryRow(TypedDict):
    level: int
    """Activity indicator level."""
    value: int
    """Raw activity count."""
    date: str
    """Human-readable date."""


class UserActivitySummaryResult(TypedDict):
    activity_months: list[str | None]
    """Names of the months (per week, where only the first occurrence has value)."""
    activity_weekdays: list[str]
    """Names of the weekdays."""
    activity_rows: list[list[UserActivitySummaryRow]]
    """Activity data in [day_of_week][week_number] format."""
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
    activity_per_day = await ChangesetQuery.count_per_day_by_user_id(user_id, created_since)

    # Generate continuous date range
    dates_range: list[datetime] = np.arange(
        created_since,
        today + timedelta(days=1),
        timedelta(days=1),
        'datetime64[D]',
    ).tolist()

    # Map activity counts to each date
    activity = np.array(
        [activity_per_day.get(date.replace(tzinfo=UTC), 0) for date in dates_range],
        np.uint32,
    )

    # Calculate activity intensity levels (0-19 scale)
    activity_positive = activity[activity > 0]
    max_activity_clip = np.percentile(activity_positive, 95) if activity_positive.size else 1
    activity_levels = np.ceil(np.clip(activity / max_activity_clip, 0, 1) * 19).astype(np.uint8)

    # Create weekday labels (showing every other day)
    i: cython.Py_ssize_t  # noqa: F842
    weekdays = [get_weekday_name(date, short=True) if i % 2 == 1 else '' for i, date in enumerate(dates_range[:7])]

    # Initialize activity grid (7 rows for days of the week)
    day_rows: list[list[UserActivitySummaryRow]] = [[] for _ in range(7)]
    months: list[str | None] = []

    day_row: list[UserActivitySummaryRow]
    level: int
    value: int
    date: datetime

    for day_row, level, value, date in zip(
        cycle(day_rows),
        activity_levels.tolist(),  # type: ignore
        activity.tolist(),  # type: ignore
        dates_range,
    ):
        day_row.append({'level': level, 'value': value, 'date': format_short_date(date)})

        # Track month changes for month labels
        if date.day == 1:
            # Fill gaps with None for weeks without month labels
            months.extend([None] * (len(day_row) - len(months)))
            months.append(get_month_name(date, short=True))

    return {
        'activity_months': months,
        'activity_weekdays': weekdays,
        'activity_rows': day_rows,
        'activity_max': int(activity.max()),
        'activity_sum': int(activity.sum()),
        'activity_days': int((activity > 0).sum()),
    }
