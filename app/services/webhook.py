"""
Webhook notification service with exponential backoff retry.

Features:
  - Exponential backoff (1s, 2s, 4s)
  - Max 3 retry attempts
  - Timeout per request (5s)
  - Failure logging with full context

Usage:
    from app.services.webhook import WebhookService
    await WebhookService.notify("evaluation.completed", {
        "task_id": "xxx",
        "evaluation_id": "yyy",
    })
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_DELAY = 1.0  # seconds
REQUEST_TIMEOUT = 5.0  # seconds


class WebhookService:
    """Sends webhook notifications with exponential backoff retry."""

    @staticmethod
    async def notify(event: str, payload: Dict[str, Any]) -> bool:
        """
        Send a webhook notification.

        Args:
            event: Event type (e.g., "evaluation.completed")
            payload: Event data

        Returns:
            True if delivered, False if all retries failed
        """
        webhook_url = settings.EVAL_WEBHOOK_URL
        if not webhook_url:
            return False

        body = {
            "event": event,
            **payload,
        }

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                    response = await client.post(webhook_url, json=body)

                if response.status_code < 300:
                    logger.info(
                        "Webhook delivered: event=%s, attempt=%d, status=%d",
                        event,
                        attempt,
                        response.status_code,
                    )
                    return True

                logger.warning(
                    "Webhook returned %d: event=%s, attempt=%d/%d",
                    response.status_code,
                    event,
                    attempt,
                    MAX_RETRIES,
                )

            except httpx.TimeoutException:
                logger.warning(
                    "Webhook timeout: event=%s, attempt=%d/%d",
                    event,
                    attempt,
                    MAX_RETRIES,
                )
            except httpx.HTTPError as e:
                logger.warning(
                    "Webhook HTTP error: event=%s, attempt=%d/%d, error=%s",
                    event,
                    attempt,
                    MAX_RETRIES,
                    e,
                )
            except Exception as e:
                logger.error(
                    "Webhook unexpected error: event=%s, attempt=%d/%d, error=%s",
                    event,
                    attempt,
                    MAX_RETRIES,
                    e,
                )

            # Exponential backoff before retry
            if attempt < MAX_RETRIES:
                delay = BASE_DELAY * (2 ** (attempt - 1))
                await asyncio.sleep(delay)

        logger.error(
            "Webhook delivery failed after %d attempts: event=%s, url=%s",
            MAX_RETRIES,
            event,
            webhook_url,
        )
        return False
