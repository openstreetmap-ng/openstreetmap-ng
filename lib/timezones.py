from datetime import datetime

import pytz

TZINFOS = {}

# range in minutes from UTC-12:00 to UTC+14:00
for i in range(-720, 840, 60):
    offset = int(i / 60)
    tz = pytz.FixedOffset(i)
    TZINFOS[f'UTC{offset:+d}'] = tz  # frmat as UTC-1, UTC+1, etc.
    TZINFOS[f'UTC{offset:+03d}'] = tz  # format as UTC-01, UTC+01, etc.
    TZINFOS[f'UTC{offset:+03d}00'] = tz  # format as UTC-0100, UTC+0100, etc.
    TZINFOS[f'{offset:+03d}'] = tz  # format as -01, +01, etc.
    TZINFOS[f'{offset:+03d}00'] = tz  # format as -0100, +0100, etc.

for tz in pytz.all_timezones:
    try:
        tz = pytz.timezone(tz)
        now = datetime.now(tz)
        abbrev = now.strftime('%Z')
        TZINFOS[abbrev] = tz
    except Exception:  # noqa: S110
        pass
