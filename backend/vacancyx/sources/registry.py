"""Explicit registry for configured job-source adapters."""

from vacancyx.sources.config import SourceConfig
from vacancyx.sources.contracts import JobSourceAdapter


class SourceRegistry:
    """Keep adapter implementations separate from source enablement and policy config."""

    def __init__(self) -> None:
        self._entries: dict[str, tuple[JobSourceAdapter, SourceConfig]] = {}

    def register(self, adapter: JobSourceAdapter, config: SourceConfig) -> None:
        """Register one adapter; duplicate or mismatched identifiers are rejected."""
        if adapter.source_key != config.source_key:
            raise ValueError("Adapter source_key must match its SourceConfig.")
        if adapter.source_key in self._entries:
            raise ValueError(f"Source adapter already registered: {adapter.source_key}")
        self._entries[adapter.source_key] = (adapter, config)

    def get(self, source_key: str) -> tuple[JobSourceAdapter, SourceConfig]:
        """Return an enabled adapter and its configuration."""
        try:
            adapter, config = self._entries[source_key]
        except KeyError as exc:
            raise KeyError(f"Unknown source adapter: {source_key}") from exc
        if not config.enabled:
            raise ValueError(f"Source adapter is disabled: {source_key}")
        return adapter, config

    def enabled_source_keys(self) -> tuple[str, ...]:
        """Return enabled source identifiers in deterministic registration order."""
        return tuple(
            key for key, (_adapter, config) in self._entries.items() if config.enabled
        )
