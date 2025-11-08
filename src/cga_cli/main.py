#!/usr/bin/env python3
"""
Command-line interface for callgraph-agent.
"""
import argparse
import os
import sys
from pathlib import Path

from cga.callgraph_agent import CallGraphAgent
from cga.llm import (
    GPTOSS_20B, GEMMA3_27B, GEMMA3_12B, DEEPSEEKR1_32B, DEEPSEEKR1_14B,
    GPT5, GPT5MINI, GPT5NANO, OllamaLLMClient
)
from cga.llm.client import LLMClient
from cga.llm.openai import OpenAIClient
from cga.utils.fs import CachedLocalFileSystem
from cga.types import CallGraph


def format_callgraph_stdout(call_graph: CallGraph) -> str:
    """Format call graph for stdout output."""
    output = []
    output.append("Call Graph Summary:")
    output.append(f"  Nodes (Functions): {len(call_graph.nodes)}")
    output.append(f"  Edges (Calls): {len(call_graph.edges)}")
    output.append("")
    
    output.append("Functions:")
    for node in call_graph.nodes:
        output.append(f"  - {node.name} ({node.loc.file}:{node.loc.line_start}-{node.loc.line_end})")
    
    output.append("")
    output.append("Function Calls:")
    for edge in call_graph.edges:
        # Find the caller and callee names
        caller = next((n for n in call_graph.nodes if n.id() == edge.caller_id), None)
        callee = next((n for n in call_graph.nodes if n.id() == edge.callee_id), None)
        if caller and callee:
            output.append(f"  - {caller.name} -> {callee.name} (at {edge.attributes.loc.file}:{edge.attributes.loc.line_start})")
    
    return "\n".join(output)


def format_callgraph_json(call_graph: CallGraph) -> str:
    """Format call graph as JSON."""
    return call_graph.model_dump_json(indent=2)


def format_callgraph_graphviz(call_graph: CallGraph) -> str:
    """Format call graph as Graphviz DOT format."""
    output = []
    output.append("digraph CallGraph {")
    output.append("  rankdir=LR;")
    output.append("  node [shape=box];")
    output.append("")

    def nomalize_id(id_str: str) -> str:
        return id_str.replace(":", "_").replace("/", "_").replace(".", "_").replace("-", "_")
    
    # Add nodes
    for node in call_graph.nodes:
        label = f"{node.name}\\n{node.loc.file}:{node.loc.line_start}"
        node_id = nomalize_id(node.id())
        output.append(f'  {node_id} [label="{label}"];')
    
    output.append("")
    
    # Add edges
    for edge in call_graph.edges:
        caller_id = nomalize_id(edge.caller_id)
        callee_id = nomalize_id(edge.callee_id)
        output.append(f"  {caller_id} -> {callee_id};")
    
    output.append("}")
    return "\n".join(output)


def parse_llm_config(config_string: str) -> dict:
    """
    Parse LLM configuration string into a dictionary.
    
    Args:
        config_string: String in format "key1=value1 key2=value2"
    
    Returns:
        Dictionary with parsed key-value pairs
    
    Examples:
        >>> parse_llm_config("model=gpt-oss:20b host=http://localhost:11434")
        {'model': 'gpt-oss:20b', 'host': 'http://localhost:11434'}
    """
    config_dict = {}
    if not config_string:
        return config_dict
    
    # Split by spaces and parse key=value pairs
    pairs = config_string.strip().split()
    for pair in pairs:
        if '=' in pair:
            key, value = pair.split('=', 1)
            config_dict[key.strip()] = value.strip()
    
    return config_dict


