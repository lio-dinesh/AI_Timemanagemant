from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional


class RiskLevel(str, Enum):
    READ = "READ"
    LOW_RISK_WRITE = "LOW_RISK_WRITE"
    HIGH_RISK_WRITE = "HIGH_RISK_WRITE"
    DESTRUCTIVE = "DESTRUCTIVE"
    ADMIN = "ADMIN"


class IntentType(str, Enum):
    # Task Management
    TASK_CREATE = "TASK_CREATE"
    TASK_UPDATE = "TASK_UPDATE"
    TASK_DELETE = "TASK_DELETE"
    TASK_COMPLETE = "TASK_COMPLETE"
    TASK_SEARCH = "TASK_SEARCH"
    TASK_LIST = "TASK_LIST"
    TASK_ASSIGN = "TASK_ASSIGN"

    # Project Management
    PROJECT_CREATE = "PROJECT_CREATE"
    PROJECT_UPDATE = "PROJECT_UPDATE"
    PROJECT_SEARCH = "PROJECT_SEARCH"

    # Timer & Time Tracking
    TIMER_START = "TIMER_START"
    TIMER_STOP = "TIMER_STOP"
    TIME_ENTRY_CREATE = "TIME_ENTRY_CREATE"
    TIME_HISTORY = "TIME_HISTORY"
    TIME_ANALYSIS = "TIME_ANALYSIS"

    # Scheduling
    SCHEDULE_CREATE = "SCHEDULE_CREATE"
    SCHEDULE_UPDATE = "SCHEDULE_UPDATE"
    SCHEDULE_DELETE = "SCHEDULE_DELETE"
    SCHEDULE_SEARCH = "SCHEDULE_SEARCH"
    SCHEDULE_CONFLICT_CHECK = "SCHEDULE_CONFLICT_CHECK"

    # Reminders
    REMINDER_CREATE = "REMINDER_CREATE"
    REMINDER_DELETE = "REMINDER_DELETE"
    REMINDER_LIST = "REMINDER_LIST"

    # Notifications
    NOTIFICATION_LIST = "NOTIFICATION_LIST"
    NOTIFICATION_READ = "NOTIFICATION_READ"

    # Productivity Analytics
    PRODUCTIVITY_SUMMARY = "PRODUCTIVITY_SUMMARY"
    PRODUCTIVITY_TREND = "PRODUCTIVITY_TREND"
    PRODUCTIVITY_PATTERN = "PRODUCTIVITY_PATTERN"

    # Reports
    REPORT_GENERATE = "REPORT_GENERATE"
    REPORT_SUMMARY = "REPORT_SUMMARY"

    # AI Operations
    AI_SCHEDULE = "AI_SCHEDULE"
    AI_TIME_ALLOCATION = "AI_TIME_ALLOCATION"
    AI_RECOMMENDATION = "AI_RECOMMENDATION"
    ANOMALY_ANALYSIS = "ANOMALY_ANALYSIS"

    # System
    HELP = "HELP"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class IntentDefinition:
    intent: IntentType
    category: str
    risk: RiskLevel
    requires_confirmation: bool
    allowed_roles: List[str]
    tool_method: str
    description: str


ALL_ROLES = ["EMPLOYEE", "MANAGER", "ADMIN"]
MANAGERS_AND_ADMINS = ["MANAGER", "ADMIN"]
ADMINS_ONLY = ["ADMIN"]

