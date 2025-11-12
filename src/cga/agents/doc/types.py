from typing import Any, Callable, Optional
from pydantic import BaseModel
from cga.agents.actions import JsonSchema


class Target(BaseModel):
    id: str
    description: str
    schema: JsonSchema
    map_fn: Optional[Callable] = None
    children: Optional[list['Target']] = None



class Result(BaseModel):
    target_id: str
    data: Any
    children: Optional[list['Result']] = None
