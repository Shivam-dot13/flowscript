# flowc/bytecode.py
import json
import os
from typing import List, Dict, Optional

def emit_bytecode(workflow_name: str, ir: List[dict], out_path: str, notifies: Optional[List[Dict]] = None):
    """
    Emit a JSON bytecode file from IR and optional notifies list.
    Format:
    {
      "workflow": "<name>",
      "steps": [...],
      "notifies": [...]
    }
    """
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    bc = {
        "workflow": workflow_name,
        "steps": ir
    }
    if notifies:
        bc["notifies"] = notifies
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(bc, f, indent=2)
    print(f"Bytecode emitted -> {out_path}")
    return out_path
