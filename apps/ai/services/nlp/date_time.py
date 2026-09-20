import re
import datetime
from typing import Optional, Tuple
from django.utils import timezone
import zoneinfo


class DateTimeNormalizer:
    @staticmethod
    def get_user_now(user) -> datetime.datetime:
        """Returns the current timezone-aware datetime adjusted for user's timezone."""
        user_tz_name = getattr(user, 'timezone', 'UTC') or 'UTC'
        try:
            tz = zoneinfo.ZoneInfo(user_tz_name)
        except Exception:
            tz = zoneinfo.ZoneInfo("UTC")
        return timezone.now().astimezone(tz)

    @staticmethod
    def normalize_date(text: str, user) -> Tuple[Optional[datetime.date], Optional[str]]:
        """
        Extracts and normalizes target date from text.
        Returns (date_obj, date_str_iso).
        """
        lower = text.lower()
        now = DateTimeNormalizer.get_user_now(user)
        today = now.date()

        if "tomorrow" in lower or "tomorow" in lower or "tommorow" in lower:
            d = today + datetime.timedelta(days=1)
            return d, d.isoformat()

        if "yesterday" in lower:
            d = today - datetime.timedelta(days=1)
            return d, d.isoformat()

        if "today" in lower:
            return today, today.isoformat()

        # Check for weekday (e.g. "next monday", "on friday")
        weekdays = {
            "monday": 0, "tuesday": 1, "wednesday": 2,
            "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6
        }
        for name, idx in weekdays.items():
            if name in lower:
                days_ahead = idx - today.weekday()
                if days_ahead <= 0 or "next" in lower:
                    days_ahead += 7
                d = today + datetime.timedelta(days=days_ahead)
                return d, d.isoformat()

        # Date pattern YYYY-MM-DD
        iso_match = re.search(r'\b(20\d\d)-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b', text)
        if iso_match:
            try:
                d = datetime.date.fromisoformat(iso_match.group(0))
                return d, d.isoformat()
            except ValueError:
                pass

        return None, None

    @staticmethod
    def normalize_time(text: str, user) -> Tuple[Optional[datetime.time], Optional[str]]:
        """
        Extracts and normalizes target time from text.
        Returns (time_obj, time_window_label).
        """
        lower = text.lower()

        # Specific time regex: 10am, 10:30am, 2pm, 14:00
        time_match = re.search(r'\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b', lower)
        if time_match and (time_match.group(3) or ":" in time_match.group(0) or "at " in time_match.group(0)):
            h = int(time_match.group(1))
            m = int(time_match.group(2) or 0)
            meridiem = (time_match.group(3) or "").lower()

            if meridiem == 'pm' and h < 12:
                h += 12
            elif meridiem == 'am' and h == 12:
                h = 0

            if 0 <= h <= 23 and 0 <= m <= 59:
                t = datetime.time(h, m)
                window = "MORNING" if h < 12 else ("AFTERNOON" if h < 17 else "EVENING")
                return t, window

        # General windows
        if "morning" in lower:
            return datetime.time(10, 0), "MORNING"
        if "afternoon" in lower:
            return datetime.time(14, 0), "AFTERNOON"
        if "evening" in lower:
            return datetime.time(17, 30), "EVENING"
        if "noon" in lower:
            return datetime.time(12, 0), "AFTERNOON"

        return None, None

    @staticmethod
    def normalize_duration(text: str) -> Optional[int]:
        """Extracts duration in minutes."""
        lower = text.lower()
        hr_match = re.search(r'(\d+)\s*(?:h|hr|hours?)\b', lower)
        min_match = re.search(r'(\d+)\s*(?:m|min|mins|minutes?)\b', lower)
        half_hr = re.search(r'\bhalf\s+an?\s+hour\b', lower)

        if half_hr:
            return 30
        if hr_match and min_match:
            return int(hr_match.group(1)) * 60 + int(min_match.group(1))
        if hr_match:
            return int(hr_match.group(1)) * 60
        if min_match:
            return int(min_match.group(1))

        # "for two hours" / words
        word_hours = {"one": 60, "two": 120, "three": 180, "four": 240}
        for word, mins in word_hours.items():
            if f"{word} hour" in lower:
                return mins

        return None

    @staticmethod
    def normalize_period(text: str) -> str:
        """Determines analytical period."""
        lower = text.lower()
        if "yesterday" in lower:
            return "YESTERDAY"
        if "last week" in lower:
            return "LAST_WEEK"
        if "this week" in lower or "week" in lower:
            return "THIS_WEEK"
        if "this month" in lower or "month" in lower:
            return "THIS_MONTH"
        return "TODAY"
