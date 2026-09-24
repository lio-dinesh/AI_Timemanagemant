import os
import json
import re
import logging
import requests
from django.conf import settings

logger = logging.getLogger('apps.ai.llm')


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


class GeminiLLMProvider(BaseLLMProvider):
    """
    Google Gemini LLM provider using the Google Generative Language REST API.
    Defaults to models/gemini-3.6-flash with graceful fallback to mock on network failure.
    """
    def __init__(self, api_key: str, model: str = None):
        self.api_key = api_key
        self.model = model or getattr(settings, 'GEMINI_MODEL', 'gemini-3.6-flash')
        self.fallback = MockLLMProvider()

    def complete(self, prompt: str, system: str = "") -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ]
        }

        if system:
            payload["systemInstruction"] = {
                "parts": [{"text": system}]
            }

        headers = {
            "Content-Type": "application/json"
        }

        import time
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=4)
            if response.status_code == 200:
                data = response.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        text_response = parts[0].get("text", "").strip()
                        # Clean markdown json fences if present
                        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text_response)
                        if match:
                            return match.group(1).strip()
                        brace_match = re.search(r'(\{[\s\S]*\})', text_response)
                        if brace_match:
                            return brace_match.group(1).strip()
                        return text_response

            logger.warning("Gemini API call failed (%s): %s. Falling back to Mock.", response.status_code, response.text[:200])
        except Exception as exc:
            logger.warning("Gemini API exception (%s). Falling back to Mock.", exc)

        return self.fallback.complete(prompt, system)


class OpenAILLMProvider(BaseLLMProvider):
    """
    OpenAI LLM provider using the OpenAI Chat Completions REST API.
    """
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model
        self.fallback = MockLLMProvider()

    def complete(self, prompt: str, system: str = "") -> str:
        url = "https://api.openai.com/v1/chat/completions"
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(
                url,
                json={"model": self.model, "messages": messages, "temperature": 0.2},
                headers=headers,
                timeout=12
            )
            if response.status_code == 200:
                data = response.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "").strip()
            logger.warning("OpenAI API call failed (%s). Falling back to Mock.", response.status_code)
        except Exception as exc:
            logger.warning("OpenAI API exception (%s). Falling back to Mock.", exc)

        return self.fallback.complete(prompt, system)


def get_llm_provider() -> BaseLLMProvider:
    import sys
    provider_name = getattr(settings, 'AI_PROVIDER', 'mock').lower()
    api_key = getattr(settings, 'AI_API_KEY', '') or os.environ.get('AI_API_KEY', '')

    if 'test' in sys.argv or not api_key or provider_name == 'mock':
        return MockLLMProvider()

    if provider_name == 'gemini':
        return GeminiLLMProvider(api_key=api_key)

    if provider_name == 'openai':
        return OpenAILLMProvider(api_key=api_key)

    return MockLLMProvider()
