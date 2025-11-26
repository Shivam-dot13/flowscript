# webui/app.py
import os, sys
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import uuid, time, threading, queue
from flask import Flask, request, render_template, send_file, jsonify, Response, redirect, url_for
from flask_cors import CORS
from werkzeug.utils import secure_filename

from flowc import parser, semantic, ir as irmod, bytecode as bcmod
from flowc.visualize import workflow_to_dot, render_workflow_to_file
from flowrun.vm import ParallelVM, load_bytecode

UPLOAD_DIR = os.path.abspath("webui_uploads")
OUT_DIR = os.path.abspath("webui_out")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

ALLOWED_EXT = {".flow", ".txt"}

app = Flask(__name__, template_folder="templates")
CORS(app)

# RUNS structure:
# RUNS[run_id] = {
#   thread, stop_event (threading.Event), log_path, status: str,
#   done: bool, status_q: queue.Queue, status_map: {step:status}
# }
RUNS = {}

def allowed_filename(filename):
    _, ext = os.path.splitext(filename)
    return ext.lower() in ALLOWED_EXT

def sse_stream_file(log_path, stop_event):
    last_pos = 0
    open(log_path, "a").close()
    with open(log_path, "r", encoding="utf-8", errors="ignore") as fh:
        fh.seek(0, os.SEEK_END)
        last_pos = fh.tell()
    while not stop_event.is_set():
        with open(log_path, "r", encoding="utf-8", errors="ignore") as fh:
            fh.seek(last_pos)
            data = fh.read()
            if data:
                last_pos = fh.tell()
                for line in data.splitlines():
                    yield f"data: {line}\n\n"
            else:
                time.sleep(0.3)
    # final flush
    with open(log_path, "r", encoding="utf-8", errors="ignore") as fh:
        fh.seek(last_pos)
        data = fh.read()
        if data:
            for line in data.splitlines():
                yield f"data: {line}\n\n"
    yield "data: [STREAM-CLOSED]\n\n"

def sse_stream_status(run_id):
    info = RUNS.get(run_id)
    if not info:
        yield "data: {}\n\n"
        return
    q = info["status_q"]
    # immediate dump of current map
    try:
        for step, st in info.get("status_map", {}).items():
            yield f"data: {{\"type\":\"status\",\"step\":\"{step}\",\"status\":\"{st}\"}}\n\n"
    except Exception:
        pass
    while True:
        try:
            item = q.get(timeout=0.5)
            # item is (step, status)
            step, st = item
            yield f"data: {{\"type\":\"status\",\"step\":\"{step}\",\"status\":\"{st}\"}}\n\n"
            if info.get("done") and q.empty():
                break
        except queue.Empty:
            # if run done and queue empty -> exit
            if info.get("done"):
                break
            continue
    yield "data: [STATUS-STREAM-CLOSED]\n\n"

def status_callback_factory(run_id):
    """
    Returns a callback that VM calls as status_callback(step, status)
    It will write to RUNS[run_id]["status_q"] and update status_map and the log file.
    """
    def cb(step, status):
        info = RUNS.get(run_id)
        if not info:
            return
        # update map
        info["status_map"][step] = status
        # push to queue
        try:
            info["status_q"].put((step, status), block=False)
        except Exception:
            pass
        # also append to log file
        try:
            with open(info["log_path"], "a", encoding="utf-8") as fh:
                fh.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] STATUS {step} -> {status}\n")
        except Exception:
            pass
    return cb

def run_workflow_background(run_id, bytecode_path, mem_limit_mb, max_workers, workdir):
    run_info = RUNS[run_id]
    run_info["status"] = "running"
    run_info["status_map"] = {}
    cb = status_callback_factory(run_id)
    cancel_event = run_info["stop_event"]

    vm = ParallelVM(load_bytecode(bytecode_path),
                    workdir=workdir,
                    mem_limit_mb=mem_limit_mb,
                    max_workers=max_workers,
                    status_callback=cb,
                    cancel_event=cancel_event)
    # execute
    try:
        ok = vm.execute()
        run_info["status"] = "finished" if ok else "failed"
    except Exception as e:
        with open(run_info["log_path"], "a", encoding="utf-8") as fh:
            fh.write(f"[EXCEPTION] {e}\n")
        run_info["status"] = "error"
    finally:
        run_info["done"] = True
        # ensure last statuses are pushed
        try:
            run_info["status_q"].put(("__done__", "1"), block=False)
        except Exception:
            pass

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/files")
def files_api():
    out = []
    for fn in os.listdir(UPLOAD_DIR):
        if allowed_filename(fn):
            out.append(fn)
    return jsonify(sorted(out))

