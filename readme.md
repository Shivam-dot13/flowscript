# FlowScript — Workflow Automation Compiler & Runtime

FlowScript is a domain-specific language (DSL) and execution engine for defining, compiling, and running automated workflows. It features a parallel virtual machine, dependency management, and a real-time Web UI.

## 🚀 Features
* **Custom DSL:** Clean syntax for defining steps, dependencies, and triggers.
* **Compiler:** Transpiles `.flow` code into optimized JSON bytecode.
* **Parallel VM:** Executes independent steps concurrently (Thread-based).
* **Sandboxing:** Enforces memory limits and timeouts per step.
* **Real-time UI:** Live DAG visualization and log streaming via Server-Sent Events (SSE).
* **Fault Tolerance:** Automatic retries and error handling notifications.

## 🛠️ Tech Stack
* **Language:** Python 3.13
* **Parser:** Lark (EBNF Grammar)
* **Backend:** Flask, APScheduler
* **Frontend:** HTML5, JavaScript (No frameworks), Ace Editor
* **Visualization:** Graphviz

## 📦 Installation

1.  **Clone the repository**
2.  **Install Graphviz** (Required for visualization)
    * Download from [graphviz.org](https://graphviz.org/) and add to System PATH.
3.  **Install Python Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

## ▶️ Usage

1.  **Start the Server**
    ```bash
    # PowerShell
    $env:FLASK_APP = "webui/app.py"
    python -m flask run --port 5000
    ```
2.  **Open Web UI**
    * Go to `http://localhost:5000`
3.  **Run a Workflow**
    * Upload a `.flow` file.
    * Click **Emit Bytecode**.
    * Click **Start Run**.

## 📄 Example Workflow

```flow
workflow data_pipeline {
  env CONFIG { DB_URL = "localhost:5432" }

  step fetch_data {
    run "echo 'fetching...'"
    timeout 10s
  }

  step process_data {
    depends_on fetch_data
    run "echo 'processing...'"
  }

  notify on_failure {
    email "admin@example.com" subject "Pipeline Failed"
  }
}
