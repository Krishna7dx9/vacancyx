"""Job-source adapter contracts and execution policy."""

from vacancyx.sources.config import SourceConfig
from vacancyx.sources.contracts import (
    JobSourceAdapter,
    SourceCapabilities,
    SourceListing,
    SourcePage,
)
from vacancyx.sources.registry import SourceRegistry

__all__ = [
    "JobSourceAdapter",
    "SourceCapabilities",
    "SourceConfig",
    "SourceListing",
    "SourcePage",
    "SourceRegistry",
]
