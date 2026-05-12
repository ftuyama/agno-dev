"""OpenTelemetry tracing for Agno (spans persisted via the shared SQLite BaseDb)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

from game_dev_crew.config import tracing_enabled

if TYPE_CHECKING:
    from agno.db.base import AsyncBaseDb, BaseDb
    from agno.remote.base import RemoteDb


def maybe_setup_tracing(db: Union["BaseDb", "AsyncBaseDb", "RemoteDb", None]) -> None:
    """Configure global OTel + OpenInference when tracing is on and a database is available."""
    if db is None or not tracing_enabled():
        return
    from agno.tracing import setup_tracing

    setup_tracing(db=db)
