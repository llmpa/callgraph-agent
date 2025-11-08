from cga.llm.client import LLMClient
from openai import OpenAI

class OpenAIClient(LLMClient):
    def __init__(self, api_key: str):
        super().__init__()
        self.client = OpenAI(api_key=api_key)


class GPT5(OpenAIClient):


    def single_round(self, message: str) -> str:
        response = self.client.responses.create(
            model="gpt-5",
            input=message,
        )

        return response.output_text

class GPT5MINI(OpenAIClient):


    def single_round(self, message: str) -> str:
        response = self.client.responses.create(
            model="gpt-5-mini",
            input=message,
        )

        return response.output_text

class GPT5NANO(OpenAIClient):


    def single_round(self, message: str) -> str:
        response = self.client.responses.create(
            model="gpt-5-nano",
            input=message,
        )

        return response.output_text