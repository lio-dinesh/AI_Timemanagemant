import inspect
import logging
from typing import Callable, Dict, Any, Optional
from apps.ai.schemas import EntitySchema, ExecutionResultSchema
from apps.ai.services.nlp.intents import IntentType, INTENT_REGISTRY

from .task_tool import TaskTool
from .project_tool import ProjectTool
from .time_tool import TimeTool
from .schedule_tool import ScheduleTool
from .reminder_tool import ReminderTool
from .notification_tool import NotificationTool
from .analytics_tool import AnalyticsTool
from .report_tool import ReportTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Controlled tool execution registry.
    Strictly maps canonical IntentType to authorized tool methods.
    The LLM never directly invokes database code; all actions route through this registry.
    """

    _REGISTRY: Dict[IntentType, Callable] = {
        # Tasks
        IntentType.TASK_CREATE: TaskTool.create_task,
        IntentType.TASK_UPDATE: TaskTool.update_task,
        IntentType.TASK_DELETE: TaskTool.delete_task,
        IntentType.TASK_COMPLETE: TaskTool.complete_task,
        IntentType.TASK_SEARCH: TaskTool.search_tasks,
        IntentType.TASK_LIST: TaskTool.list_tasks,
        IntentType.TASK_ASSIGN: TaskTool.assign_task,

        # Projects
        IntentType.PROJECT_CREATE: ProjectTool.create_project,
        IntentType.PROJECT_UPDATE: ProjectTool.update_project,
        IntentType.PROJECT_SEARCH: ProjectTool.search_projects,

        # Time & Timer
        IntentType.TIMER_START: TimeTool.start_timer,
        IntentType.TIMER_STOP: TimeTool.stop_timer,
        IntentType.TIME_ENTRY_CREATE: TimeTool.create_manual_entry,
        IntentType.TIME_HISTORY: TimeTool.get_history,
        IntentType.TIME_ANALYSIS: TimeTool.analyze_time,

        # Scheduling
        IntentType.SCHEDULE_CREATE: ScheduleTool.create_event,
        IntentType.SCHEDULE_UPDATE: ScheduleTool.update_event,
        IntentType.SCHEDULE_DELETE: ScheduleTool.delete_event,
        IntentType.SCHEDULE_SEARCH: ScheduleTool.get_schedule,
        IntentType.SCHEDULE_CONFLICT_CHECK: ScheduleTool.check_conflicts,

        # Reminders
        IntentType.REMINDER_CREATE: ReminderTool.create_reminder,
        IntentType.REMINDER_DELETE: ReminderTool.delete_reminder,
        IntentType.REMINDER_LIST: ReminderTool.list_reminders,

        # Notifications
        IntentType.NOTIFICATION_LIST: NotificationTool.list_notifications,
        IntentType.NOTIFICATION_READ: NotificationTool.mark_as_read,

        # Productivity Analytics
        IntentType.PRODUCTIVITY_SUMMARY: AnalyticsTool.get_summary,
        IntentType.PRODUCTIVITY_TREND: AnalyticsTool.get_trend,
        IntentType.PRODUCTIVITY_PATTERN: AnalyticsTool.get_patterns,

        # Reports
        IntentType.REPORT_GENERATE: ReportTool.generate_and_send,
        IntentType.REPORT_SUMMARY: ReportTool.get_summary,

        # AI Operations
        IntentType.AI_SCHEDULE: ScheduleTool.plan_day,
        IntentType.AI_TIME_ALLOCATION: ScheduleTool.get_free_slots,
        IntentType.AI_RECOMMENDATION: AnalyticsTool.get_recommendations,
        IntentType.ANOMALY_ANALYSIS: AnalyticsTool.check_anomalies,

        # System
        IntentType.HELP: TaskTool.get_help,
        IntentType.UNKNOWN: TaskTool.unknown_command,
    }

    @classmethod
    def get_tool(cls, intent: IntentType) -> Optional[Callable]:
        return cls._REGISTRY.get(intent)

    @classmethod
    def execute(
        cls,
        intent: IntentType,
        user: Any,
        entities: EntitySchema,
        resolved_entity: Any = None
    ) -> ExecutionResultSchema:
        """
        Executes the registered tool method for the given intent.
        Passes resolved_entity if the tool method accepts it.
        """
        tool_fn = cls.get_tool(intent)
        if not tool_fn:
            logger.error(f"No tool registered for intent: {intent}")
            return ExecutionResultSchema(
                success=False,
                action=intent.value if isinstance(intent, IntentType) else str(intent),
                intent=intent.value if isinstance(intent, IntentType) else str(intent),
                message=f"I don't have an automated tool to execute '{intent}' yet."
            )

        try:
            # Check signature parameters
            sig = inspect.signature(tool_fn)
            kwargs = {}
            if len(sig.parameters) >= 3 or any(
                p.name in ('resolved_task', 'resolved_event', 'resolved_project', 'resolved_entity')
                for p in sig.parameters.values()
            ):
                # Pass resolved entity to the third param
                param_names = list(sig.parameters.keys())
                if len(param_names) >= 3:
                    third_param = param_names[2]
                    kwargs[third_param] = resolved_entity
                return tool_fn(user, entities, **kwargs)
            else:
                return tool_fn(user, entities)

        except Exception as e:
            logger.exception(f"Error executing tool for intent {intent}: {e}")
            return ExecutionResultSchema(
                success=False,
                action=intent.value if isinstance(intent, IntentType) else str(intent),
                intent=intent.value if isinstance(intent, IntentType) else str(intent),
                message=f"An error occurred while executing the action: {str(e)}"
            )