INTENT_REGISTRY: Dict[IntentType, IntentDefinition] = {
    # Tasks
    IntentType.TASK_CREATE: IntentDefinition(
        intent=IntentType.TASK_CREATE,
        category="task",
        risk=RiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="task_tool.create_task",
        description="Creates a new task with title, priority, and deadline."
    ),
    IntentType.TASK_UPDATE: IntentDefinition(
        intent=IntentType.TASK_UPDATE,
        category="task",
        risk=RiskLevel.HIGH_RISK_WRITE,
        requires_confirmation=True,
        allowed_roles=ALL_ROLES,
        tool_method="task_tool.update_task",
        description="Updates an existing task's deadline, priority, or details."
    ),
    IntentType.TASK_DELETE: IntentDefinition(
        intent=IntentType.TASK_DELETE,
        category="task",
        risk=RiskLevel.DESTRUCTIVE,
        requires_confirmation=True,
        allowed_roles=ALL_ROLES,
        tool_method="task_tool.delete_task",
        description="Permanently removes a task after user confirmation."
    ),
    IntentType.TASK_COMPLETE: IntentDefinition(
        intent=IntentType.TASK_COMPLETE,
        category="task",
        risk=RiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="task_tool.complete_task",
        description="Marks an existing task as COMPLETED."
    ),
    IntentType.TASK_SEARCH: IntentDefinition(
        intent=IntentType.TASK_SEARCH,
        category="task",
        risk=RiskLevel.READ,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="task_tool.search_tasks",
        description="Searches tasks by keyword, deadline, or priority."
    ),
    IntentType.TASK_LIST: IntentDefinition(
        intent=IntentType.TASK_LIST,
        category="task",
        risk=RiskLevel.READ,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="task_tool.list_tasks",
        description="Lists active or pending tasks for the current user."
    ),
    IntentType.TASK_ASSIGN: IntentDefinition(
        intent=IntentType.TASK_ASSIGN,
        category="task",
        risk=RiskLevel.HIGH_RISK_WRITE,
        requires_confirmation=True,
        allowed_roles=MANAGERS_AND_ADMINS,
        tool_method="task_tool.assign_task",
        description="Assigns a task to a subordinate team member."
    ),

    # Projects
    IntentType.PROJECT_CREATE: IntentDefinition(
        intent=IntentType.PROJECT_CREATE,
        category="project",
        risk=RiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        allowed_roles=MANAGERS_AND_ADMINS,
        tool_method="project_tool.create_project",
        description="Creates a new project."
    ),
    IntentType.PROJECT_UPDATE: IntentDefinition(
        intent=IntentType.PROJECT_UPDATE,
        category="project",
        risk=RiskLevel.HIGH_RISK_WRITE,
        requires_confirmation=True,
        allowed_roles=MANAGERS_AND_ADMINS,
        tool_method="project_tool.update_project",
        description="Updates project status or deadline."
    ),
    IntentType.PROJECT_SEARCH: IntentDefinition(
        intent=IntentType.PROJECT_SEARCH,
        category="project",
        risk=RiskLevel.READ,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="project_tool.search_projects",
        description="Lists or searches projects."
    ),

    # Timer & Time Tracking
    IntentType.TIMER_START: IntentDefinition(
        intent=IntentType.TIMER_START,
        category="time",
        risk=RiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="time_tool.start_timer",
        description="Starts the authoritative server-side timer."
    ),
    IntentType.TIMER_STOP: IntentDefinition(
        intent=IntentType.TIMER_STOP,
        category="time",
        risk=RiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="time_tool.stop_timer",
        description="Stops active timer and records logged focus duration."
    ),
    IntentType.TIME_ENTRY_CREATE: IntentDefinition(
        intent=IntentType.TIME_ENTRY_CREATE,
        category="time",
        risk=RiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="time_tool.create_manual_entry",
        description="Logs a manual past time entry."
    ),
    IntentType.TIME_HISTORY: IntentDefinition(
        intent=IntentType.TIME_HISTORY,
        category="time",
        risk=RiskLevel.READ,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="time_tool.get_history",
        description="Retrieves recent time tracking history entries."
    ),
    IntentType.TIME_ANALYSIS: IntentDefinition(
        intent=IntentType.TIME_ANALYSIS,
        category="time",
        risk=RiskLevel.READ,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="time_tool.analyze_time",
        description="Aggregates tracked time by period, task, or category."
    ),

    # Scheduling
    IntentType.SCHEDULE_CREATE: IntentDefinition(
        intent=IntentType.SCHEDULE_CREATE,
        category="schedule",
        risk=RiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="schedule_tool.create_event",
        description="Schedules a focus session or calendar event."
    ),
    IntentType.SCHEDULE_UPDATE: IntentDefinition(
        intent=IntentType.SCHEDULE_UPDATE,
        category="schedule",
        risk=RiskLevel.HIGH_RISK_WRITE,
        requires_confirmation=True,
        allowed_roles=ALL_ROLES,
        tool_method="schedule_tool.update_event",
        description="Reschedules an existing calendar event."
    ),
    IntentType.SCHEDULE_DELETE: IntentDefinition(
        intent=IntentType.SCHEDULE_DELETE,
        category="schedule",
        risk=RiskLevel.DESTRUCTIVE,
        requires_confirmation=True,
        allowed_roles=ALL_ROLES,
        tool_method="schedule_tool.delete_event",
        description="Cancels a scheduled event."
    ),
    IntentType.SCHEDULE_SEARCH: IntentDefinition(
        intent=IntentType.SCHEDULE_SEARCH,
        category="schedule",
        risk=RiskLevel.READ,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="schedule_tool.get_schedule",
        description="Queries user calendar events for today or specified date."
    ),
    IntentType.SCHEDULE_CONFLICT_CHECK: IntentDefinition(
        intent=IntentType.SCHEDULE_CONFLICT_CHECK,
        category="schedule",
        risk=RiskLevel.READ,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="schedule_tool.check_conflicts",
        description="Checks if a proposed time slot conflicts with existing events."
    ),

    # Reminders
    IntentType.REMINDER_CREATE: IntentDefinition(
        intent=IntentType.REMINDER_CREATE,
        category="reminder",
        risk=RiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="reminder_tool.create_reminder",
        description="Schedules an alert before an upcoming meeting or task."
    ),
    IntentType.REMINDER_DELETE: IntentDefinition(
        intent=IntentType.REMINDER_DELETE,
        category="reminder",
        risk=RiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="reminder_tool.delete_reminder",
        description="Dismisses or cancels a scheduled reminder."
    ),
    IntentType.REMINDER_LIST: IntentDefinition(
        intent=IntentType.REMINDER_LIST,
        category="reminder",
        risk=RiskLevel.READ,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="reminder_tool.list_reminders",
        description="Lists active reminders."
    ),

    # Notifications
    IntentType.NOTIFICATION_LIST: IntentDefinition(
        intent=IntentType.NOTIFICATION_LIST,
        category="notification",
        risk=RiskLevel.READ,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="notification_tool.list_notifications",
        description="Fetches recent unread or read notifications."
    ),
    IntentType.NOTIFICATION_READ: IntentDefinition(
        intent=IntentType.NOTIFICATION_READ,
        category="notification",
        risk=RiskLevel.LOW_RISK_WRITE,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="notification_tool.mark_as_read",
        description="Marks notifications as read."
    ),

    # Productivity Analytics
    IntentType.PRODUCTIVITY_SUMMARY: IntentDefinition(
        intent=IntentType.PRODUCTIVITY_SUMMARY,
        category="analytics",
        risk=RiskLevel.READ,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="analytics_tool.get_summary",
        description="Returns today's or weekly productivity score rollup."
    ),
    IntentType.PRODUCTIVITY_TREND: IntentDefinition(
        intent=IntentType.PRODUCTIVITY_TREND,
        category="analytics",
        risk=RiskLevel.READ,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="analytics_tool.get_trend",
        description="Compares productivity trends across days or weeks."
    ),
    IntentType.PRODUCTIVITY_PATTERN: IntentDefinition(
        intent=IntentType.PRODUCTIVITY_PATTERN,
        category="analytics",
        risk=RiskLevel.READ,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="analytics_tool.get_patterns",
        description="Analyzes peak productive hours and focus patterns."
    ),

    # Reports
    IntentType.REPORT_GENERATE: IntentDefinition(
        intent=IntentType.REPORT_GENERATE,
        category="report",
        risk=RiskLevel.HIGH_RISK_WRITE,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="report_tool.generate_and_send",
        description="Generates productivity report and dispatches via Brevo email."
    ),
    IntentType.REPORT_SUMMARY: IntentDefinition(
        intent=IntentType.REPORT_SUMMARY,
        category="report",
        risk=RiskLevel.READ,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="report_tool.get_summary",
        description="Retrieves high-level summary report for screen display."
    ),

    # AI Operations
    IntentType.AI_SCHEDULE: IntentDefinition(
        intent=IntentType.AI_SCHEDULE,
        category="ai",
        risk=RiskLevel.HIGH_RISK_WRITE,
        requires_confirmation=True,
        allowed_roles=ALL_ROLES,
        tool_method="schedule_tool.plan_day",
        description="Generates AI schedule optimization for the day."
    ),
    IntentType.AI_TIME_ALLOCATION: IntentDefinition(
        intent=IntentType.AI_TIME_ALLOCATION,
        category="ai",
        risk=RiskLevel.READ,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="schedule_tool.get_free_slots",
        description="Identifies available focus slots in schedule."
    ),
    IntentType.AI_RECOMMENDATION: IntentDefinition(
        intent=IntentType.AI_RECOMMENDATION,
        category="ai",
        risk=RiskLevel.READ,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="analytics_tool.get_recommendations",
        description="Fetches personalized active recommendations."
    ),
    IntentType.ANOMALY_ANALYSIS: IntentDefinition(
        intent=IntentType.ANOMALY_ANALYSIS,
        category="ai",
        risk=RiskLevel.READ,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="analytics_tool.check_anomalies",
        description="Checks for unusual session duration or idle ratio anomalies."
    ),

    # System
    IntentType.HELP: IntentDefinition(
        intent=IntentType.HELP,
        category="system",
        risk=RiskLevel.READ,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="task_tool.get_help",
        description="Returns supported natural language commands."
    ),
    IntentType.UNKNOWN: IntentDefinition(
        intent=IntentType.UNKNOWN,
        category="system",
        risk=RiskLevel.READ,
        requires_confirmation=False,
        allowed_roles=ALL_ROLES,
        tool_method="task_tool.unknown_command",
        description="Fallback for unrecognized natural language inputs."
    ),
}


def get_intent_definition(intent: str) -> Optional[IntentDefinition]:
    try:
        itype = IntentType(intent)
        return INTENT_REGISTRY.get(itype)
    except ValueError:
        return None
