# flowc/visualize.py
from graphviz import Digraph
from typing import List
from .ast import Workflow, Step

def workflow_to_dot(workflow: Workflow, show_details: bool = True) -> Digraph:
    """
    Convert Workflow AST into a graphviz Digraph.
    show_details: include step metadata in node labels (timeout/retries).
    """
    dot = Digraph(name=workflow.name)
    dot.attr(rankdir='LR', splines='true', fontsize='10')

    # Add workflow node (cluster)
    with dot.subgraph(name='cluster_workflow') as c:
        c.attr(style='filled', color='lightgrey')
        c.node_attr.update(style='filled', color='white')
        c.attr(label=f"Workflow: {workflow.name}")

        # Add step nodes
        for s in workflow.steps:
            label = s.name
            if show_details:
                meta = []
                if s.run:
                    # shorten command for label
                    cmd = s.run
                    if len(cmd) > 60:
                        cmd = cmd[:57] + '...'
                    meta.append(f"cmd: {cmd}")
                if s.timeout:
                    meta.append(f"t: {s.timeout}")
                if s.retries:
                    meta.append(f"r: {s.retries}")
                if meta:
                    label = f"{s.name}\\n" + "\\n".join(meta)
            c.node(s.name, label=label, shape='box')

        # Add notify nodes
        for n in workflow.notifies:
            dot.node(n.name, label=f"notify\\n{n.name}", shape='note', color='orange')

    # Add edges for dependencies
    for s in workflow.steps:
        for dep in s.depends_on:
            dot.edge(dep, s.name)

    # Optionally, add edges from steps to their on_error handler (dashed red)
    for s in workflow.steps:
        if s.on_error:
            dot.edge(s.name, s.on_error, style='dashed', color='red', label='on_error')

    return dot

def render_workflow_to_file(workflow: Workflow, out_path: str, format: str = 'png', show_details: bool = True):
    dot = workflow_to_dot(workflow, show_details=show_details)
    # Set file name & render
    # graphviz will add file extension automatically
    dot.format = format
    # If out_path contains extension, strip it
    if out_path.endswith(f'.{format}'):
        out_path = out_path[:-(len(format)+1)]
    dot.render(out_path, cleanup=True)
    return f"{out_path}.{format}"
