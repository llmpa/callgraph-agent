from abc import ABC, abstractmethod

class LLMClient(ABC):
    @abstractmethod
    def single_round(self, message: str) -> str:
        pass


