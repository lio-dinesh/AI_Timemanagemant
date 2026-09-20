import urllib.parse
from datetime import datetime
from django.utils import timezone
from apps.scheduling.models import ScheduleEvent, ScheduleEventStatus


class CalendarSyncService:
    """
    Generates RFC 5545 compliant iCalendar (.ics) files and direct web calendar
    intent links for Google Calendar, Outlook Web, and Office 365.
    """

    @classmethod
    def generate_ics_content(cls, events, calendar_name="AI TimeSync Calendar") -> str:
        """
        Builds a valid iCalendar (.ics) string containing the specified schedule events.
        """
        now_str = timezone.now().strftime("%Y%m%dT%H%M%SZ")
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//AI Time Management//AI TimeSync v1.0//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            f"X-WR-CALNAME:{calendar_name}",
            "X-WR-TIMEZONE:UTC",
        ]

        for event in events:
            if event.status == ScheduleEventStatus.CANCELLED:
                continue

            dtstart = event.start_at.strftime("%Y%m%dT%H%M%SZ")
            dtend = event.end_at.strftime("%Y%m%dT%H%M%SZ")
            uid = f"aitimesync-event-{event.id}-{dtstart}@aitimemanagement.com"
            summary = cls._escape_ics_text(event.title)
            desc = cls._escape_ics_text(event.description or f"AI TimeSync Event [{event.event_type}]")
            location = cls._escape_ics_text(event.location or event.meeting_url or "")

            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{now_str}",
                f"DTSTART:{dtstart}",
                f"DTEND:{dtend}",
                f"SUMMARY:{summary}",
                f"DESCRIPTION:{desc}",
                f"LOCATION:{location}",
                "STATUS:CONFIRMED",
                "TRANSP:OPAQUE",
                "END:VEVENT"
            ])

        lines.append("END:VCALENDAR")
        return "\r\n".join(lines) + "\r\n"

    @staticmethod
    def _escape_ics_text(text: str) -> str:
        if not text:
            return ""
        return (
            text.replace("\\", "\\\\")
            .replace(";", "\\;")
            .replace(",", "\\,")
            .replace("\r\n", "\\n")
            .replace("\n", "\\n")
        )

    @classmethod
    def get_google_calendar_url(cls, event: ScheduleEvent) -> str:
        """
        Constructs a 1-click Google Calendar web creation URL.
        """
        dtstart = event.start_at.strftime("%Y%m%dT%H%M%SZ")
        dtend = event.end_at.strftime("%Y%m%dT%H%M%SZ")
        params = {
            "action": "TEMPLATE",
            "text": event.title,
            "dates": f"{dtstart}/{dtend}",
            "details": event.description or f"Scheduled via AI TimeSync [{event.event_type}]",
            "location": event.location or event.meeting_url or "",
        }
        return f"https://calendar.google.com/calendar/render?{urllib.parse.urlencode(params)}"

    @classmethod
    def get_outlook_calendar_url(cls, event: ScheduleEvent) -> str:
        """
        Constructs a 1-click Outlook Live / Office 365 web creation URL.
        """
        params = {
            "path": "/calendar/action/compose",
            "rru": "addevent",
            "subject": event.title,
            "startdt": event.start_at.isoformat(),
            "enddt": event.end_at.isoformat(),
            "body": event.description or f"Scheduled via AI TimeSync [{event.event_type}]",
            "location": event.location or event.meeting_url or "",
        }
        return f"https://outlook.live.com/calendar/0/deeplink/compose?{urllib.parse.urlencode(params)}"
