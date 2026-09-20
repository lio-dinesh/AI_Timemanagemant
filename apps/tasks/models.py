from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class TaskStatus(models.TextChoices):
    TODO = 'TODO', 'To Do'
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    BLOCKED = 'BLOCKED', 'Blocked'
    COMPLETED = 'COMPLETED', 'Completed'
    CANCELLED = 'CANCELLED', 'Cancelled'


class Task(models.Model):
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks',
        db_index=True
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assigned_tasks',
        db_index=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_tasks',
        db_index=True
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')

    status = models.CharField(
        max_length=20,
        choices=TaskStatus.choices,
        default=TaskStatus.TODO,
        db_index=True
    )
    priority = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Priority rank from 1 (lowest) to 10 (highest)"
    )
    progress = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Progress from 0% to 100%"
    )

    estimated_seconds = models.PositiveIntegerField(
        default=3600,
        help_text="Estimated completion time in seconds"
    )
    actual_seconds = models.PositiveIntegerField(
        default=0,
        help_text="Cached aggregate of closed time entries in seconds"
    )

    deadline = models.DateTimeField(db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    category = models.CharField(max_length=64, default='General', db_index=True)
    tags = models.JSONField(default=list, blank=True)

    is_recurring = models.BooleanField(default=False)
    recurrence_rule = models.CharField(max_length=128, null=True, blank=True)
    recurrence_until = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tasks'
        ordering = ['deadline', '-priority']
        indexes = [
            models.Index(fields=['project']),
            models.Index(fields=['assigned_to']),
            models.Index(fields=['created_by']),
            models.Index(fields=['status']),
            models.Index(fields=['deadline']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['assigned_to', 'deadline']),
            models.Index(fields=['project', 'status']),
        ]

    def __str__(self):
        return f"[{self.status}] {self.title} (P{self.priority})"

    @property
    def is_overdue(self):
        if self.status in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
            return False
        return self.deadline < timezone.now()

    @property
    def actual_hours(self):
        return round(self.actual_seconds / 3600, 2)

    @property
    def estimated_hours(self):
        return round(self.estimated_seconds / 3600, 2)

    def mark_completed(self):
        self.status = TaskStatus.COMPLETED
        self.progress = 100
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'progress', 'completed_at', 'updated_at'])
