# flowrun/vm.py
import json
import os
import time
from typing import Optional, List, Dict, Set, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
import threading

from flowrun.executor import run_cmd_sandbox
from flowc.semantic import SemanticError
from flowc.ast import Step

def load_bytecode(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

class ParallelVM:
    """
    Parallel VM that executes bytecode steps concurrently while respecting dependencies.
    Accepts optional:
      - status_callback(step_name, status)  called on 'queued','running','succeeded','failed'
      - cancel_event: threading.Event that, if set, will instruct VM to cancel execution
    """
    def __init__(self, bytecode: Dict, workdir: Optional[str] = None, mem_limit_mb: Optional[int] = None,
                 max_workers: Optional[int] = None, status_callback: Optional[Callable]=None,
                 cancel_event: Optional[threading.Event]=None):
        self.bytecode = bytecode
        self.workdir = workdir or os.path.join(os.getcwd(), "flowscript_vm")
        self.mem_limit_mb = mem_limit_mb
        self.max_workers = max_workers or min(32, (os.cpu_count() or 2) * 2)
        self.status_callback = status_callback
        self.cancel_event = cancel_event

        self.steps_raw: List[Dict] = bytecode.get("steps", [])
        self.notifies_raw: List[Dict] = bytecode.get("notifies", []) or []

        self.step_objs: List[Step] = []
        for s in self.steps_raw:
            step = Step(
                name=s.get("step"),
                run=s.get("cmd"),
                timeout=s.get("timeout"),
                retries=s.get("retries", 0),
                depends_on=s.get("depends_on", []) or [],
                on_error=s.get("on_error")
            )
            self.step_objs.append(step)

        self.name_to_raw = {s.get("step"): s for s in self.steps_raw}
        self.notify_map = {n.get("name"): n for n in self.notifies_raw}

        self.lock = threading.Lock()
        self.completed: Set[str] = set()
        self.failed: Set[str] = set()
        self.running_futures: Dict[Future, str] = {}
        self.cancelled = False

        self.adj: Dict[str, List[str]] = {}
        self.indeg: Dict[str, int] = {}
        self.steps_set: Set[str] = set(s.name for s in self.step_objs)

    def _parse_timeout(self, timeout_raw: Optional[str]) -> Optional[int]:
        if not timeout_raw:
            return None
        try:
            return int(str(timeout_raw).rstrip("s"))
        except Exception:
            return None

    def _build_graph(self):
        self.adj = {n: [] for n in self.steps_set}
        self.indeg = {n: 0 for n in self.steps_set}
        for s in self.step_objs:
            name = s.name
            for dep in s.depends_on:
                if dep not in self.steps_set:
                    raise SemanticError(f"Bytecode step '{name}' depends on unknown step '{dep}'")
                self.adj.setdefault(dep, []).append(name)
                self.indeg[name] = self.indeg.get(name, 0) + 1

    def _report(self, step_name: str, status: str):
        # status: queued, running, succeeded, failed
        try:
            if self.status_callback:
                self.status_callback(step_name, status)
        except Exception:
            pass

    def _execute_step(self, step_name: str) -> bool:
        raw = self.name_to_raw.get(step_name, {})
        cmd = raw.get("cmd") or ""
        timeout_raw = raw.get("timeout")
        timeout = self._parse_timeout(timeout_raw)
        retries = raw.get("retries", 0) or 0

        self._report(step_name, "running")

        for attempt in range(retries + 1):
            if (self.cancel_event and self.cancel_event.is_set()) or self.cancelled:
                self._report(step_name, "failed")
                return False
            ok = run_cmd_sandbox(cmd, timeout=timeout, mem_limit_mb=self.mem_limit_mb, cwd=self.workdir)
            if ok:
                self._report(step_name, "succeeded")
                return True
            else:
                # retry or fail
                continue
        self._report(step_name, "failed")
        return False

    def _emit_notify(self, notify_name: str, failed_step: Optional[str] = None):
        n = self.notify_map.get(notify_name)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        if n:
            email = n.get("email")
            subject = n.get("subject")
            body = n.get("body")
            if failed_step and body:
                body = body.replace("${failed_step}", failed_step)
            os.makedirs(os.path.dirname(self.workdir) or ".", exist_ok=True)
            with open(os.path.join(self.workdir, "notifications.log"), "a", encoding="utf-8") as fh:
                fh.write(f"[{timestamp}] NOTIFY {notify_name} -> email: {email} subject: {subject} body: {body}\n")
        else:
            with open(os.path.join(self.workdir, "notifications.log"), "a", encoding="utf-8") as fh:
                fh.write(f"[{timestamp}] NOTIFY-MISSING {notify_name} for failed_step={failed_step}\n")

    def execute(self) -> bool:
        os.makedirs(self.workdir, exist_ok=True)
        try:
            self._build_graph()
        except SemanticError as e:
            print("Bytecode semantic error:", e)
            return False

        # initial ready queue
        ready = [n for n, d in self.indeg.items() if d == 0]
        for r in ready:
            self._report(r, "queued")

        if not ready and self.steps_set:
            print("No ready steps; possible cycle or empty workflow")
            return False

        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            for name in sorted(ready):
                fut = ex.submit(self._execute_step, name)
                with self.lock:
                    self.running_futures[fut] = name

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
                        print(f"[VM:{step}] raised exception: {e}")

                    if ok:
                        with self.lock:
                            self.completed.add(step)
                        newly_ready = []
                        for neigh in self.adj.get(step, []):
                            with self.lock:
                                self.indeg[neigh] -= 1
                                if self.indeg[neigh] == 0:
                                    newly_ready.append(neigh)
                                    self._report(neigh, "queued")
                        for nr in sorted(newly_ready):
                            if nr in self.completed or nr in self.failed:
                                continue
                            nfut = ex.submit(self._execute_step, nr)
                            with self.lock:
                                self.running_futures[nfut] = nr
                    else:
                        with self.lock:
                            self.failed.add(step)
                        raw = self.name_to_raw.get(step, {})
                        if raw.get("on_error"):
                            notify_name = raw.get("on_error")
                            print(f"[VM:{step}] calling on_error notify '{notify_name}'")
                            try:
                                self._emit_notify(notify_name, failed_step=step)
                            except Exception as e:
                                print(f"[VM] notify handler error: {e}")
                            newly_ready = []
                            for neigh in self.adj.get(step, []):
                                with self.lock:
                                    self.indeg[neigh] -= 1
                                    if self.indeg[neigh] == 0:
                                        newly_ready.append(neigh)
                                        self._report(neigh, "queued")
                            for nr in sorted(newly_ready):
                                if nr in self.completed or nr in self.failed:
                                    continue
                                nfut = ex.submit(self._execute_step, nr)
                                with self.lock:
                                    self.running_futures[nfut] = nr
                        else:
                            print(f"[VM:{step}] no on_error - aborting workflow")
                            self.cancelled = True
                            with self.lock:
                                for f in list(self.running_futures.keys()):
                                    try:
                                        f.cancel()
                                    except Exception:
                                        pass
                                self.running_futures.clear()
                            return False

                # honor external cancel_event
                if (self.cancel_event and self.cancel_event.is_set()) or self.cancelled:
                    print("VM detected cancel event; aborting")
                    with self.lock:
                        for f in list(self.running_futures.keys()):
                            try:
                                f.cancel()
                            except Exception:
                                pass
                        self.running_futures.clear()
                    return False

        if self.failed:
            print("VM finished with failures:", self.failed)
            return False
        print("VM finished successfully")
        return True
