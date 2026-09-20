from django.db import models
from django.conf import settings
from django.utils import timezone


class ProjectStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    COMPLETED = 'COMPLETED', 'Completed'
    ON_HOLD = 'ON_HOLD', 'On Hold'
    ARCHIVED = 'ARCHIVED', 'Archived'


class Project(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owned_projects',
        db_index=True
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=ProjectStatus.choices,
        default=ProjectStatus.ACTIVE,
        db_index=True
    )
    priority = models.PositiveIntegerField(default=5)  # 1 (lowest) to 10 (highest)
    start_date = models.DateField(default=timezone.now)
    deadline = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'projects'
        ordering = ['deadline', '-priority']
        indexes = [
            models.Index(fields=['owner']),
            models.Index(fields=['status']),
            models.Index(fields=['deadline']),
            models.Index(fields=['owner', 'status']),
            models.Index(fields=['owner', 'deadline']),
        ]

    def __str__(self):
        return f"{self.name} ({self.status})"

    def archive(self):
        self.status = ProjectStatus.ARCHIVED
        self.archived_at = timezone.now()
        self.save(update_fields=['status', 'archived_at', 'updated_at'])
