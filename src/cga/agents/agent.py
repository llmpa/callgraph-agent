from abc import ABC
import json
from typing import Any
import tiktoken
from cga.agents.actions import ActionProvider, AgentAction
from cga.llm.client import LLMClient
from cga.utils.llm_response import trim_json_markers
import time

import logging
logger = logging.getLogger(__name__)

class Agent(ABC):
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self._metrics = {
            "in_tokens": 0,
            "out_tokens": 0,
            "time_secs": 0
        }
        self._metrics_enc = tiktoken.get_encoding("o200k_base")
        self._actions: dict[str, AgentAction] = {}

    def get_metrics(self) -> dict:
        return self._metrics

    def _inc_out_token(self, tokens:int):
        self._metrics["out_tokens"] += tokens

    def _inc_in_token(self, tokens: int):
        self._metrics["in_tokens"] += tokens

    def _get_number_of_out_tokens(self, prompt:str) -> int:
        return len(self._metrics_enc.encode(prompt))
    
    def _llm_json(self, prompt: str) -> dict:
        _in_tokens = self._get_number_of_out_tokens(prompt)
        self._inc_in_token(_in_tokens)
        start_at = time.perf_counter()
        content = self.llm_client.single_round(prompt)
        end_at = time.perf_counter()
        self._metrics["time_secs"] += end_at - start_at
        _out_tokens = self._get_number_of_out_tokens(content)
        self._inc_out_token(_out_tokens)

        logger.debug(f"[LLM Response]: \"{content}\"")

        trimmed_content = trim_json_markers(content)
        if not trimmed_content:
            return {}
        return json.loads(trimmed_content)

    def add_action(self, action: AgentAction):
        # if action.name in self._actions:
        #     raise ValueError(f"Action with name {action.name} already exists.")
        self._actions[action.name] = action

    def add_action_provider(self, provider: ActionProvider):
        for action in provider.get_actions():
            self.add_action(action)

    def _action_context(self) -> str:
        context = "Available Actions:\n"
        for action in self._actions.values():
            context += f"- {action.name}: {action.description}\n"
            context += f"  Input Schema: {action.input_schema}\n"
        return context

    def _get_prompt(self, user_input: str) -> str:
        actions_context = self._action_context()
        prompt = f"""
You are an intelligent agent. You can perform the following actions to help answer the user's input.
{actions_context}

{user_input}

Respond with a JSON object:
{{
    "actions": [
        {{
            "name": "action_name",
            "input": {{
                // action input according to the schema
            }}
        }}
    ]
}}
"""
        return prompt.strip()
    
    def _handle_actions(self, actions: list[dict]) -> Any:
        results = []
        for action_dict in actions:
            action_name = action_dict.get("name")
            action_input = action_dict.get("input", {})
            if action_name not in self._actions:
                raise ValueError(f"Unknown action: {action_name}")
            action = self._actions[action_name]
            result = action.fn(**action_input)
            results.append(result)
        return results
    
