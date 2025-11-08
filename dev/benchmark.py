import os
import re
import json
from typing import Dict, List, Tuple

from cga.types import CallGraph, CallGraphFuncNode



def _detect_language_and_source_file(dir_path: str) -> Tuple[str, str]:
    """
    Infer language by locating the main source file in the given benchmark project directory.
    Returns (language, source_file_path).
    """
    candidates = [
        ("c", "main.c"),
        ("cpp", "main.cpp"),
        ("go", "main.go"),
        ("python", "main.py"),
        ("rust", "main.rs"),
    ]
    for lang, filename in candidates:
        full = os.path.join(dir_path, filename)
        if os.path.isfile(full):
            return lang, full
    # Fallback: first file in dir
    for entry in os.listdir(dir_path):
        full = os.path.join(dir_path, entry)
        if os.path.isfile(full):
            return "unknown", full
    raise FileNotFoundError(f"No source file found in {dir_path}")


def _read_lines(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().splitlines()


def _collect_function_defs(lang: str, lines: List[str]) -> Dict[str, int]:
    """
    Return mapping: function_name -> start_line_number (1-based).
    Minimalistic regexes tailored for the benchmark patterns.
    """
    defs: Dict[str, int] = {}

    if lang == "python":
        pat = re.compile(r"^\s*def\s+([A-Za-z_]\w*)\s*\(")
        for i, line in enumerate(lines, start=1):
            m = pat.search(line)
            if m:
                defs[m.group(1)] = i
        return defs

    if lang == "go":
        pat = re.compile(r"^\s*func\s+([A-Za-z_]\w*)\s*\(")
        for i, line in enumerate(lines, start=1):
            m = pat.search(line)
            if m:
                defs[m.group(1)] = i
        return defs

    if lang == "rust":
        pat = re.compile(r"^\s*fn\s+([A-Za-z_]\w*)\s*\(")
        for i, line in enumerate(lines, start=1):
            m = pat.search(line)
            if m:
                defs[m.group(1)] = i
        return defs

    # C / C++ (very loose heuristic)
    # Match lines like: 'void func_a(...) {', 'int main(...) {', etc.
    pat = re.compile(r"^\s*(?:[A-Za-z_][\w\s\*]*\s+)?([A-Za-z_]\w*)\s*\([^;]*\)\s*\{")
    for i, line in enumerate(lines, start=1):
        m = pat.search(line)
        if m:
            defs[m.group(1)] = i
    return defs


def _collect_function_bodies_python(lines: List[str], defs: Dict[str, int]) -> Dict[str, Tuple[int, int]]:
    """
    Python body extents by indentation: returns name -> (start_idx, end_idx) inclusive, 0-based indices.
    """
    name_by_line = {ln: name for name, ln in defs.items()}
    bodies: Dict[str, Tuple[int, int]] = {}
    n = len(lines)
    def_indent = None
    for i in range(n):
        ln = i + 1
        if ln in name_by_line:
            name = name_by_line[ln]
            # Measure indentation of definition line
            indent = len(lines[i]) - len(lines[i].lstrip())
            # Body starts at next line
            start = i + 1
            j = start
            while j < n:
                if lines[j].strip() == "":
                    j += 1
                    continue
                cur_indent = len(lines[j]) - len(lines[j].lstrip())
                if cur_indent <= indent and lines[j].lstrip().startswith("def "):
                    break
                if cur_indent <= indent and not lines[j].startswith(" ") and not lines[j].startswith("\t"):
                    # New top-level (unlikely in benchmark), break
                    break
                j += 1
            bodies[name] = (start, j - 1)
    return bodies


def _collect_function_bodies_braces(lines: List[str], defs: Dict[str, int]) -> Dict[str, Tuple[int, int]]:
    """
    Braces languages (C/C++/Go/Rust): returns name -> (start_idx, end_idx) inclusive, 0-based indices.
    """
    bodies: Dict[str, Tuple[int, int]] = {}
    # Convert def line numbers to 0-based indices
    def_idx = {name: ln - 1 for name, ln in defs.items()}
    n = len(lines)
    for name, idx in def_idx.items():
        # Find first '{' on or after the def line
        i = idx
        while i < n and '{' not in lines[i]:
            i += 1
        if i >= n:
            bodies[name] = (idx, idx)
            continue
        # Brace matching
        depth = 0
        start = i
        j = i
        found_start = False
        while j < n:
            for ch in lines[j]:
                if ch == '{':
                    depth += 1
                    found_start = True
                elif ch == '}':
                    depth -= 1
                    if found_start and depth == 0:
                        bodies[name] = (start, j)
                        break
            if name in bodies:
                break
            j += 1
        if name not in bodies:
            bodies[name] = (start, n - 1)
    return bodies


def _find_calls_in_body(lines: List[str], body: Tuple[int, int], callee_names: List[str]) -> List[str]:
    """
    Naive call finder: any occurrence of 'name(' where name is in callee_names.
    Returns list of callee names in lexical order of first appearance.
    """
    start, end = body
    called: List[str] = []
    # Create a regex that matches any callee as a word immediately followed by '('
    if not callee_names:
        return called
    # Sort by length desc to avoid prefix issues (e.g., func vs func_a)
    escaped = sorted([re.escape(n) for n in callee_names], key=len, reverse=True)
    pat = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(escaped) + r")\s*\(")
    for i in range(start, end + 1):
        for m in pat.finditer(lines[i]):
            name = m.group(1)
            called.append(name)
    return called


