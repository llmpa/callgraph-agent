from cga.llm.client import LLMClient
from ollama import Client

class OllamaLLMClient(LLMClient):
    def __init__(self, host:str):
        super().__init__()
        self.client = Client(
            host=host
        )

class GPTOSS_20B(OllamaLLMClient):

    def single_round(self, message: str) -> str:
        response = self.client.chat(model='gpt-oss:20b', messages=[
            {
                'role': 'user',
                'content': message,
            },
        ])
        return response['message']['content']

class GEMMA3_27B(OllamaLLMClient):
    def single_round(self, message: str) -> str:
        response = self.client.chat(model='gemma3:27b', messages=[
            {
                'role': 'user',
                'content': message,
            },
        ])
        return response['message']['content']
    
class GEMMA3_12B(OllamaLLMClient):
    def single_round(self, message: str) -> str:
        response = self.client.chat(model='gemma3:12b', messages=[
            {
                'role': 'user',
                'content': message,
            },
        ])
        return response['message']['content']

class DEEPSEEKR1_32B(OllamaLLMClient):
    def single_round(self, message: str) -> str:
        response = self.client.chat(model='deepseek-r1:32b', messages=[
            {
                'role': 'user',
                'content': message,
            },
        ])
        return response['message']['content']
    
class DEEPSEEKR1_14B(OllamaLLMClient):
    def single_round(self, message: str) -> str:
        response = self.client.chat(model='deepseek-r1:14b', messages=[
            {
                'role': 'user',
                'content': message,
            },
        ])
        return response['message']['content']