# flowrun/runtime_parallel.py
import os
import time
from typing import List, Dict, Optional, Set
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
import threading

from flowrun.executor import run_cmd_sandbox

class ParallelRuntime:
    """
    Dependency-aware parallel runtime.
    - expects IR ordered arbitrarily; builds dependency graph itself.
    - executes independent steps in parallel using ThreadPoolExecutor.
    - respects per-step timeout and retries.
    - if a step fails and has no on_error, the workflow is aborted.
    """

    def __init__(self, ir: List[dict], workdir: str = "/tmp/flowscript_run", max_workers: Optional[int] = None, mem_limit_mb: Optional[int] = None):
        self.ir = ir
        self.workdir = workdir
        self.mem_limit_mb = mem_limit_mb
        self.max_workers = max_workers or min(32, (os.cpu_count() or 2) * 2)
        # build maps
        self.name_to_instr: Dict[str, dict] = {instr['step']: instr for instr in ir}
        self.steps: Set[str] = set(self.name_to_instr.keys())

        # build dependency graph (adj and indegree)
        self.adj: Dict[str, List[str]] = {n: [] for n in self.steps}
        self.indeg: Dict[str, int] = {n: 0 for n in self.steps}
        for name, instr in self.name_to_instr.items():
            for dep in instr.get('depends_on', []) or []:
                if dep in self.adj:
                    self.adj[dep].append(name)
                else:
                    # missing dependency will be caught by semantic checks earlier
                    self.adj.setdefault(dep, []).append(name)
                self.indeg[name] = self.indeg.get(name, 0) + 1

        # runtime state
        self.lock = threading.Lock()
        self.completed: Set[str] = set()
        self.failed: Set[str] = set()
        self.running_futures: Dict[Future, str] = {}
        self.cancelled = False

    def _parse_timeout(self, timeout_raw: Optional[str]) -> Optional[int]:
        if not timeout_raw:
            return None
        try:
            return int(str(timeout_raw).rstrip('s'))
        except Exception:
            return None

    def _execute_step(self, step_name: str) -> bool:
        """
        Execute single step with retries and timeout using run_cmd_sandbox.
        Returns True on success, False on failure.
        """
        instr = self.name_to_instr[step_name]
        cmd = instr.get('cmd') or ""
        timeout_raw = instr.get('timeout')
        timeout = self._parse_timeout(timeout_raw)
        retries = instr.get('retries', 0) or 0

        for attempt in range(retries + 1):
            if self.cancelled:
                return False
            print(f"[{step_name}] attempt {attempt+1}/{retries+1}")
            ok = run_cmd_sandbox(cmd, timeout=timeout, mem_limit_mb=self.mem_limit_mb, cwd=self.workdir)
            if ok:
                return True
            else:
                print(f"[{step_name}] attempt {attempt+1} failed")
        return False

    def execute(self) -> bool:
        """
        Run the workflow in parallel, return True if all steps succeeded.
        """
        # initial ready queue: steps with indeg 0
        ready = [n for n, d in self.indeg.items() if d == 0]
        if not ready and self.steps:
            print("No ready steps; possible cycle or empty workflow")
            return False

        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            # submit initial tasks
            for name in ready:
                fut = ex.submit(self._execute_step, name)
                with self.lock:
                    self.running_futures[fut] = name

            # main loop: as futures complete, submit newly-ready tasks
            while self.running_futures:
                done_iter = as_completed(list(self.running_futures.keys()), timeout=None)
                for fut in done_iter:
                    step = None
                    with self.lock:
                        step = self.running_futures.pop(fut, None)
                    try:
                        ok = fut.result()
                    except Exception as e:
                        ok = False
                        print(f"[{step}] raised exception: {e}")

                    if ok:
                        print(f"[{step}] succeeded")
                        with self.lock:
                            self.completed.add(step)
                        # reduce indegree of neighbors; submit any that become 0
                        newly_ready = []
                        for neigh in self.adj.get(step, []):
                            with self.lock:
                                self.indeg[neigh] -= 1
                                if self.indeg[neigh] == 0:
                                    newly_ready.append(neigh)
                        for nr in newly_ready:
                            if nr in self.completed or nr in self.failed:
                                continue
                            nfut = ex.submit(self._execute_step, nr)
                            with self.lock:
                                self.running_futures[nfut] = nr
                    else:
                        print(f"[{step}] failed")
                        with self.lock:
                            self.failed.add(step)
                        # handle on_error if present
                        instr = self.name_to_instr.get(step, {})
                        if instr.get('on_error'):
                            print(f"[{step}] on_error -> {instr.get('on_error')}")
                            # simple behavior: just print; you could schedule notify handler
                        else:
                            # abort whole workflow: cancel running futures and stop
                            print(f"[{step}] no on_error handler — aborting workflow")
                            self.cancelled = True
                            # try to cancel other futures
                            with self.lock:
                                for f in list(self.running_futures.keys()):
                                    try:
                                        f.cancel()
                                    except Exception:
                                        pass
                                self.running_futures.clear()
                            return False

                # loop continues until no running futures left
            # end while
        # decide overall result
        if self.failed:
            print("Workflow finished with failures:", self.failed)
            return False
        print("Workflow finished successfully")
        return True
