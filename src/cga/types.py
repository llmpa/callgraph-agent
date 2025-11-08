from pydantic import BaseModel

class FileLoc(BaseModel):
    file: str
    line_start: int
    line_end: int

class CallGraphNode(BaseModel):
    name: str
    loc: FileLoc
    
    def id(self) -> str:
        return f"{self.loc.file}:{self.loc.line_start}:{self.name}"

class CallGraphEdgeAttributes(BaseModel):
    loc: FileLoc

class CallGraphEdge(BaseModel):
    caller_id: str
    callee_id: str
    attributes: CallGraphEdgeAttributes

class CallGraph(BaseModel):
    nodes: list[CallGraphNode]
    edges: list[CallGraphEdge]