@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    if not f:
        return "No file", 400
    filename = secure_filename(f.filename)
    if not allowed_filename(filename):
        return "Invalid file type", 400
    dest = os.path.join(UPLOAD_DIR, filename)
    f.save(dest)
    return redirect(url_for("index"))

@app.route("/raw/<filename>")
def raw_file(filename):
    path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(path):
        return "Not found", 404
    return send_file(path, mimetype="text/plain")

@app.route("/save/<filename>", methods=["POST"])
def save_file(filename):
    data = request.json or {}
    content = data.get("content", "")
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return jsonify({"ok": True})

@app.route("/emit/<filename>", methods=["POST"])
def emit_bytecode_endpoint(filename):
    src_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(src_path):
        return "File not found", 404
    try:
        with open(src_path, "r", encoding="utf-8") as fh:
            src = fh.read()
        ast = parser.parse(src)
        semantic.semantic_check(ast)
    except Exception as e:
        return f"Parse/semantic error: {e}", 400

    ir = irmod.workflow_to_ir(ast)
    outbc = os.path.join(OUT_DIR, f"{filename}.bc.json")
    notifies = []
    for n in getattr(ast, "notifies", []):
        notifies.append({"name": n.name, "email": n.email, "subject": n.subject, "body": n.body})
    bcmod.emit_bytecode(ast.name, ir, outbc, notifies=notifies)

    # render SVG (for interactive coloring), store as .svg
    dot = workflow_to_dot(ast, show_details=True)
    dot.format = "svg"
    svg_out = os.path.join(OUT_DIR, f"{filename}.svg")
    if svg_out.endswith(".svg"):
        svg_base = svg_out[:-4]
    else:
        svg_base = svg_out
    dot.render(svg_base, cleanup=True)
    # dot.render creates svg_out; return base filename
    return jsonify({"bytecode": os.path.basename(outbc), "dag_svg": os.path.basename(svg_out)})

@app.route("/dag/<fname>")
def get_dag(fname):
    fpath = os.path.join(OUT_DIR, fname)
    if not os.path.exists(fpath):
        return "Not found", 404
    return send_file(fpath, mimetype="image/svg+xml")

@app.route("/start", methods=["POST"])
def start_run():
    data = request.json or {}
    bcname = data.get("bytecode")
    if not bcname:
        return "bytecode param required", 400
    bcpath = os.path.join(OUT_DIR, bcname)
    if not os.path.exists(bcpath):
        return "bytecode not found", 404
    mem = int(data.get("mem_limit_mb")) if data.get("mem_limit_mb") else None
    workers = int(data.get("max_workers")) if data.get("max_workers") else None

    run_id = str(uuid.uuid4())[:8]
    run_dir = os.path.join(OUT_DIR, f"run_{run_id}")
    os.makedirs(run_dir, exist_ok=True)
    log_path = os.path.join(run_dir, "run.log")

    RUNS[run_id] = {
        "thread": None,
        "stop_event": threading.Event(),
        "log_path": log_path,
        "status": "queued",
        "done": False,
        "status_q": queue.Queue(),
        "status_map": {}
    }

    t = threading.Thread(target=run_workflow_background, args=(run_id, bcpath, mem, workers, run_dir), daemon=True)
    RUNS[run_id]["thread"] = t
    t.start()
    return jsonify({"run_id": run_id})

@app.route("/stop/<run_id>", methods=["POST"])
def stop_run(run_id):
    info = RUNS.get(run_id)
    if not info:
        return "run not found", 404
    info["stop_event"].set()
    info["status"] = "stopping"
    return jsonify({"ok": True})

@app.route("/logs/<run_id>")
def get_logs(run_id):
    info = RUNS.get(run_id)
    if not info:
        return "run not found", 404
    path = info["log_path"]
    if not os.path.exists(path):
        return "", 200
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        data = fh.read()
    return Response(data, mimetype="text/plain")

@app.route("/stream/<run_id>")
def stream_logs(run_id):
    info = RUNS.get(run_id)
    if not info:
        return "run not found", 404
    return Response(sse_stream_file(info["log_path"], info["stop_event"]), mimetype="text/event-stream")

@app.route("/stream-status/<run_id>")
def stream_status(run_id):
    info = RUNS.get(run_id)
    if not info:
        return "run not found", 404
    return Response(sse_stream_status(run_id), mimetype="text/event-stream")

@app.route("/runs")
def list_runs():
    out = {}
    for rid, info in RUNS.items():
        out[rid] = {"status": info["status"], "log": os.path.basename(info["log_path"]), "done": info.get("done", False)}
    return jsonify(out)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
