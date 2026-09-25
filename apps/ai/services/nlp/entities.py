import re
from typing import Dict, Any, Optional
from apps.ai.schemas import EntitySchema
from .date_time import DateTimeNormalizer


class EntityExtractor:
    @staticmethod
    def extract_entities(text: str, user, intent: Optional[str] = None) -> EntitySchema:
        """
        Extracts structured entities from natural language text.
        """
        entities = EntitySchema()
        lower = text.lower()

        # 1. Dates and Times
        d_obj, d_str = DateTimeNormalizer.normalize_date(text, user)
        if d_str:
            entities.date = d_str

        t_obj, window = DateTimeNormalizer.normalize_time(text, user)
        if t_obj:
            entities.start_time = t_obj.strftime("%H:%M")
        if window:
            entities.time_window = window

        # 2. Duration
        duration = DateTimeNormalizer.normalize_duration(text)
        if duration:
            entities.duration_minutes = duration

        # 3. Period
        entities.period = DateTimeNormalizer.normalize_period(text)

        # 4. Task ID extraction (e.g. "task #4", "task 12", "id 5")
        id_match = re.search(r'\btask\s+(?:#|id\s*)?(\d+)\b', lower)
        if not id_match:
            id_match = re.search(r'\b#(\d+)\b', lower)
        if id_match:
            entities.task_id = int(id_match.group(1))

        # 5. Task Title extraction
        title_patterns = [
            r'(?:task\s+called|task\s+named|named|called)\s+[\'"]?([a-zA-Z0-9_\-\s]+?)[\'"]?(?:\s+(?:by|due|for|at|with|on|tomorrow|today)|$)',
            r'(?:create|add)\s+(?:a\s+)?(?:new\s+)?([a-zA-Z0-9_\-]+)\s+task\b',
            r'(?:create|add)\s+(?:a\s+)?(?:new\s+)?task\s+(?:to\s+)?([a-zA-Z0-9_\-\s]+?)(?:\s+(?:by|due|for|at|with|on|tomorrow|today)|$)',
            r'(?:complete|finish|mark)\s+(?:my\s+|the\s+)?([a-zA-Z0-9_\-]+)\s+task\b',
            r'(?:complete|finish|mark)\s+(?:the\s+)?(?:task\s+)?([a-zA-Z0-9_\-\s]+?)(?:\s+task|\s+as\s+completed|\s+as\s+done|$)',
            r'(?:schedule)\s+(?:my\s+)?([a-zA-Z0-9_\-]+)\s+(?:for|tomorrow|today|at|in|on)\b',
            r'(?:schedule)\s+(?:my\s+)?(?:task\s+)?([a-zA-Z0-9_\-\s]+?)(?:\s+task|\s+tomorrow|\s+today|\s+for|\s+at|$)',
        ]
        for pat in title_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                extracted = m.group(1).strip()
                # Clean filler words
                extracted = re.sub(r'^(to\s+|my\s+|the\s+|task\s+)', '', extracted, flags=re.IGNORECASE).strip()
                extracted = re.sub(r'\s+task$', '', extracted, flags=re.IGNORECASE).strip()
                # Strip trailing time/date and assignment keywords
                extracted = re.sub(r'\s+(?:and\s+)?assign(?:ed)?\s+(?:to\s+)?[\w\.-]+(?:@[\w\.-]+\.\w+)?.*$', '', extracted, flags=re.IGNORECASE).strip()
                extracted = re.sub(r'\s+(tomorrow|today|tonight|at|by|due|for|with|on|urgent|priority.*)$', '', extracted, flags=re.IGNORECASE).strip()
                if extracted and len(extracted) > 1 and extracted.lower() not in ('it', 'that', 'this'):
                    entities.task_title = extracted.title()
                    break

        # 6. Priority extraction (e.g. "high priority", "priority 8", "urgent", "low priority")
        if "highest priority" in lower or "top priority" in lower or "critical" in lower:
            entities.priority = 10
        elif "urgent" in lower:
            entities.priority = 9
        elif "high priority" in lower:
            entities.priority = 8
        elif "medium priority" in lower or "normal priority" in lower:
            entities.priority = 5
        elif "low priority" in lower:
            entities.priority = 2

        num_priority = re.search(r'priority\s+(?:level\s*)?(\d{1,2})', lower)
        if num_priority:
            val = int(num_priority.group(1))
            entities.priority = max(1, min(10, val))

        # 7. User Reference / Assignee extraction (e.g. "assign to liodinesh1905@gmail.com", "to dinesh")
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        if email_match:
            entities.user_reference = email_match.group(0).strip()
            entities.extra['assignee_email'] = entities.user_reference
        else:
            assign_match = re.search(r'(?:assign(?:ed)?\s+(?:the\s+)?(?:task\s+)?to|delegate\s+to)\s+([a-zA-Z0-9_\-]+)', text, re.IGNORECASE)
            if assign_match:
                entities.user_reference = assign_match.group(1).strip()

        # 8. Project Name extraction
        proj_match = re.search(r'(?:project\s+called|project\s+named|project)\s+[\'"]?([a-zA-Z0-9_\-\s]+?)[\'"]?(?:\s+(?:by|due|for|at)|$)', text, re.IGNORECASE)
        if proj_match:
            p_name = proj_match.group(1).strip()
            p_name = re.sub(r'^(to\s+|my\s+|the\s+)', '', p_name, flags=re.IGNORECASE).strip()
            if p_name:
                entities.project_title = p_name.title()

        # 9. Reminders & Targets
        if "remind" in lower or "alert" in lower or "notify" in lower:
            # Check "in X minutes"
            in_mins = re.search(r'\bin\s+(\d+)\s*(?:min|mins|minutes?)\b', lower)
            if in_mins:
                entities.reminder_minutes = int(in_mins.group(1))
            else:
                rem_match = re.search(r'(\d+)\s*(?:min|mins|minutes?)\s+before', lower)
                if rem_match:
                    entities.reminder_minutes = int(rem_match.group(1))
                elif "half an hour" in lower:
                    entities.reminder_minutes = 30
                elif duration:
                    entities.reminder_minutes = duration
                else:
                    entities.reminder_minutes = 30

            # Target of reminder: "remind me ... to <action>"
            target_match = re.search(r'(?:to\s+)([a-zA-Z0-9_\-\s]+?)(?:\s+(?:at|on|tomorrow|today)|$)', text, re.IGNORECASE)
            if target_match:
                t_act = target_match.group(1).strip()
                t_act = re.sub(r'\s+(tomorrow|today|tonight|at|on).*$', '', t_act, flags=re.IGNORECASE).strip()
                if t_act:
                    entities.extra['target_title'] = t_act.title()
                    if not entities.task_title:
                        entities.task_title = t_act.title()

        # 10. Format (for reports)
        if "csv" in lower:
            entities.format = "CSV"
        elif "json" in lower:
            entities.format = "JSON"
        elif "email" in lower:
            entities.format = "EMAIL"

        rel_offset = DateTimeNormalizer.normalize_relative_offset(text, user)
        if rel_offset:
            entities.extra['relative_offset'] = rel_offset.isoformat()

        return entities
