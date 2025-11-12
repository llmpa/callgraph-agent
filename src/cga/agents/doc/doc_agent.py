from typing import Any
from cga.agents.actions import ActionProvider, AgentAction, JsonSchema
from cga.agents.agent import Agent
from cga.llm.client import LLMClient
from cga.utils.fs import FileSystem
import logging

from cga.agents.doc.types import Result, Target

logger = logging.getLogger(__name__)



class DocAgent(Agent, ActionProvider):
    """
    Extract information from file(s) or directory containing documentation files.
    """
    def __init__(self, 
        llm_client: LLMClient, 
        fs: FileSystem,
        targets: list[Target],
    ):
        super().__init__(llm_client)
        self.fs = fs
        self.targets = targets
        self._current_file = None
        self._start_line = None
        self._end_line = None
        self._end_line_limit = None
        self._start_line_limit = 1
        self._omitted_lines = None
        
        # During the same level,
        # If a-b lines is target "A", 
        # then a-b lines will not be considered 
        # for other targets at the same level
        # it will be used if the target does not contain line range information (e.g., start_line, end_line)
        self._same_level_targets_overlap = False
        self._found: list[Result] = []
        self._current_parent_found = None
        # if _same_level_targets_overlap is set to False,
        # record the blacked lines as (start, end) tuples
        # it will be used if the target does not contain line range information (e.g., start_line, end_line)
        self._blacked_lines:list[tuple[int, int]] = []

    def run(self, file: str) -> list[Any]:
        self._current_file = file
        self._start_line_limit = 1
        self._end_line_limit = self.fs.get_file_metadata(file).lines
        for target in self.targets:
            self._current_target = target
            self._start_loop(target)
        
        return self._found
        
    def _start_loop(self, target: Target = None):
        self.add_action_provider(self)
        logger.debug(f"Starting loop with limit {self._start_line_limit}-{self._end_line_limit} for target {target.id}")
        self._start_line = max(1, self._start_line_limit)
        self._end_line = min(30, self._end_line_limit)
        self._omitted_lines = ""
        while True:
            logger.debug(f"reading lines {self._start_line} to {self._end_line} of file {self._current_file}")
            # Adjust the start and end line to skip blacked lines
            if not self._same_level_targets_overlap and self._blacked_lines:
                # case 1: 1 - 30, blacked: 5-10 => 1-4
                # case 2: 1 - 30, blacked: 25-35 => 1-25
                next_more_from = None
                for (bstart, bend) in self._blacked_lines:
                    
                    if self._start_line <= bstart <= self._end_line:
                        next_more_from = bend + 1
                        self._end_line = bstart - 1                                   
                        logger.debug(f"Adjusting reading lines to skip blacked lines ({bstart}-{bend}): now reading {self._start_line} to {self._end_line}")
                        break
                    elif self._start_line <= bend <= self._end_line:
                        self._start_line = bend + 1
                        logger.debug(f"Adjusting reading lines to skip blacked lines ({bstart}-{bend}): now reading {self._start_line} to {self._end_line}")
                        break
            if self._start_line > self._end_line:
                logger.debug("All lines are blacked, moving to next more lines.")
                if next_more_from is not None:
                    self._start_line = next_more_from + 1
                
                if self._start_line > self._end_line_limit:
                    break
                self._next_more(30)
                
                continue
            content = self.fs.read_file_with_lines(
                self._current_file, 
                self._start_line, 
                self._end_line, 
                with_linenum=True,
                omitted_lines=self._omitted_lines)
            
            logger.debug(f"Read content:\n{content}")
            
            prompt = self._get_prompt(
                f"Extract all targets align with definition \"{target.description}\" from the following document."
                f"Document Path: {self._current_file}\n"
                f"Current Part of Document:\n{content}\n"
                f"The document has {self._end_line_limit - self._start_line_limit + 1} lines in total.\n"
                f"If a target is found but not finished, return a retry_with action with appropriate line range.\n"
                f"At most one retry_with action can be returned each time. Each time read more 30 lines (can be less than 30 if reaching the end of the document).\n"
            )
            # logger.debug(f"[LLM Prompt]: \"{prompt}\"")
            actions_res = self._llm_json(prompt)
            actions = actions_res.get("actions", [])
            self._handle_actions(actions)
            if self._end_line >= self._end_line_limit:
                break

            actions_names = [action.get("name", "") for action in actions]
            if "retry_with" not in actions_names:
                self._next_more(30)
                
        if target.children:
            # find all found belongs to this target
            target_found = [f for f in self._found if f.target_id == target.id]
            old_end_lines = self._end_line_limit
            old_start_lines = self._start_line_limit
            old_blacked_lines = self._blacked_lines
            
            # loop each target found to find children targets
            for result in target_found:
                self._current_parent_found = result
                for child_target in target.children:
                    self._current_target = child_target
                    target_start_line = result.data.get("start_line", 1)
                    target_end_line = result.data.get("end_line", old_end_lines)
                    self._start_line_limit = target_start_line
                    self._end_line_limit = target_end_line
                    self._blacked_lines = []
                    self._start_loop(child_target)
            self._current_parent_found = None
            self._start_line_limit = old_start_lines
            self._end_line_limit = old_end_lines
            self._blacked_lines = old_blacked_lines
    def _retry_with(self, start, end, omitted_lines: str = ""):
        self._start_line = start
        self._end_line = end
        self._omitted_lines = omitted_lines

    def _next_more(self, lines: int):
        self._start_line = self._end_line + 1
        self._end_line = min(self._start_line + lines, self._end_line_limit)

    def _found_target(self, **kwargs):
        if "start_line" in kwargs and "end_line" in kwargs:
            start_line = kwargs["start_line"]
            end_line = kwargs["end_line"]
            if not self._same_level_targets_overlap:
                self._blacked_lines.append((start_line, end_line))
        
        data = kwargs
        if self._current_target.map_fn:
            data = self._current_target.map_fn(kwargs)
        
        logger.debug(f"Found target {self._current_target.id} with data: {type(data)}\n{data}")
        result = Result(
            target_id=self._current_target.id,
            data=data,
            children=[]
        )
        
        if self._current_parent_found is not None:
            self._current_parent_found.children.append(result)
        else:
            self._found.append(result)
        
        

    def get_actions(self) -> list:
        return [
            AgentAction(
                name="found_target",
                description="Indicates target definition has been found.",
                input_schema=self._current_target.schema,
                fn=self._found_target
            ),
            AgentAction(
                name="retry_with",
                description="Retry with more fine-grained lines to complete finding target definition. If too many lines are read, specify omitted lines.",
                input_schema=JsonSchema(
                    type="object",
                    properties={
                        "start": {
                            "type": "integer",
                            "description": "Starting line number to read from."
                        },
                        "end": {
                            "type": "integer",
                            "description": "Ending line number to read to."
                        },
                        "omitted_lines": {
                            "type": "string",
                            "description": "Lines omitted in the new read. Optional. E.g., '5-10,15-20' means lines 5 to 10 and lines 15 to 20 are omitted.",
                        }
                    },
                    required=["start", "end"]
                ),  
                fn=lambda **kwargs: self._retry_with(kwargs["start"], kwargs["end"], kwargs.get("omitted_lines", ""))
            )
        ]
    
        
        
