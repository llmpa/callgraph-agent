

from abc import ABC, abstractmethod
from typing import Callable, Optional
from pydantic import BaseModel

class JsonSchema(BaseModel):
    type: str
    properties: dict
    required: list[str]

class AgentAction(BaseModel):
    name: str
    description: str
    fn: Callable 
    input_schema: Optional[JsonSchema] = None
    

class ActionProvider(ABC):
    @abstractmethod
    def get_actions(self) -> list[AgentAction]:
        pass