def create_llm_client(llm_type: str, config: dict) -> LLMClient:
    """
    Create an LLM client based on type and configuration.
    
    Args:
        llm_type: Type of LLM ("ollama" or "openai")
        config: Configuration dictionary with model and other params
    
    Returns:
        Initialized LLM client
    """
    model = config.get("model", "")
    
    if llm_type == "ollama":
        # Map model names to their corresponding classes
        ollama_models = {
            "gpt-oss:20b": GPTOSS_20B,
            "gemma3:27b": GEMMA3_27B,
            "gemma3:12b": GEMMA3_12B,
            "deepseek-r1:32b": DEEPSEEKR1_32B,
            "deepseek-r1:14b": DEEPSEEKR1_14B,
        }
        
        # Get host from config or environment
        host = config.get("host") or os.getenv("OLLAMA_HOST")
        if not host:
            print("Error: OLLAMA_HOST not provided in config or environment.", file=sys.stderr)
            print("Use --llm-config 'host=http://localhost:11434' or set OLLAMA_HOST.", file=sys.stderr)
            sys.exit(1)
        
        # Select model class
        if model in ollama_models:
            model_class = ollama_models[model]
            return model_class(host=host)
        else:
            # Default to generic OllamaLLMClient if model not recognized
            print(f"Warning: Unknown Ollama model '{model}', using OllamaLLMClient", file=sys.stderr)
            return OllamaLLMClient(host=host)
    
    elif llm_type == "openai":
        # Map model names to their corresponding classes
        openai_models = {
            "gpt-5": GPT5,
            "gpt-5-mini": GPT5MINI,
            "gpt-5-nano": GPT5NANO,
        }
        
        # Get API key from config or environment
        api_key = config.get("api_key") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("Error: OpenAI API key not provided in config or environment.", file=sys.stderr)
            print("Use --llm-config 'api_key=YOUR_KEY' or set OPENAI_API_KEY.", file=sys.stderr)
            sys.exit(1)
        
        # Select model class
        if model in openai_models:
            model_class = openai_models[model]
            return model_class(api_key=api_key)
        else:
            # Default to generic OpenAIClient if model not recognized
            print(f"Warning: Unknown OpenAI model '{model}', using OpenAIClient", file=sys.stderr)
            return OpenAIClient(api_key=api_key)
    
    else:
        print(f"Error: Unknown LLM type '{llm_type}'", file=sys.stderr)
        sys.exit(1)


def run_callgraph_agent(input_path: Path, llm_client: LLMClient) -> CallGraph:
    """Run the call graph agent on the given path."""
    # Initialize file system
    fs = CachedLocalFileSystem()
    
    # Create agent and run
    agent = CallGraphAgent(llm_client=llm_client, fs=fs)
    call_graph = agent.run(str(input_path))
    
    return call_graph


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="cga",
        description="Generate call graphs from source code files or directories.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s path/to/file.py --llm ollama --llm-config "model=gpt-oss:20b host=http://localhost:11434" --out output/ -f graphviz
  %(prog)s path/to/file.py --llm openai --llm-config "model=gpt-5 api_key=YOUR_KEY" --out callgraph.json --out-format json
        """
    )
    
    # Positional argument: file or folder path
    parser.add_argument(
        "path",
        type=str,
        help="Path to a source file or directory to analyze"
    )
    
    # Optional output flag
    parser.add_argument(
        "--out", "-o",
        type=str,
        dest="output",
        help="Output path for the call graph (file or directory). If not specified, prints to stdout."
    )
    
    # Output format flag
    parser.add_argument(
        "--out-format", "-f",
        type=str,
        dest="format",
        choices=["graphviz", "stdout", "json"],
        default="stdout",
        help="Output format for the call graph (default: stdout)"
    )
    
    # LLM type flag
    parser.add_argument(
        "--llm",
        type=str,
        dest="llm_type",
        choices=["ollama", "openai"],
        default="ollama",
        help="LLM provider to use (default: ollama)"
    )
    
    # LLM configuration flag
    parser.add_argument(
        "--llm-config",
        type=str,
        dest="llm_config",
        default="",
        help="LLM configuration as 'key1=value1 key2=value2'. Examples: 'model=gpt-oss:20b host=http://localhost:11434' or 'model=gpt-5 api_key=YOUR_KEY'"
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Validate input path
    input_path = Path(args.path)
    if not input_path.exists():
        print(f"Error: Path does not exist: {args.path}", file=sys.stderr)
        sys.exit(1)
    
    if not input_path.is_file() and not input_path.is_dir():
        print(f"Error: Path is neither a file nor a directory: {args.path}", file=sys.stderr)
        sys.exit(1)
    
    # Parse LLM configuration
    llm_config = parse_llm_config(args.llm_config)
    
    # Create LLM client
    llm_client = create_llm_client(args.llm_type, llm_config)
    print(f"Using {args.llm_type} LLM with config: {llm_config}", file=sys.stderr)
    
    # Run the call graph agent
    print(f"Analyzing {input_path}...", file=sys.stderr)
    call_graph = run_callgraph_agent(input_path, llm_client)
    print(f"Analysis complete. Found {len(call_graph.nodes)} functions and {len(call_graph.edges)} calls.", file=sys.stderr)
    
    # Format the output based on the requested format
    if args.format == "json":
        output_content = format_callgraph_json(call_graph)
    elif args.format == "graphviz":
        output_content = format_callgraph_graphviz(call_graph)
    else:  # stdout
        output_content = format_callgraph_stdout(call_graph)
    
    # Write or print the output
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(output_content)
        print(f"Output written to: {output_path}", file=sys.stderr)
    else:
        print(output_content)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
