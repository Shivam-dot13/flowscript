# flowc/ir.py
from typing import List

def workflow_to_ir(workflow):
    """
    Produce a simple IR: list of instructions (dicts) describing steps.
    """
    ir = []
    for s in workflow.steps:
        instr = {
            "op": "RUN",
            "step": s.name,
            "cmd": s.run,
            "timeout": s.timeout,
            "retries": s.retries,
            "depends_on": s.depends_on,
            "on_error": s.on_error
        }
        ir.append(instr)
    return ir
