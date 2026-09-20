from celery import shared_task
import logging
from apps.accounts.models import User
from apps.ai.services.scheduler import SchedulingOptimizer
from apps.ai.services.predictor import ProductivityPredictor
from apps.ai.services.anomaly import AnomalyDetector
from apps.ai.services.recommender import RecommenderService

logger = logging.getLogger(__name__)

@shared_task
def generate_ai_schedule(user_id):
    try:
        user = User.objects.get(id=user_id)
        insights = SchedulingOptimizer.optimize_schedule_for_user(user)
        logger.info("Generated %s AI schedule recommendations for user %s", len(insights), user_id)
        return len(insights)
    except User.DoesNotExist:
        return 0

@shared_task
def run_productivity_prediction(user_id):
    try:
        user = User.objects.get(id=user_id)
        insight = ProductivityPredictor.predict_user_productivity(user)
        return insight.score
    except User.DoesNotExist:
        return None

@shared_task
def run_periodic_anomaly_detection():
    """
    Celery Beat task checking active users for excessive idle or long timers.
    """
    users = User.objects.filter(is_active=True)
    total_anomalies = 0
    for u in users:
        anomalies = AnomalyDetector.detect_user_anomalies(u)
        total_anomalies += len(anomalies)
    logger.info("run_periodic_anomaly_detection: %s anomalies detected across users.", total_anomalies)
    return total_anomalies
