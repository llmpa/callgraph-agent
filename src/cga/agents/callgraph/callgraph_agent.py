from cga.agents.actions import ActionProvider, AgentAction, JsonSchema
from cga.agents.agent import Agent
from cga.agents.doc.doc_agent import DocAgent
from cga.llm.client import LLMClient
from cga.agents.callgraph.types import CallGraph, CallGraphEdge, CallGraphNode
from cga.utils.fs import FileSystem
import logging

logger = logging.getLogger(__name__)



class CallGraphAgent(Agent, ActionProvider):
    """
    Extract call graph information from file(s) or directory containing source code files.
    """
    def __init__(self, 
        llm_client: LLMClient, 
        fs: FileSystem,
    ):
        super().__init__(llm_client)
        self.fs = fs
        self.add_action_provider(self)
        self._graph: CallGraph = CallGraph(nodes=[], edges=[])
        self._start_line = 1
        self._end_line = 30
        self._max_lines = None
        
    def run(self, file_or_dir: str) -> CallGraph:
        # Implementation for extracting call graph information goes here
        files = self.fs.list_files(file_or_dir)
        doc_agent = DocAgent(
            llm_client=self.llm_client,
            fs=self.fs,
            target_def="function definition",
            target_schema=JsonSchema(
                type="object",
                properties={
                    "file": {
                        "type": "string",
                        "description": "The file where the function is defined."
                    },
                    "function_name": {
                        "type": "string",
                        "description": "Name of the function defined."
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Starting line number of the function definition."
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Ending line number of the function definition."
                    }
                },
                required=["function_name", "start_line", "end_line"]     
            ),
            target_map_fn=lambda target: CallGraphNode(
                name=target["function_name"],
                loc={
                    "file": target['file'],
                    "line_start": target["start_line"],
                    "line_end": target["end_line"]
                }
            )
        )
        
        # collect all functions from the files
        all_functions: list[CallGraphNode] = []
        for file in files:
            functions = doc_agent.run(file)
            all_functions.extend(functions)

            for func in functions:
                logger.debug(f"Found function: {func.name} in {func.loc.file} lines {func.loc.line_start}-{func.loc.line_end}")
        
        # collect function call relationships
        self._graph.nodes = all_functions
        for func in all_functions:
            edges = self._extract_calls_from_func(func)
            self._graph.edges.extend(edges)

        return self._graph
    
    def _extract_calls_from_func(self, func: CallGraphNode) -> list[CallGraphEdge]:
        # Implementation for extracting function calls from a given function
        edges: list[CallGraphEdge] = []
        # Read the function's source code from the file
        content = self.fs.read_file_with_lines(
            func.loc.file, 
            func.loc.line_start, 
            func.loc.line_end, 
            with_linenum=True
        )
        prompt = self._get_prompt(self._get_cg_prompt(content))

        logger.debug(f"[LLM Prompt]: \"{prompt}\"")
        actions_res = self._llm_json(prompt)
        actions = actions_res.get("actions", [])
        results = self._handle_actions(actions)
        for (action, result) in zip(actions, results):
            if action.get("name") == "record_function_call":
                callee_name = result["name"]
                call_line = result["file_line"]
                callee_node = next((n for n in self._graph.nodes if n.name == callee_name), None)
                if callee_node:
                    edge = CallGraphEdge(
                        caller_id=func.id(),
                        callee_id=callee_node.id(),
                        attributes={
                            "loc": {
                                "file": func.loc.file,
                                "line_start": call_line,
                                "line_end": call_line
                            }
                        }
                    )
                    edges.append(edge)
        return edges
    
    def _find_function_by_name(self, name: str, file: str, file_line:int) -> CallGraphNode | None:
        # get candidates by name
        candidates = [n for n in self._graph.nodes if n.name == name]
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        
        # we can have different ways to 

    def _get_cg_prompt(self, content: str) -> str:
        prompt = (
            "Extract the call graph information from the following source code.\n\n"
            f"Current Part of Source Code:\n{content}\n\n"
        )
        return prompt

    def get_actions(self):
        return [
            AgentAction(
                name="record_function_call",
                description="Record a function call relationship between two functions.",
                input_schema=JsonSchema(
                    type="object",
                    properties={
                        "name": {
                            "type": "string",
                            "description": "Name of the function being called."
                        },
                        "file_line": {
                            "type": "integer",
                            "description": "Line number where the function call occurs."
                        },
                    },
                    required=["name", "file_line"]
                ),
                fn=lambda **kwargs: kwargs
            )
        ]





