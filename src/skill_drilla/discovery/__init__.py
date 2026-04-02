"""Discovery layer for project and session inventory."""

from skill_drilla.discovery.inventory import (
    DiscoverySummary,
    InventoryRecord,
    ProjectRecord,
    discover_corpus,
)
from skill_drilla.discovery.lineage import derive_lineage
from skill_drilla.discovery.scoping import ScopedInventory, apply_scope
from skill_drilla.discovery.writer import write_discovery_artifacts

__all__ = [
    "DiscoverySummary",
    "InventoryRecord",
    "ProjectRecord",
    "ScopedInventory",
    "apply_scope",
    "derive_lineage",
    "discover_corpus",
    "write_discovery_artifacts",
]
