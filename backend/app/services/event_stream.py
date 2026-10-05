"""
ReviewEventStream — in-process pub/sub for SSE streaming.

One ReviewEventStream is created per review. The background runner
publishes events as each graph node completes. Any number of SSE
clients can subscribe and receive all events (including replayed
past events for late-connecting clients).

Architecture:
  Runner  → publish(event) → stored in self.events + wakes waiters
  SSE endpoint → subscribe() → replay past + stream new events
"""
import asyncio
import logging
from datetime import datetime

from app.models.review import StreamEvent

logger = logging.getLogger(__name__)


class ReviewEventStream:
    def __init__(self, review_id: str):
        self.review_id = review_id
        self.events: list[StreamEvent] = []
        self._done = False
        self._waiters: list[asyncio.Event] = []

    def publish(self, event: StreamEvent) -> None:
        self.events.append(event)
        if event.event in ("done", "error"):
            self._done = True
        # Wake all waiting subscribers
        for waiter in self._waiters:
            waiter.set()

    async def subscribe(self, timeout: float = 120.0):
        """
        Async generator — yields StreamEvents in order.
        Replays already-published events, then streams new ones.
        Stops when a 'done' or 'error' event is received, or timeout expires.
        """
        pos = 0
        deadline = asyncio.get_event_loop().time() + timeout

        while True:
            # Yield all buffered events from current position
            while pos < len(self.events):
                yield self.events[pos]
                pos += 1

            # Check if finished
            if self._done and pos >= len(self.events):
                break

            # Wait for next event with timeout
            waiter = asyncio.Event()
            self._waiters.append(waiter)
            try:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    logger.warning("SSE stream timed out for review %s", self.review_id)
                    yield StreamEvent(event="error", message="Stream timed out")
                    break
                await asyncio.wait_for(waiter.wait(), timeout=min(remaining, 5.0))
            except asyncio.TimeoutError:
                # Check for new events after timeout (prevents tight loops)
                continue
            finally:
                self._waiters.discard(waiter) if hasattr(self._waiters, 'discard') else None
                try:
                    self._waiters.remove(waiter)
                except ValueError:
                    pass
