import logging
from apps.tracking.models import ProductivityCategory

logger = logging.getLogger('apps.tracking.classifier')

PRODUCTIVE_KEYWORDS = {
    'code', 'dev', 'git', 'terminal', 'python', 'django', 'docs', 'stack', 'study',
    'jira', 'confluence', 'ide', 'vscode', 'mysql', 'sql', 'test', 'debug', 'api'
}
DISTRACTION_KEYWORDS = {
    'youtube', 'netflix', 'facebook', 'twitter', 'instagram', 'tiktok', 'reddit',
    'game', 'gaming', 'twitch', 'steam', 'discord', 'reels', 'shorts'
}
NEUTRAL_KEYWORDS = {
    'slack', 'teams', 'zoom', 'email', 'outlook', 'gmail', 'calendar', 'meet', 'sync', 'standup'
}

TRAINING_CORPUS = [
    # PRODUCTIVE
    ("writing django models and database migrations", ProductivityCategory.PRODUCTIVE),
    ("python code development in vs code visual studio editor", ProductivityCategory.PRODUCTIVE),
    ("debugging backend api test suite and fixing bugs", ProductivityCategory.PRODUCTIVE),
    ("git commit push branch pull request review on github", ProductivityCategory.PRODUCTIVE),
    ("mysql workbench query optimization and index tuning", ProductivityCategory.PRODUCTIVE),
    ("reading architectural documentation on confluence and notion", ProductivityCategory.PRODUCTIVE),
    ("docker container build and deployment kubernetes config", ProductivityCategory.PRODUCTIVE),
    ("jira issue tracking sprint backlog grooming and planning", ProductivityCategory.PRODUCTIVE),
    ("frontend react htmx template styling and bootstrap css", ProductivityCategory.PRODUCTIVE),
    ("writing unit tests and integration tests with pytest", ProductivityCategory.PRODUCTIVE),
    ("terminal powershell bash command line execution", ProductivityCategory.PRODUCTIVE),
    ("data science machine learning model training in scikit-learn", ProductivityCategory.PRODUCTIVE),
    ("researching technical documentation on stackoverflow and developer docs", ProductivityCategory.PRODUCTIVE),
    ("submitting code changes and answering code review comments", ProductivityCategory.PRODUCTIVE),

    # NEUTRAL
    ("slack team daily standup channel messages and pings", ProductivityCategory.NEUTRAL),
    ("microsoft teams company all hands meeting and status call", ProductivityCategory.NEUTRAL),
    ("zoom client video conference call with client stakeholders", ProductivityCategory.NEUTRAL),
    ("reading corporate emails and announcements on microsoft outlook", ProductivityCategory.NEUTRAL),
    ("google calendar schedule planning and meeting invitations", ProductivityCategory.NEUTRAL),
    ("answering customer support tickets on zendesk helpdesk", ProductivityCategory.NEUTRAL),
    ("google meet one on one manager catchup and alignment", ProductivityCategory.NEUTRAL),
    ("gmail inbox triaging and email drafting to partners", ProductivityCategory.NEUTRAL),
    ("daily project check-in with product manager", ProductivityCategory.NEUTRAL),

    # DISTRACTION
    ("watching youtube trending videos funny compilation and music", ProductivityCategory.DISTRACTION),
    ("netflix streaming movie and tv series binge watching", ProductivityCategory.DISTRACTION),
    ("scrolling facebook newsfeed and friend social posts", ProductivityCategory.DISTRACTION),
    ("twitter x browsing viral tweets memes and political arguments", ProductivityCategory.DISTRACTION),
    ("instagram photo feed stories reels explore page", ProductivityCategory.DISTRACTION),
    ("tiktok short viral video scrolling and entertainment", ProductivityCategory.DISTRACTION),
    ("reddit gaming discussion and meme threads casual browsing", ProductivityCategory.DISTRACTION),
    ("playing games on steam twitch streaming gameplay and esports", ProductivityCategory.DISTRACTION),
    ("online shopping amazon deals cart checkout retail browsing", ProductivityCategory.DISTRACTION),
    ("online browser gaming and casual arcade games", ProductivityCategory.DISTRACTION),
]


class ProductivityClassifier:
    """
    Machine Learning powered activity classifier using Scikit-Learn (TF-IDF + Multinomial Naive Bayes)
    with keyword-heuristic fallback.
    """
    _pipeline = None
    _is_trained = False

    @classmethod
    def _init_pipeline(cls):
        if cls._is_trained and cls._pipeline is not None:
            return

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.naive_bayes import MultinomialNB
            from sklearn.pipeline import Pipeline

            texts = [item[0] for item in TRAINING_CORPUS]
            labels = [item[1] for item in TRAINING_CORPUS]

            cls._pipeline = Pipeline([
                ('tfidf', TfidfVectorizer(ngram_range=(1, 2), stop_words='english', lowercase=True)),
                ('nb', MultinomialNB(alpha=0.5))
            ])
            cls._pipeline.fit(texts, labels)
            cls._is_trained = True
            logger.info("Scikit-Learn ProductivityClassifier pipeline initialized with %d training samples", len(texts))
        except Exception as exc:
            logger.warning("Scikit-Learn initialization failed (%s). Falling back to keyword heuristics.", exc)
            cls._pipeline = None
            cls._is_trained = False

    @classmethod
    def classify(cls, activity_type="", app_name="", domain_name=""):
        """
        Classifies an activity into PRODUCTIVE, NEUTRAL, or DISTRACTION.
        Returns a tuple: (ProductivityCategory, confidence_score)
        """
        text = f"{activity_type} {app_name} {domain_name}".strip().lower()

        if not text:
            return ProductivityCategory.PRODUCTIVE, 0.70

        # Attempt Scikit-Learn prediction
        cls._init_pipeline()

        if cls._pipeline is not None:
            try:
                probs = cls._pipeline.predict_proba([text])[0]
                classes = cls._pipeline.classes_
                best_idx = probs.argmax()
                best_class = classes[best_idx]
                confidence = float(probs[best_idx])

                # If model is sufficiently confident, return ML prediction
                if confidence >= 0.45:
                    return best_class, round(confidence, 2)
            except Exception as e:
                logger.debug("ML prediction error (%s), using keyword heuristic", e)

        # Keyword Heuristic Fallback
        if any(w in text for w in DISTRACTION_KEYWORDS):
            return ProductivityCategory.DISTRACTION, 0.90
        elif any(w in text for w in PRODUCTIVE_KEYWORDS):
            return ProductivityCategory.PRODUCTIVE, 0.95
        elif any(w in text for w in NEUTRAL_KEYWORDS):
            return ProductivityCategory.NEUTRAL, 0.85

        return ProductivityCategory.PRODUCTIVE, 0.70
