# flowrun/metrics.py
from prometheus_client import Counter, Gauge, start_http_server

# Counters
steps_started = Counter("flowscript_steps_started_total", "Total steps started")
steps_succeeded = Counter("flowscript_steps_succeeded_total", "Total steps succeeded")
steps_failed = Counter("flowscript_steps_failed_total", "Total steps failed")
notifications_sent = Counter("flowscript_notifications_sent_total", "Total notifications emitted")

# Gauges
running_steps = Gauge("flowscript_running_steps", "Current running steps")

def start_metrics_server(port: int = 8000):
    """
    Starts the Prometheus metrics HTTP server on given port (non-blocking).
    """
    start_http_server(port)
    print(f"[metrics] Prometheus metrics server started on :{port}")
