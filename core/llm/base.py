from abc import ABC, abstractmethod

class LLMProvider(ABC):
    def __init__(self, config=None):
        self.config = config or {}
    
    @abstractmethod
    def chat(self, messages, **kwargs):
        pass
    
    @abstractmethod
    def list_models(self):
        pass
