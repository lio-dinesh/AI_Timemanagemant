from celery import shared_task
import logging
from django.utils import timezone
from apps.accounts.models import User
from apps.analytics.services.aggregator import ProductivityAggregator
from apps.analytics.services.reports import ReportingService

logger = logging.getLogger(__name__)

@shared_task
def calculate_daily_productivity(user_id, date_str):
    """
    Asynchronous Celery task to recalculate a single user's productivity summary for a date.
    """
    try:
        record = ProductivityAggregator.aggregate_user_date(user_id, date_str)
        logger.info("Recalculated productivity for user %s on %s: Score %.1f", user_id, date_str, record.productivity_score)
        return record.productivity_score
    except Exception as exc:
        logger.error("Error in calculate_daily_productivity for user %s on %s: %s", user_id, date_str, str(exc))
        return None

@shared_task
def run_all_users_daily_aggregation():
    """
    Nightly Celery Beat task aggregating today's stats for all active users.
    """
    today = timezone.localdate()
    user_ids = User.objects.filter(is_active=True).values_list('id', flat=True)
    count = 0
    for uid in user_ids:
        ProductivityAggregator.aggregate_user_date(uid, today)
        count += 1
    logger.info("run_all_users_daily_aggregation finished for %s users on %s", count, today)
    return count
