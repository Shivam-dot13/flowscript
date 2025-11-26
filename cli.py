# cli.py (updated run-bytecode handling)
import sys
import time
import threading
from flowc import parser
from flowc import semantic, ir as irmod, codegen, bytecode as bcmod
from flowrun.runtime import Runtime
from flowrun.runtime_parallel import ParallelRuntime
from flowrun.vm import ParallelVM, load_bytecode
from flowc.visualize import render_workflow_to_file
from flowrun.metrics import start_metrics_server

USAGE = """
Usage:
  python cli.py parse <file>
  python cli.py check <file>
  python cli.py transpile <file> <out.py>
  python cli.py emit-bytecode <file> <out.bc.json>
  python cli.py run-bytecode <out.bc.json> [mem_limit_mb] [max_workers]
  python cli.py run <file>
  python cli.py run-parallel <file> [max_workers] [mem_limit_mb]
  python cli.py visualize <file> <out.png|out.svg>
"""

def do_run_with_monitor(bytecode_path, port: int = 8000, mem_limit_mb=None, max_workers=None):
    # start metrics server in background thread (start_http_server is non-blocking but this ensures clarity)
    start_metrics_server(int(port))

    print(f"Metrics available at http://localhost:{port}/metrics")
    # run the bytecode in same process so metrics update
    from flowrun.vm import ParallelVM, load_bytecode
    bc = load_bytecode(bytecode_path)
    vm = ParallelVM(bc, mem_limit_mb=(int(mem_limit_mb) if mem_limit_mb else None),
                    max_workers=(int(max_workers) if max_workers else None))
    ok = vm.execute()
    print("VM completed" if ok else "VM failed")
def do_parse(path):
    src = open(path).read()
    ast = parser.parse(src)
    print(ast)
    return ast

def do_check(path):
    ast = do_parse(path)
    order = semantic.semantic_check(ast)
    print("Semantic OK. Topo order:", order)
    return ast, order

def do_transpile(path, out):
    ast, order = do_check(path)
    ir = irmod.workflow_to_ir(ast)
    name_to_instr = {instr["step"]: instr for instr in ir}
    ordered_ir = [name_to_instr[n] for n in order]
    codegen.transpile(ordered_ir, out)

def do_emit_bytecode(path, outbc):
    ast, order = do_check(path)
    ir = irmod.workflow_to_ir(ast)
    # convert notifies AST objects to simple dicts
    notifies = []
    for n in getattr(ast, "notifies", []):
        notifies.append({
            "name": n.name,
            "email": getattr(n, "email", None),
            "subject": getattr(n, "subject", None),
            "body": getattr(n, "body", None)
        })
    bcmod.emit_bytecode(ast.name, ir, outbc, notifies=notifies)


def do_run_bytecode(path, mem_limit_mb=None, max_workers=None):
    bc = load_bytecode(path)
    vm = ParallelVM(bc, mem_limit_mb=(int(mem_limit_mb) if mem_limit_mb else None), max_workers=(int(max_workers) if max_workers else None))
    ok = vm.execute()
    print("VM completed" if ok else "VM failed")

# remaining functions unchanged...
def do_run(path):
    ast, order = do_check(path)
    ir = irmod.workflow_to_ir(ast)
    name_to_instr = {instr["step"]: instr for instr in ir}
    ordered_ir = [name_to_instr[n] for n in order]
    r = Runtime(ordered_ir)
    ok = r.execute()
    print("Workflow completed" if ok else "Workflow failed")

def do_run_parallel(path, max_workers=None, mem_limit_mb=None):
    ast, order = do_check(path)
    ir = irmod.workflow_to_ir(ast)
    r = ParallelRuntime(ir, max_workers=(int(max_workers) if max_workers else None), mem_limit_mb=(int(mem_limit_mb) if mem_limit_mb else None))
    ok = r.execute()
    print("Workflow completed" if ok else "Workflow failed")

def do_visualize(path, outpath):
    ast, order = do_check(path)
    out = render_workflow_to_file(ast, outpath)
    print("Rendered:", out)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(USAGE)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "parse":
        do_parse(sys.argv[2])
    elif cmd == "check":
        do_check(sys.argv[2])
    elif cmd == "transpile":
        do_transpile(sys.argv[2], sys.argv[3])
    elif cmd == "emit-bytecode":
        do_emit_bytecode(sys.argv[2], sys.argv[3])
    elif cmd == "run-bytecode":
        # usage: python cli.py run-bytecode out/backup.bc.json [mem_limit_mb] [max_workers]
        path = sys.argv[2]
        mem = sys.argv[3] if len(sys.argv) > 3 else None
        workers = sys.argv[4] if len(sys.argv) > 4 else None
        do_run_bytecode(path, mem_limit_mb=mem, max_workers=workers)
    elif cmd == "run":
        do_run(sys.argv[2])
    elif cmd == "run-parallel":
        max_workers = sys.argv[3] if len(sys.argv) > 3 else None
        mem_limit_mb = sys.argv[4] if len(sys.argv) > 4 else None
        do_run_parallel(sys.argv[2], max_workers=max_workers, mem_limit_mb=mem_limit_mb)
    elif cmd == "visualize":
        if len(sys.argv) < 4:
            print("Usage: python cli.py visualize <file> <out.png|out.svg>")
            sys.exit(1)
        do_visualize(sys.argv[2], sys.argv[3])
    elif cmd == "start-monitor":
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
        from flowrun.metrics import start_metrics_server
        start_metrics_server(port)
        # block so server stays alive
        print(f"Metrics server running at http://localhost:{port}/")
        print("Press Ctrl+C to stop metrics server")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            print("Metrics server stopped")
    elif cmd == "run-with-monitor":
        # usage: python cli.py run-with-monitor out/backup.bc.json 8000 [mem_limit_mb] [max_workers]
        path = sys.argv[2]
        port = sys.argv[3] if len(sys.argv) > 3 else 8000
        mem = sys.argv[4] if len(sys.argv) > 4 else None
        workers = sys.argv[5] if len(sys.argv) > 5 else None
        do_run_with_monitor(path, port, mem_limit_mb=mem, max_workers=workers)

    else:
        print(USAGE)
