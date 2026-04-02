"""Artifact directory conventions for the chat analysis repository."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ArtifactLayout:
    root: Path
    contracts: Path
    discovery: Path
    normalization: Path
    substrate: Path
    reports: Path
    episodes: Path

    @classmethod
    def from_config(cls, artifact_root: str | Path) -> "ArtifactLayout":
        root = Path(artifact_root)
        return cls(
            root=root,
            contracts=root / "contracts",
            discovery=root / "discovery",
            normalization=root / "normalization",
            substrate=root / "substrate",
            reports=root / "reports",
            episodes=root / "episodes",
        )

    def ensure(self) -> None:
        for path in (
            self.root,
            self.contracts,
            self.discovery,
            self.normalization,
            self.substrate,
            self.reports,
            self.episodes,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def as_dict(self) -> dict[str, str]:
        return {
            "artifact_root": str(self.root),
            "contracts_dir": str(self.contracts),
            "discovery_dir": str(self.discovery),
            "normalization_dir": str(self.normalization),
            "substrate_dir": str(self.substrate),
            "reports_dir": str(self.reports),
            "episodes_dir": str(self.episodes),
        }
