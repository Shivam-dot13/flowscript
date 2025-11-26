# flowc/semantic.py
from typing import List
from .ast import Workflow, Step
import re

BANNED_PATTERNS = [
    r"rm\s+-rf",
    r"(^|;|\s)\|(\s|$)",   # pipe
    r"(>>)",               # append redirect
    r"(^|;|\s)&(\s|$)",    # background
    r"`"                   # backticks
]

class SemanticError(Exception):
    pass

def check_duplicates(steps: List[Step]):
    names = set()
    for s in steps:
        if s.name in names:
            raise SemanticError(f"Duplicate step name: {s.name}")
        names.add(s.name)

def check_missing_dependencies(steps: List[Step]):
    names = {s.name for s in steps}
    for s in steps:
        for d in s.depends_on:
            if d not in names:
                raise SemanticError(f"Step '{s.name}' depends on missing step '{d}'")

def detect_cycle(steps: List[Step]):
    # Kahn's algorithm for cycle detection
    graph = {s.name: set(s.depends_on) for s in steps}
    indeg = {n: len(graph[n]) for n in graph}
    queue = [n for n, d in indeg.items() if d == 0]
    order = []
    queue.sort()
    while queue:
        n = queue.pop(0)
        order.append(n)
        for m in list(graph.keys()):
            if n in graph[m]:
                graph[m].remove(n)
                indeg[m] -= 1
                if indeg[m] == 0:
                    queue.append(m)
        queue.sort()
    if len(order) != len(steps):
        raise SemanticError("Cycle detected in step dependencies")

def check_banned_commands(steps: List[Step]):
    for s in steps:
        if s.run:
            for pat in BANNED_PATTERNS:
                if re.search(pat, s.run):
                    raise SemanticError(f"Banned pattern in step '{s.name}': pattern '{pat}' matched")

def build_dag(steps: List[Step]) -> List[str]:
    # deterministic topological sort using Kahn's algorithm
    graph = {s.name: set(s.depends_on) for s in steps}
    indeg = {n: len(graph[n]) for n in graph}
    queue = [n for n, d in indeg.items() if d == 0]
    order = []
    queue.sort()
    while queue:
        n = queue.pop(0)
        order.append(n)
        for m in list(graph.keys()):
            if n in graph[m]:
                graph[m].remove(n)
                indeg[m] -= 1
                if indeg[m] == 0:
                    queue.append(m)
        queue.sort()
    if len(order) != len(steps):
        raise SemanticError("Cycle detected when building DAG")
    return order

def semantic_check(workflow: Workflow) -> List[str]:
    check_duplicates(workflow.steps)
    check_missing_dependencies(workflow.steps)
    detect_cycle(workflow.steps)
    check_banned_commands(workflow.steps)
    order = build_dag(workflow.steps)
    return order
