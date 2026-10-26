import json
import os
import httpx
from .base import LLMProvider

class OpenRouterProvider(LLMProvider):
    def __init__(self, config=None):
        super().__init__(config)
        self.url = self.config.get('url', 'https://openrouter.ai/api/v1/chat/completions')
        self.model = self.config.get('model', 'google/gemini-2.5-flash')
        self.api_key = self.config.get('api_key') or os.environ.get('OPENROUTER_API_KEY', '')

    def chat(self, messages, **kwargs):
        if not self.api_key:
            return ''
        try:
            response = httpx.post(
                self.url,
                headers=self._headers(),
                json={'model': self.model, 'messages': messages},
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            return data.get('choices', [{}])[0].get('message', {}).get('content', '')
        except Exception as e:
            print(f"OpenRouter error: {e}")
            return ''

    def chat_stream(self, messages, **kwargs):
        if not self.api_key:
            yield ''
            return
        try:
            with httpx.stream(
                'POST',
                self.url,
                headers=self._headers(),
                json={'model': self.model, 'messages': messages, 'stream': True},
                timeout=120,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line or not line.startswith('data: '):
                        continue
                    payload = line[6:]
                    if payload.strip() == '[DONE]':
                        break
                    data = json.loads(payload)
                    delta = data.get('choices', [{}])[0].get('delta', {}).get('content') or ''
                    if delta:
                        yield delta
        except Exception as e:
            print(f"OpenRouter error: {e}")
            yield ''

    def _headers(self):
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
