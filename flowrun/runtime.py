# flowrun/runtime.py
from flowrun.executor import run_cmd_sandbox
from typing import List

class Runtime:
    def __init__(self, ir: List[dict], workdir: str = "/tmp/flowscript_run"):
        self.ir = ir
        self.workdir = workdir
        self.state = {instr["step"]: "PENDING" for instr in ir}

    def execute(self) -> bool:
        # IR must be topologically ordered by caller
        for instr in self.ir:
            step = instr["step"]
            cmd = instr["cmd"] or ""
            timeout = None
            if instr.get("timeout"):
                try:
                    timeout = int(str(instr["timeout"]).rstrip("s"))
                except Exception:
                    timeout = None
            retries = instr.get("retries", 0) or 0
            ok = False
            for attempt in range(retries + 1):
                print(f"Running {step}, attempt {attempt+1}")
                ok = run_cmd_sandbox(cmd, timeout=timeout, cwd=self.workdir)
                if ok:
                    break
            self.state[step] = "OK" if ok else "FAILED"
            if not ok:
                print(f"Step {step} failed")
                if instr.get("on_error"):
                    print(f"On error: {instr.get('on_error')}")
                return False
        return True
