"""
AsyncReporter - Background batch reporting of trajectory data.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Any, Dict, List, Optional

import httpx

from agent_eval_sdk.exceptions import ReportingError
from agent_eval_sdk.models import (
    EvaluationRequest,
    EvaluationResponse,
    TaskCreate,
    TaskResponse,
    TrajectoryStep,
)

logger = logging.getLogger("agent_eval_sdk.reporter")


def with_retry(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
    """Simple retry decorator with exponential backoff."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (ConnectionError, TimeoutError, OSError, httpx.TransportError) as e:
                    last_exception = e
                    if attempt == max_retries:
                        raise ReportingError(f"Failed after {max_retries} retries: {e}") from e
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    import random
                    jitter = random.uniform(0, delay * 0.5)
                    time.sleep(delay + jitter)
            raise ReportingError("Unexpected retry loop exit") from last_exception
        return wrapper
    return decorator


class AsyncReporter:
    """
    Async Reporter - Batch send trajectory data in background thread.

    Design:
    - Use queue.Queue for thread-safe data passing
    - Batch send when batch_size or flush_interval reached
    - Built-in exponential backoff retry
    - Graceful shutdown: stop() flushes remaining data

    Why sync httpx + background thread instead of asyncio:
    - SDK needs to support both sync and async agents
    - Background thread is transparent to user code
    - Avoids conflicts with user event loops
    """

    def __init__(self, config):
        self._config = config
        self._task_id: Optional[str] = None
        self._queue: queue.Queue = queue.Queue(maxsize=config.max_queue_size)
        self._flush_event = threading.Event()
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._http: Optional[httpx.Client] = None

    # ---- Lifecycle ----

    def start(self, task_id: str) -> None:
        """Start reporter."""
        self._task_id = task_id
        self._http = httpx.Client(
            base_url=self._config.api_base_url,
            timeout=self._config.api_timeout,
            headers=self._build_headers(),
        )
        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="agent-eval-reporter",
            daemon=True,
        )
        self._worker_thread.start()

    def stop(self) -> None:
        """Stop reporter, wait for remaining data to be sent."""
        self._stop_event.set()
        self._flush_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10.0)
        if self._http:
            self._http.close()
            self._http = None

    # ---- Data Enqueue ----

    def enqueue(self, step: TrajectoryStep) -> None:
        """Put step into report queue."""
        try:
            self._queue.put_nowait(step)
        except queue.Full:
            logger.warning("Report queue is full, dropping step %d", step.step_number)

    def flush(self) -> None:
        """Trigger immediate flush of all queued data."""
        self._flush_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            deadline = time.monotonic() + 5.0
            while not self._queue.empty() and time.monotonic() < deadline:
                time.sleep(0.1)

    # ---- Sync API (executed in calling thread) ----

    def create_task_sync(self, task_data: TaskCreate) -> TaskResponse:
        """Synchronously create a task."""
        response = self._ensure_http().post(
            "/api/v1/tasks/",
            json=task_data.model_dump(),
        )
        response.raise_for_status()
        return TaskResponse(**response.json())

    def mark_task_complete_sync(self, task_id: str) -> None:
        """Synchronously mark task complete (no-op for now)."""
        pass

    def run_evaluation_sync(self, task_id: str) -> EvaluationResponse:
        """Synchronously trigger evaluation."""
        response = self._ensure_http().post(
            "/api/v1/evaluations/",
            json=EvaluationRequest(task_id=task_id).model_dump(),
        )
        response.raise_for_status()
        return EvaluationResponse(**response.json())

    # ---- Background Worker Thread ----

    def _worker_loop(self) -> None:
        """Background thread main loop."""
        while not self._stop_event.is_set():
            self._flush_event.wait(timeout=self._config.flush_interval)
            self._flush_event.clear()
            self._drain_and_send()
        self._drain_and_send()

    def _drain_and_send(self) -> None:
        """Drain queue and send batch."""
        steps: List[TrajectoryStep] = []
        while len(steps) < self._config.batch_size:
            try:
                step = self._queue.get_nowait()
                steps.append(step)
            except queue.Empty:
                break
        if steps:
            self._send_batch(steps)

    @with_retry(max_retries=3, base_delay=1.0, max_delay=30.0)
    def _send_batch(self, steps: List[TrajectoryStep]) -> None:
        """
        Send a batch of trajectory steps to backend API.

        Endpoint: POST /api/v1/tasks/{task_id}/trajectory
        Body: List[TrajectoryStep] (direct array, matches backend tasks.py line 67)
        """
        if not self._http or not self._task_id:
            return

        payload = [step.model_dump_for_api() for step in steps]

        try:
            response = self._http.post(
                f"/api/v1/tasks/{self._task_id}/trajectory",
                json=payload,
            )
            response.raise_for_status()
            logger.debug("Sent %d steps for task %s", len(steps), self._task_id)
        except httpx.HTTPStatusError as e:
            raise ReportingError(
                f"HTTP {e.response.status_code} sending trajectory: {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            raise ReportingError(f"Request failed: {e}") from e

    # ---- Internal Helpers ----

    def _build_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        return headers

    def _ensure_http(self) -> httpx.Client:
        if self._http is None:
            self._http = httpx.Client(
                base_url=self._config.api_base_url,
                timeout=self._config.api_timeout,
                headers=self._build_headers(),
            )
        return self._http
