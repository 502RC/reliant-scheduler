"""Prometheus metrics definitions for Reliant Scheduler.

All application-level Prometheus metrics are defined here so that they
can be imported by middleware, services, and the ``/metrics`` endpoint.
"""

from prometheus_client import Counter, Gauge, Histogram

# ---------------------------------------------------------------------------
# HTTP request metrics (populated by CorrelationIdMiddleware)
# ---------------------------------------------------------------------------
HTTP_REQUESTS_TOTAL = Counter(
    "reliant_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "reliant_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "reliant_http_requests_in_progress",
    "HTTP requests currently being processed",
    ["method", "path"],
)

# ---------------------------------------------------------------------------
# Job execution metrics
# ---------------------------------------------------------------------------
JOB_RUNS_TOTAL = Counter(
    "reliant_job_runs_total",
    "Total job runs by status",
    ["status"],
)

JOB_RUN_DURATION = Histogram(
    "reliant_job_run_duration_seconds",
    "Job run duration in seconds",
    ["job_type"],
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600, 1800, 3600),
)

JOBS_ENQUEUED_TOTAL = Counter(
    "reliant_jobs_enqueued_total",
    "Total jobs enqueued to Service Bus",
)

# ---------------------------------------------------------------------------
# Queue depth and agent status
# ---------------------------------------------------------------------------
QUEUE_DEPTH = Gauge(
    "reliant_queue_depth",
    "Current depth of the job queue",
    ["queue_name"],
)

AGENTS_CONNECTED = Gauge(
    "reliant_agents_connected",
    "Number of currently connected worker agents",
)

AGENTS_BY_STATUS = Gauge(
    "reliant_agents_by_status",
    "Agent count by status",
    ["status"],
)

# ---------------------------------------------------------------------------
# SLA metrics
# ---------------------------------------------------------------------------
SLA_BREACHES_TOTAL = Counter(
    "reliant_sla_breaches_total",
    "Total SLA breach events",
)

SLA_AT_RISK_TOTAL = Counter(
    "reliant_sla_at_risk_total",
    "Total SLA at-risk events",
)

# ---------------------------------------------------------------------------
# Health check metrics
# ---------------------------------------------------------------------------
HEALTH_CHECK_STATUS = Gauge(
    "reliant_health_check_status",
    "Health check result per dependency (1 = healthy, 0 = unhealthy)",
    ["dependency"],
)
