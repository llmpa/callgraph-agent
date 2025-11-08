import pytest
from cga.callgraph_agent import CallGraphAgent
from cga.utils.fs import CachedLocalFileSystem
from cga.llm import GPTOSS_20B
import os


@pytest.fixture
def llm_client():
    ollama_host = os.getenv("OLLAMA_HOST")
    if not ollama_host:
        raise ValueError("OLLAMA_HOST environment variable not set for tests.")
    return GPTOSS_20B(host=ollama_host)

@pytest.mark.integration
def test_callgraph_agent_py_simple(llm_client):
    # use file system in memory for testing
    fs = CachedLocalFileSystem()
    fs.write_file("/example.py", """\
def foo():
    bar()
def bar():
    pass
""", True)
    cg_agent = CallGraphAgent(llm_client=llm_client, fs=fs)
    call_graph = cg_agent.run("/example.py")
    assert len(call_graph.nodes) == 2  # foo and bar
    assert len(call_graph.edges) == 1  # foo calls bar
    edge = call_graph.edges[0]
    assert edge.caller_id == call_graph.nodes[0].id()  # foo
    assert edge.callee_id == call_graph.nodes[1].id()  # bar

@pytest.mark.integration
def test_callgraph_agent_rust_simple(llm_client):
    # use file system in memory for testing
    fs = CachedLocalFileSystem()
    fs.write_file("/example.rs", """\
fn foo() {
    bar();
}
fn bar() {
}  
""", True)
    cg_agent = CallGraphAgent(llm_client=llm_client, fs=fs)
    call_graph = cg_agent.run("/example.rs")
    assert len(call_graph.nodes) == 2  # foo and bar
    assert len(call_graph.edges) == 1  # foo calls bar
    edge = call_graph.edges[0]
    assert edge.caller_id == call_graph.nodes[0].id()  # foo
    assert edge.callee_id == call_graph.nodes[1].id()  # bar 
    