def run_agent(project_dir: str) -> CallGraph:
    """
    Build a simple call graph for the given benchmark project directory.
    Returns a CallGraph matching the schema in metadata.json.
    """
    lang, src_file = _detect_language_and_source_file(project_dir)
    lines = _read_lines(src_file)

    defs = _collect_function_defs(lang, lines)
    # Determine body extents
    if lang == "python":
        bodies = _collect_function_bodies_python(lines, defs)
    else:
        bodies = _collect_function_bodies_braces(lines, defs)

    # Compute base to make file paths relative to callgraph-benchmark
    repo_root = os.path.abspath(os.path.dirname(__file__))
    bench_root = os.path.abspath(os.path.join(repo_root, "callgraph-benchmark"))
    rel_file = os.path.relpath(src_file, bench_root)
    rel_file = rel_file.replace("\\", "/")  # normalize

    # Build nodes
    nodes = [CallGraphFuncNode(name=n, file_line=ln, file=rel_file) for n, ln in defs.items()]

    # Build edges
    edges: Dict[str, List[str]] = {}
    defined_names = list(defs.keys())
    id_by_name = {n: CallGraphFuncNode(n, defs[n], rel_file).id() for n in defined_names}
    for name, ln in defs.items():
        src_id = f"{rel_file}:{ln}:{name}"
        body = bodies.get(name)
        if not body:
            continue
        callees = _find_calls_in_body(lines, body, [n for n in defined_names if n != name])
        # Map to ids, preserve order but unique
        seen = set()
        callee_ids: List[str] = []
        for callee in callees:
            cid = id_by_name.get(callee)
            if cid and cid not in seen:
                seen.add(cid)
                callee_ids.append(cid)
        if callee_ids:
            edges[src_id] = callee_ids

    return CallGraph(nodes=nodes, edges=edges)


def list_benchmark_projects(bench_root: str) -> List[str]:
    """
    List all project directories under each language inside callgraph-benchmark/*/project*/.
    Returns absolute paths to project directories that contain a metadata.json file.
    """
    bench_root = os.path.abspath(bench_root)
    if not os.path.isdir(bench_root):
        raise FileNotFoundError(f"Benchmark root not found: {bench_root}")

    projects: List[str] = []
    for lang in os.listdir(bench_root):
        lang_dir = os.path.join(bench_root, lang)
        if not os.path.isdir(lang_dir):
            continue
        for proj in os.listdir(lang_dir):
            proj_dir = os.path.join(lang_dir, proj)
            if not os.path.isdir(proj_dir):
                continue
            meta_path = os.path.join(proj_dir, "metadata.json")
            if os.path.isfile(meta_path):
                projects.append(proj_dir)
    return sorted(projects)


