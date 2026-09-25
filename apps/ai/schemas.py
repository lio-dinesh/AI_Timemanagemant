import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from enum import Enum


class CommandSource(str, Enum):
    TEXT = "TEXT"
    VOICE = "VOICE"


@dataclass
class EntitySchema:
    task_id: Optional[int] = None
    task_title: Optional[str] = None
    project_id: Optional[int] = None
    project_title: Optional[str] = None
    date: Optional[str] = None
    time_window: Optional[str] = None  # "MORNING", "AFTERNOON", "EVENING"
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_minutes: Optional[int] = None
    priority: Optional[int] = None
    status: Optional[str] = None
    category: Optional[str] = None
    reminder_minutes: Optional[int] = None
    user_reference: Optional[str] = None
    period: Optional[str] = None  # "TODAY", "YESTERDAY", "THIS_WEEK", "LAST_WEEK", "THIS_MONTH"
    group_by: Optional[str] = None  # "PROJECT", "DAY", "CATEGORY"
    format: Optional[str] = "HTML"  # "HTML", "CSV", "JSON"
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ActionPreviewSchema:
    action_type: str
    title: str
    description: str
    diff_summary: Dict[str, Any]
    confirm_token: str
    expires_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionResultSchema:
    success: bool
    action: str
    intent: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    audit_logged: bool = False
    requires_confirmation: bool = False
    preview: Optional[ActionPreviewSchema] = None
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        if self.preview:
            res["preview"] = self.preview.to_dict()
        return res


@dataclass
class CommandSchema:
    intent: str
    raw_text: str
    normalized_text: str
    user_id: int
    entities: EntitySchema = field(default_factory=EntitySchema)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    confidence: float = 1.0
    risk_level: str = "LOW_RISK_WRITE"
    requires_confirmation: bool = False
    confirmation_token: Optional[str] = None
    source: CommandSource = CommandSource.TEXT

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["entities"] = self.entities.to_dict()
        res["source"] = self.source.value
        return res


@dataclass
class ContextSessionSchema:
    conversation_id: str
    user_id: int
    last_intent: Optional[str] = None
    pending_action: Optional[str] = None
    pending_entities: Dict[str, Any] = field(default_factory=dict)
    candidate_entities: List[Dict[str, Any]] = field(default_factory=list)
    confirmation_required: bool = False
    confirmation_token: Optional[str] = None
    last_task_id: Optional[int] = None
    last_task_title: Optional[str] = None
    last_event_id: Optional[int] = None
    last_event_title: Optional[str] = None
    dialogue_history: List[Dict[str, str]] = field(default_factory=list)
    created_at: Optional[str] = None
    expires_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AnalyticsQueryPlanSchema:
    metric: str  # "tracked_time", "productive_time", "score", "overdue_count"
    period: str  # "TODAY", "THIS_WEEK", "LAST_WEEK", "THIS_MONTH"
    group_by: Optional[str] = None  # "PROJECT", "DAY", "CATEGORY"
    filters: Dict[str, Any] = field(default_factory=dict)
    start_date: Optional[str] = None
    end_date: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
