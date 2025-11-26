# flowrun/executor.py
import subprocess
import os
import time
from typing import Optional

# Try to import resource (POSIX). It may be missing on Windows or constrained builds.
try:
    import resource
except Exception:
    resource = None

# psutil is recommended on Windows for memory monitoring. If not installed, memory enforcement is best-effort.
try:
    import psutil
except Exception:
    psutil = None


def _can_setrlimit() -> bool:
    """
    True if resource.setrlimit with RLIMIT_AS is available and usable.
    """
    return resource is not None and hasattr(resource, "setrlimit") and hasattr(resource, "RLIMIT_AS")


def _kill_process_tree(processes):
    """
    Kill a list of psutil.Process or Popen-like objects if possible.
    Accepts mixed list; ignores errors.
    """
    if not processes:
        return
    for pr in processes:
        try:
            # if it's a psutil.Process
            if hasattr(pr, "kill"):
                pr.kill()
            else:
                # fallback: try os-level kill if has pid
                pid = getattr(pr, "pid", None)
                if pid:
                    try:
                        os.kill(pid, 9)
                    except Exception:
                        pass
        except Exception:
            pass


def _monitor_and_enforce(proc: subprocess.Popen, mem_limit_mb: Optional[int], timeout: Optional[int]) -> bool:
    """
    Monitor proc and its children for memory usage and timeout.
    Returns True if process ended with exit code 0; False if killed or non-zero exit.
    """

    start = time.time()
    poll_interval = 0.2  # seconds

    # If psutil not available and no mem limit requested, just wait with timeout
    if psutil is None and mem_limit_mb is None:
        try:
            ret = proc.wait(timeout=timeout)
            return ret == 0
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except Exception:
                pass
            return False

    # prepare psutil Process wrapper if possible
    p = None
    procs_list = []  # always defined to avoid unbound variable
    try:
        if psutil is not None:
            p = psutil.Process(proc.pid)
    except Exception:
        p = None

    # Monitoring loop
    while True:
        # timeout check
        if timeout is not None and (time.time() - start) > timeout:
            try:
                # try psutil kill if available
                if p is not None:
                    try:
                        procs_list = [p] + p.children(recursive=True)
                    except Exception:
                        procs_list = [p]
                    _kill_process_tree(procs_list)
                else:
                    proc.kill()
            except Exception:
                pass
            return False

        # check if process finished
        if proc.poll() is not None:
            # finished
            return proc.returncode == 0

        # compute memory usage of process tree (RSS)
        rss = 0
        try:
            if p is not None:
                try:
                    procs_list = [p] + p.children(recursive=True)
                except Exception:
                    procs_list = [p]
                for pr in procs_list:
                    try:
                        rss += pr.memory_info().rss
                    except Exception:
                        # ignore processes we can't query
                        pass
            else:
                procs_list = []
        except Exception:
            procs_list = []

        if mem_limit_mb is not None:
            limit_bytes = int(mem_limit_mb) * 1024 * 1024
            if rss > limit_bytes:
                # exceeds memory limit — kill process tree
                try:
                    if procs_list:
                        _kill_process_tree(procs_list)
                    else:
                        proc.kill()
                except Exception:
                    pass
                return False

        time.sleep(poll_interval)


def run_cmd_sandbox(cmd: str,
                    timeout: Optional[int] = None,
                    mem_limit_mb: Optional[int] = None,
                    cwd: Optional[str] = None) -> bool:
    """
    Cross-platform sandbox runner.
      - Creates working directory if missing.
      - On POSIX, tries resource.setrlimit (best-effort) before exec.
      - Uses psutil (if available) to monitor memory on all platforms.
      - Enforces timeout and kills process tree on violations.
    Returns True if command succeeded (exit code 0), False otherwise.
    """
    cwd = cwd or os.getcwd()
    os.makedirs(cwd, exist_ok=True)

    # POSIX preexec to set RLIMIT_AS if available (best-effort)
    preexec_fn = None
    if os.name != 'nt' and _can_setrlimit() and mem_limit_mb:
        def _preexec():
            try:
                soft = hard = int(mem_limit_mb) * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (soft, hard))
            except Exception:
                # best-effort: ignore failures to set limits
                pass
        preexec_fn = _preexec

    # Start process with Popen so we can monitor/kill it on Windows
    try:
        proc = subprocess.Popen(cmd, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=preexec_fn)
    except TypeError:
        # Some Windows Pythons/platforms may error if preexec_fn passed unexpectedly; fallback
        proc = subprocess.Popen(cmd, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    success = _monitor_and_enforce(proc, mem_limit_mb, timeout)

    # try to collect output (non-blocking small read)
    try:
        out, err = proc.communicate(timeout=0.1)
    except Exception:
        out, err = b"", b""

    # optionally, you can log out.decode() / err.decode()
    return success
