import pytest
from cga.agents.callgraph.callgraph_agent import CallGraphAgent
from cga.utils.fs import CachedLocalFileSystem
from cga.llm import GPTOSS_20B
import os
import json
from pathlib import Path


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


def run_benchmark_test(benchmark_dir: str, llm_client) -> dict:
    """
    Run call graph analysis on a benchmark directory and compare with metadata.
    
    Args:
        benchmark_dir: Path to benchmark directory (e.g., callgraph-benchmark/python/project2)
        llm_client: LLM client to use for analysis
    
    Returns:
        dict with 'success' (bool), 'errors' (list), 'call_graph' (CallGraph), 'metadata' (dict)
    """
    benchmark_path = Path(benchmark_dir)
    metadata_path = benchmark_path / "metadata.json"
    
    # Load metadata
    if not metadata_path.exists():
        return {
            "success": False,
            "errors": [f"metadata.json not found in {benchmark_dir}"],
            "call_graph": None,
            "metadata": None
        }
    
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    # Find source file (main.py, main.c, main.cpp, main.go, main.rs)
    source_files = list(benchmark_path.glob("main.*"))
    source_files = [f for f in source_files if f.suffix in ['.py', '.c', '.cpp', '.go', '.rs']]
    
    if not source_files:
        return {
            "success": False,
            "errors": [f"No source file found in {benchmark_dir}"],
            "call_graph": None,
            "metadata": metadata
        }
    
    source_file = str(source_files[0])
    
    # Run call graph analysis
    fs = CachedLocalFileSystem()
    cg_agent = CallGraphAgent(llm_client=llm_client, fs=fs)
    call_graph = cg_agent.run(source_file)
    
    # Compare results
    errors = []
    
    # Check number of nodes
    expected_nodes = len(metadata["nodes"])
    actual_nodes = len(call_graph.nodes)
    if expected_nodes != actual_nodes:
        errors.append(f"Node count mismatch: expected {expected_nodes}, got {actual_nodes}")
    
    # Build a map of expected functions by name
    expected_funcs = {node["name"]: node for node in metadata["nodes"]}
    actual_funcs = {node.name: node for node in call_graph.nodes}
    
    # Check if all expected functions are found
    for func_name in expected_funcs.keys():
        if func_name not in actual_funcs:
            errors.append(f"Missing function: {func_name}")
    
    # Check edges (call relationships)
    expected_edges = metadata["edges"]
    
    # Build actual edges map
    actual_edges = {}
    for edge in call_graph.edges:
        if edge.caller_id not in actual_edges:
            actual_edges[edge.caller_id] = []
        actual_edges[edge.caller_id].append(edge.callee_id)
    
    # Compare edges
    for caller_id, callees in expected_edges.items():
        if caller_id not in actual_edges:
            errors.append(f"Missing caller: {caller_id}")
            continue
        
        actual_callees = actual_edges[caller_id]
        expected_callee_set = set(callees)
        actual_callee_set = set(actual_callees)
        
        missing_callees = expected_callee_set - actual_callee_set
        extra_callees = actual_callee_set - expected_callee_set
        
        if missing_callees:
            errors.append(f"Missing edges from {caller_id} to {missing_callees}")
        if extra_callees:
            errors.append(f"Extra edges from {caller_id} to {extra_callees}")
    
    return {
        "success": len(errors) == 0,
        "errors": errors,
        "call_graph": call_graph,
        "metadata": metadata
    }


@pytest.mark.benchmark
def test_benchmark_python_project2(llm_client):
    """Test call graph analysis on python/project2 benchmark."""
    # Get the repository root
    test_dir = Path(__file__).parent.parent.parent
    benchmark_dir = test_dir / "callgraph-benchmark" / "python" / "project2"
    
    result = run_benchmark_test(str(benchmark_dir), llm_client)
    
    # Print detailed results for debugging
    if not result["success"]:
        print("\nBenchmark test failed with errors:")
        for error in result["errors"]:
            print(f"  - {error}")
        
        if result["call_graph"]:
            print("\nActual call graph:")
            print(f"  Nodes: {[n.name for n in result['call_graph'].nodes]}")
            print(f"  Edges: {[(e.caller_id, e.callee_id) for e in result['call_graph'].edges]}")
    
    assert result["success"], f"Benchmark test failed: {result['errors']}"
