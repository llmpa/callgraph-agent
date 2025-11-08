from typing import Any
from cga.actions import ActionProvider, AgentAction, JsonSchema
from cga.agent import Agent
from cga.llm.client import LLMClient
from cga.utils.fs import FileSystem
import logging

logger = logging.getLogger(__name__)

class DocAgent(Agent, ActionProvider):
    """
    Extract information from file(s) or directory containing documentation files.
    """
    def __init__(self, 
        llm_client: LLMClient, 
        fs: FileSystem,
        target_def: str = "rule or requirement",
        target_schema = JsonSchema(
            type="object",
            properties={
                "sentence": {
                    "type": "string",
                    "description": "The sentence containing the target definition."
                }
            },
            required=["sentence"]
        ),
        target_map_fn = None,
        ):
        super().__init__(llm_client)
        self.fs = fs
        
        self.target_def = target_def
        self.target_schema = target_schema
        self.target_map_fn = target_map_fn
        self.targets = []
        self._current_file = None
        self._start_line = 1
        self._end_line = 30
        self._max_lines = None

    def run(self, file: str) -> list[Any]:
        self.add_action_provider(self)
        self._current_file = file
        self._max_lines = self.fs.get_file_metadata(file).lines
        self._end_line = min(self._end_line, self._max_lines)
        while True:
            content = self.fs.read_file_with_lines(file, self._start_line, self._end_line, with_linenum=True)
            logger.debug(f"Reading lines {self._start_line} to {self._end_line} of file {file}, {self._max_lines} lines total.")
            prompt = self._get_prompt(
                f"Extract any target align with definition \"{self.target_def}\" from the following document."
                f"Document Path: {file}\n"
                f"Current Part of Document:\n{content}\n"
                f"The document has {self._max_lines} lines in total.\n"
                f"If a sentence is not continuous, return corresponding action to cover the sentence.\n"
                f"At most one concat_more action can be returned each time. Each time read maximum 30 lines (can be less than 30 if reaching the end of the document).\n"
                f"Stop(return nothing) if reaching the end of the document."
            )
            # logger.debug(f"[LLM Prompt]: \"{prompt}\"")
            actions_res = self._llm_json(prompt)
            actions = actions_res.get("actions", [])
            self._handle_actions(actions)
            if self._end_line >= self._max_lines:
                break

            actions_names = [action.get("name", "") for action in actions]
            if "concat_more" not in actions_names:
                self._next_more(30)
                

        return self.targets

    def _concat_more(self, lines: int):
        self._end_line += lines

    def _next_more(self, lines: int):
        self._start_line = self._end_line + 1
        self._end_line = min(self._start_line + lines, self._max_lines)

    def _found_target(self, **kwargs):
        if self.target_map_fn:
            mapped_target = self.target_map_fn(kwargs)
            self.targets.append(mapped_target)
        else:
            self.targets.append(kwargs)
    def get_actions(self) -> list:
        return [
            AgentAction(
                name="found_target",
                description="Indicates target definition has been found.",
                input_schema=self.target_schema,
                fn=self._found_target
            ),
            AgentAction(
                name="concat_more",
                description="Read additional lines from the current part of the document.",
                input_schema=JsonSchema(
                    type="object",
                    properties={
                        "lines": {
                            "type": "integer",
                            "description": "Number of additional lines to read. 1 - 30."
                        }
                    },
                    required=["lines"]
                ),  
                fn=lambda **kwargs: self._concat_more(kwargs["lines"])
            )
        ]
    
        