def _load_metadata(project_dir: str) -> Dict:
    with open(os.path.join(project_dir, "metadata.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def compare_with_metadata(graph: CallGraph, project_dir: str) -> Dict:
    """
    Compare computed call graph with metadata.json. Returns a dict of comparison details.
    """
    repo_root = os.path.abspath(os.path.dirname(__file__))
    bench_root = os.path.abspath(os.path.join(repo_root, "callgraph-benchmark"))
    rel_file_prefix = os.path.relpath(project_dir, bench_root).replace("\\", "/")

    meta = _load_metadata(project_dir)

    # Nodes comparison (by id)
    meta_node_ids = set(
        f"{n['file']}:{n['file_line']}:{n['name']}" for n in meta.get("nodes", [])
    )
    graph_node_ids = set(n.id() for n in graph.nodes)

    node_missing = sorted(meta_node_ids - graph_node_ids)
    node_extra = sorted(graph_node_ids - meta_node_ids)

    # Edges comparison (as set of pairs)
    def edge_set_from_mapping(mapping: Dict[str, List[str]]) -> set:
        s = set()
        for src, dsts in mapping.items():
            for d in dsts:
                s.add((src, d))
        return s

    meta_edges = edge_set_from_mapping(meta.get("edges", {}))
    graph_edges = edge_set_from_mapping(graph.edges)

    edge_missing = sorted(meta_edges - graph_edges)
    edge_extra = sorted(graph_edges - meta_edges)

    return {
        "project": rel_file_prefix,
        "nodes_total_meta": len(meta_node_ids),
        "nodes_total_graph": len(graph_node_ids),
        "nodes_missing": node_missing,
        "nodes_extra": node_extra,
        "edges_total_meta": len(meta_edges),
        "edges_total_graph": len(graph_edges),
        "edges_missing": edge_missing,
        "edges_extra": edge_extra,
        "pass": not node_missing and not node_extra and not edge_missing and not edge_extra,
    }


def run_all() -> List[Dict]:
    """
    Discover all benchmark projects, run agent for each, and compare with metadata.
    Returns list of comparison result dicts.
    """
    repo_root = os.path.abspath(os.path.dirname(__file__))
    bench_root = os.path.join(repo_root, "callgraph-benchmark")
    results: List[Dict] = []
    for proj_dir in list_benchmark_projects(bench_root):
        graph = run_agent(proj_dir)
        cmp = compare_with_metadata(graph, proj_dir)
        results.append(cmp)
    return results


def main() -> None:
    results = run_all()
    # Print a concise report
    total = len(results)
    passed = sum(1 for r in results if r["pass"]) 
    print(f"Benchmarks: {passed}/{total} passed")
    for r in results:
        status = "PASS" if r["pass"] else "FAIL"
        print(f"- {r['project']}: {status} | nodes(meta/graph) {r['nodes_total_meta']}/{r['nodes_total_graph']} | edges(meta/graph) {r['edges_total_meta']}/{r['edges_total_graph']}")
        if not r["pass"]:
            if r["nodes_missing"]:
                print(f"  nodes_missing: {r['nodes_missing']}")
            if r["nodes_extra"]:
                print(f"  nodes_extra:   {r['nodes_extra']}")
            if r["edges_missing"]:
                print(f"  edges_missing: {r['edges_missing']}")
            if r["edges_extra"]:
                print(f"  edges_extra:   {r['edges_extra']}")


if __name__ == "__main__":
    main()
