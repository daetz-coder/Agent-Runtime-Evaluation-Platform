"""
Prometheus metrics for the Agent Evaluation Platform.

Exposes operational metrics at /metrics endpoint for Prometheus scraping.

Key metrics:
  - Evaluation duration, count, success/failure rates
  - LLM call latency and token usage per provider
  - Tool execution counts and error rates
  - HTTP request latency

Usage:
  # In any module:
  from app.core.metrics import EVALUATION_DURATION, EVALUATION_COUNT
  with EVALUATION_DURATION.time():
      await run_evaluation()
  EVALUATION_COUNT.labels(status="success").inc()
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram, Info

# ── Evaluation Metrics ────────────────────────────────────────

EVALUATION_COUNT = Counter(
    "agent_eval_evaluation_total",
    "Total number of evaluations",
    ["status"],  # status: success/failed
)

EVALUATION_DURATION = Histogram(
    "agent_eval_evaluation_duration_seconds",
    "Evaluation duration in seconds",
    ["mode"],
    buckets=[5, 15, 30, 60, 120, 300, 600],
)

EVALUATION_SCORE = Histogram(
    "agent_eval_evaluation_score",
    "Evaluation overall score distribution",
    buckets=[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
)

# ── Agent Runtime Metrics ────────────────────────────────────

AGENT_STEPS = Histogram(
    "agent_eval_agent_steps",
    "Number of steps taken by agent per run",
    buckets=[1, 3, 5, 10, 15, 20, 30, 50],
)

AGENT_RUN_DURATION = Histogram(
    "agent_eval_agent_run_duration_seconds",
    "Agent run duration in seconds",
    buckets=[10, 30, 60, 120, 300, 600],
)

# ── LLM Metrics ──────────────────────────────────────────────

LLM_CALL_COUNT = Counter(
    "agent_eval_llm_calls_total",
    "Total LLM API calls",
    ["provider", "model"],
)

LLM_CALL_DURATION = Histogram(
    "agent_eval_llm_call_duration_seconds",
    "LLM call latency",
    ["provider"],
    buckets=[0.5, 1, 2, 5, 10, 30, 60],
)

LLM_TOKENS = Counter(
    "agent_eval_llm_tokens_total",
    "Total LLM tokens consumed",
    ["model", "type"],  # type: input/output
)

# ── Tool Metrics ──────────────────────────────────────────────

TOOL_CALL_COUNT = Counter(
    "agent_eval_tool_calls_total",
    "Total tool calls",
    ["tool", "status"],  # status: success/failed/timeout
)

TOOL_CALL_DURATION = Histogram(
    "agent_eval_tool_call_duration_seconds",
    "Tool execution duration",
    ["tool"],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60],
)

# ── HTTP Metrics ──────────────────────────────────────────────

HTTP_REQUEST_COUNT = Counter(
    "agent_eval_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "agent_eval_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 5, 10, 30],
)

# ── App Info ──────────────────────────────────────────────────

APP_INFO = Info(
    "agent_eval",
    "Agent Evaluation Platform information",
)
