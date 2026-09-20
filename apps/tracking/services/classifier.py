from apps.tracking.models import ProductivityCategory

PRODUCTIVE_KEYWORDS = {'code', 'dev', 'git', 'terminal', 'python', 'django', 'docs', 'stack', 'study', 'jira', 'confluence'}
DISTRACTION_KEYWORDS = {'youtube', 'netflix', 'facebook', 'twitter', 'instagram', 'tiktok', 'reddit', 'game', 'gaming', 'twitch'}
NEUTRAL_KEYWORDS = {'slack', 'teams', 'zoom', 'email', 'outlook', 'gmail', 'calendar'}

class ProductivityClassifier:
    @staticmethod
    def classify(activity_type="", app_name="", domain_name=""):
        text = f"{activity_type} {app_name} {domain_name}".lower()

        if any(w in text for w in DISTRACTION_KEYWORDS):
            return ProductivityCategory.DISTRACTION, 0.90
        elif any(w in text for w in PRODUCTIVE_KEYWORDS):
            return ProductivityCategory.PRODUCTIVE, 0.95
        elif any(w in text for w in NEUTRAL_KEYWORDS):
            return ProductivityCategory.NEUTRAL, 0.85
        else:
            return ProductivityCategory.PRODUCTIVE, 0.70  # Default assumed productive during work sessions
