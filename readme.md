
# **FlowScript – A Lightweight Workflow Automation DSL + Compiler, Runtime, and Web UI**

FlowScript is a **custom domain-specific language (DSL)** designed to define, visualize, and execute multi-step workflows.
It includes a full **compiler pipeline**, **parallel execution engine**, and a **modern Web UI** with live logs, step status updates, and DAG visualization.

This project demonstrates concepts from **compilers**, **concurrency**, **runtime systems**, and **DevOps automation**, packaged into an understandable and practical system.

---

## 🚀 **Features**

### ✔️ **1. Custom DSL (FlowScript)**

Easy, human-readable workflow definition language:

```txt
workflow backup {
  trigger cron "0 2 * * *"
  env VARS { BACKUP_DIR = "/tmp/backup" }

  step dump_db {
    run "mysqldump mydb > db.sql"
    retries 2
    timeout 600s
  }

  step compress {
    depends_on dump_db
    run "tar -czf ${BACKUP_DIR}/db.tar.gz db.sql"
  }

  notify notify_admin {
    "your@email.com"
    "Backup Failed!"
    "Step failed: ${failed_step}"
  }
}
```

---

### ✔️ **2. Full Compiler Pipeline**

FlowScript includes:

* **Lexer + Parser** (Lark)
* **AST Builder**
* **Semantic Analyzer**
* **IR (Intermediate Representation)**
* **Bytecode Generator**
* **Bytecode Loader & Executor**
* **Safe Command Sandbox** (Windows compatible)

---

### ✔️ **3. Parallel Execution Engine**

A Python-based runtime capable of:

* Executing independent workflow steps in parallel
* Enforcing memory limits
* Retrying failed steps
* Handling timeouts
* Triggering notifications on failure
* Graceful cancellation

---

### ✔️ **4. DAG Visualization**

Every workflow automatically emits:

* A **DAG (Directed Acyclic Graph)** PNG/SVG showing step dependencies
* Node coloring for **running / success / failed**
* Updated in real time in the Web UI

Powered by: **Graphviz**

---

### ✔️ **5. Modern Web UI**

A full Flask-based web dashboard:

* Upload `.flow` files
* Edit workflows live
* Visual DAG preview
* Generate bytecode
* Run workflows
* Live logs (Server-Sent Events)
* Live step-status updates
* Stop/cancel workflow

---

### ✔️ **6. Monitoring & Metrics**

Exports Prometheus metrics:

* Total steps started
* Steps succeeded
* Steps failed
* Running steps
* Notifications emitted

---

## 🧩 **Architecture Overview**

```
FlowScript Source (.flow)
         │
         ▼
   Parser (Lark)
         │
         ▼
Abstract Syntax Tree (AST)
         │
         ▼
  Semantic Analyzer
         │
         ▼
      IR Builder
         │
         ▼
  Bytecode (.bc.json)
         │
         ▼
Parallel Execution VM
         │
         ├── Logs
         ├── Notifications
         ├── Prometheus Metrics
         └── DAG Node Status
```

---

## 🛠️ **Tech Stack**

| Component        | Technology               |
| ---------------- | ------------------------ |
| DSL Parsing      | Lark Parser              |
| Compiler Backend | Python                   |
| Runtime VM       | Python (thread/parallel) |
| Web UI           | Flask + HTML/JS          |
| Live Logs        | Server Sent Events (SSE) |
| Visualization    | Graphviz                 |
| Monitoring       | Prometheus client        |
| Sandbox          | psutil + subprocess      |

---

## 📦 **Installation**

### Clone the repo

```bash
git clone https://github.com/<your-username>/flowscript
cd flowscript
```

### Create virtual environment

```bash
python -m venv venv
venv\Scripts\activate
```

### Install dependencies

```bash
pip install -r requirements.txt
```

---

## ▶️ **How to Use**

### 1. Run the Web UI

```bash
python webui/app.py
```

Open:
👉 [http://localhost:5000](http://localhost:5000)

### 2. Run compiler/debug tools

```bash
python cli.py parse examples/backup.flow
python cli.py check examples/backup.flow
python cli.py transpile examples/backup.flow out/run_backup.py
python cli.py emit-bytecode examples/backup.flow out/backup.bc.json
```

### 3. Run with metrics

```bash
python cli.py run-with-monitor out/backup.bc.json 8000
```

Metrics at:
👉 [http://localhost:8000/metrics](http://localhost:8000/metrics)

---

## 📊 **Screenshots**

(You can add these once UI is working)

* UML diagram
* DAG visualization
* Web UI main page
* Logs streaming
* Metrics screenshot

---

## 🧪 **Testing**

```bash
pytest -q
```

---

## 📚 **Project Goal**

This project was built as a **major academic project** showcasing:

* DSL design
* Compiler construction
* Static + dynamic analysis
* Workflow automation
* Parallel runtimes
* Monitoring & observability
* Web-based control systems

---

## 🚧 **Future Enhancements**

* Built-in step caching
* More backends (e.g. Docker runner)
* Real notification email sending
* Web-based DAG editor
* Workflow versioning + history

---

## 💡 **Why This Project Is Unique**

Unlike typical college projects (todo apps, URL detection, ML models), this project:
* Invents a **new language**, not just an app
* Builds a real **compiler + VM**
* Handles concurrency, cancellation, sandboxing
* Includes **visualization and monitoring**
* Has a **professional-grade UI**
* Demonstrates deep system design skills
---

## 🧑‍💻 **Author**

Shivam Dhariwal
✔ UML diagrams (DFD, Class diagram, Activity, Sequence)
✔ Installation guide
✔ API documentation

Just tell me: **"Generate report"** or **"Generate PPT"**.
