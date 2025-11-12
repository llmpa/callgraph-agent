import os
from cga.agents.actions import JsonSchema
from cga.agents.doc.doc_agent import DocAgent
from cga.agents.doc.types import Target
from cga.llm.ollama import GPTOSS_20B
from cga.utils.fs import CachedLocalFileSystem
import pytest



@pytest.fixture
def llm_client():
    ollama_host = os.getenv("OLLAMA_HOST")
    if not ollama_host:
        raise ValueError("OLLAMA_HOST environment variable not set for tests.")
    return GPTOSS_20B(host=ollama_host)

@pytest.fixture
def callgraph_targets():
    ft = Target(
        id="function",
        description="function",
        schema=JsonSchema(
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
                    "description": "Starting line number of the function."
                },
                "end_line": {
                    "type": "integer",
                    "description": "Ending line number of the function."
                }
            },
            required=["function_name", "start_line", "end_line"]     
        )
    )
    return [
        Target(
            id="class",
            description="class",
            schema=JsonSchema(
                type="object",
                properties={
                    "class_name": {
                        "type": "string",
                        "description": "Name of the class."
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Starting line number of the class."
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Ending line number of the class."
                    }
                },
                required=["class_name", "start_line", "end_line"]
            ),
            children=[ft]
        ),
        ft
    ]
    
@pytest.mark.integration
def test_doc_agent_py_with_class(llm_client, callgraph_targets):
    # use file system in memory for testing
    fs = CachedLocalFileSystem()
    fs.write_file("/example.py", """\
def foo():
    bar()

def bar():
    # some random comment2
    # some random comment3
    # some random comment4
    pass

class MyClass:
    def method1(self):
        # some random comment
        pass
        
    def method2(self):
        # another comment 
        a = 1
        b = 3
        c = a + b
        pass
""", True)
    
    agent = DocAgent(llm_client=llm_client, fs=fs, targets=callgraph_targets)
    targets = agent.run("/example.py")
    assert len(targets) == 3
    assert targets[0].data["class_name"] == "MyClass"

    assert targets[1].data["function_name"] == "foo"
    assert targets[2].data["function_name"] == "bar"
    assert len(targets[0].children) == 2
    assert targets[0].children[0].data["function_name"] == "method1"
    assert targets[0].children[1].data["function_name"] == "method2"