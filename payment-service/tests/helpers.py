from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class TrackingSession:
    """Minimal session double: detects a provider call inside a DB transaction."""

    def __init__(self) -> None:
        self.active_transactions = 0
        self.started_transactions = 0

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[None]:
        assert self.active_transactions == 0
        self.active_transactions += 1
        self.started_transactions += 1
        try:
            yield
        finally:
            self.active_transactions -= 1

    async def refresh(self, _object: object) -> None:
        pass
