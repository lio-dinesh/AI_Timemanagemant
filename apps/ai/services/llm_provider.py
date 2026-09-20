import os
import json
import re
from django.conf import settings

class BaseLLMProvider:
    def complete(self, prompt: str, system: str = "") -> str:
        raise NotImplementedError


class MockLLMProvider(BaseLLMProvider):
    """
    Built-in heuristic & regex mock provider for offline development, local demos, and testing.
    """
    def complete(self, prompt: str, system: str = "") -> str:
        prompt_lower = prompt.lower()
        if "schedule" in prompt_lower:
            return json.dumps({
                "action": "SCHEDULE_TASK",
                "title": "Scheduled Task via NLP",
                "start_time": "10:00",
                "duration_minutes": 60,
                "confidence": 0.88
            })
        elif "remind" in prompt_lower:
            return json.dumps({
                "action": "CREATE_REMINDER",
                "target": "meeting",
                "minutes_before": 30,
                "confidence": 0.92
            })
        elif "most time-consuming" in prompt_lower or "summary" in prompt_lower:
            return json.dumps({
                "action": "QUERY_ANALYTICS",
                "query_type": "LONGEST_TASK",
                "confidence": 0.85
            })
        return json.dumps({
            "action": "UNKNOWN",
            "confidence": 0.50
        })


def get_llm_provider() -> BaseLLMProvider:
    provider_name = getattr(settings, 'AI_PROVIDER', 'mock').lower()
    api_key = getattr(settings, 'AI_API_KEY', '') or os.environ.get('AI_API_KEY', '')

    # Return Mock if no API key is present
    if not api_key or provider_name == 'mock':
        return MockLLMProvider()

    # Placeholders for pluggable providers
    return MockLLMProvider()
