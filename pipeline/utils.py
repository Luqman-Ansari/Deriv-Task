"""Shared utilities for the pipeline."""
import re
import time

from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError


def _parse_retry_after(error_msg: str) -> float | None:
    """Extract the suggested retry delay (seconds) from a 429 error message."""
    match = re.search(r"retry in (\d+(?:\.\d+)?)s", error_msg, re.IGNORECASE)
    return float(match.group(1)) if match else None


def run_with_retry(agent: Agent, prompt: str, *, max_retries: int = 6) -> object:
    """
    Call agent.run_sync(prompt) and automatically retry on 429 rate-limit errors.

    On each 429 the suggested 'retry in Xs' delay from the API response is used
    when available, otherwise an exponential back-off starting at 20 s is applied.
    """
    for attempt in range(max_retries):
        try:
            return agent.run_sync(prompt)
        except ModelHTTPError as exc:
            if exc.status_code != 429 or attempt == max_retries - 1:
                raise

            suggested = _parse_retry_after(str(exc))
            wait = (suggested + 2) if suggested else (20 * 2 ** attempt)
            print(
                f"\n    [rate-limit] 429 received. "
                f"Waiting {wait:.0f}s before retry {attempt + 1}/{max_retries - 1} ...",
                end=" ",
                flush=True,
            )
            time.sleep(wait)
            print("retrying")
