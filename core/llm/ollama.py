import json
import httpx
from .base import LLMProvider

class OllamaProvider(LLMProvider):
    def __init__(self, config=None):
        super().__init__(config)
        self.url = self.config.get('url', 'http://localhost:11434')
        self.model = self.config.get('model', 'qwen2.5:3b')
        self.keep_alive = self.config.get('keep_alive', '30m')

    def chat(self, messages, **kwargs):
        try:
            url = f"{self.url}/api/chat"
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "keep_alive": self.keep_alive,
                "options": kwargs
            }
            response = httpx.post(url, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            return data.get('message', {}).get('content', '')
        except Exception as e:
            print(f"Ollama error: {e}")
            return f"Erro ao conectar com Ollama: {e}"

    def chat_stream(self, messages, **kwargs):
        url = f"{self.url}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "keep_alive": self.keep_alive,
            "options": kwargs
        }
        try:
            with httpx.stream('POST', url, json=payload, timeout=120) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get('done'):
                        break
                    yield data.get('message', {}).get('content', '')
        except Exception as e:
            print(f"Ollama error: {e}")
            yield ''
    
    def list_models(self):
        try:
            url = f"{self.url}/api/tags"
            response = httpx.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            return [m['name'] for m in data.get('models', [])]
        except Exception as e:
            print(f"Ollama list error: {e}")
            return []
