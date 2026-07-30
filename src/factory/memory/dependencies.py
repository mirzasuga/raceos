"""
Dependency Graph Lookup.

Provides dependency analysis across the codebase:
    - What does file X import?
    - What imports file X?
    - Is there a circular dependency?
    - Does this change violate layered architecture?

Special support for RaceOS layered architecture validation:
    app/ → middleware/ → drivers/ → core/ (one-way only)

Usage:
    deps = DependencyLookup(client, config)
    imports = deps.get_imports("firmware/middleware/ecu_parser.cpp")
    dependents = deps.get_dependents("firmware/core/board_config.h")
    violations = deps.check_layer_violations("firmware/drivers/tft_espi_panel.h")
    cycles = deps.detect_cycles()
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .client import MemoryClient, MemoryClientError, ServerUnavailableError
from .types import Dependency, DependencyDirection, DependencyNode, Language


@dataclass
class LayerConfig:
    """RaceOS layered architecture configuration."""

    layers: list[str] = field(default_factory=lambda: [
        "firmware/app/",
        "firmware/middleware/",
        "firmware/drivers/",
        "firmware/core/",
    ])

    def get_layer_index(self, file_path: str) -> int:
        """
        Get the layer index for a file (0 = top, 3 = bottom).
        Returns -1 if file is not in any layer.
        """
        for i, layer in enumerate(self.layers):
            if file_path.startswith(layer):
                return i
        return -1

    def is_valid_dependency(self, source: str, target: str) -> bool:
        """
        Check if a dependency direction is valid.

        Valid: higher layer → lower layer (source_idx < target_idx)
        Invalid: lower layer → higher layer (source_idx > target_idx)
        Neutral: same layer or outside layer system
        """
        source_idx = self.get_layer_index(source)
        target_idx = self.get_layer_index(target)

        # If either file is outside layer system, it's neutral
        if source_idx == -1 or target_idx == -1:
            return True

        # Same layer is OK
        if source_idx == target_idx:
            return True

        # Higher → lower is valid (app imports middleware, etc.)
        return source_idx <= target_idx


@dataclass
class LayerViolation:
    """A detected layered architecture violation."""

    source: str                  # File importing (in wrong direction)
    target: str                  # File being imported
    source_layer: str            # e.g., "drivers/"
    target_layer: str            # e.g., "app/"
    import_statement: str        # The offending #include
    severity: str = "error"      # error | warning


class DependencyLookup:
    """
    Dependency graph queries and layer validation.

    Uses the indexed dependency data to answer questions about
    code relationships and architectural compliance.
    """

    def __init__(
        self,
        client: MemoryClient,
        layer_config: LayerConfig | None = None,
    ):
        self.client = client
        self.layer_config = layer_config or LayerConfig()

    def get_imports(self, file_path: str) -> list[Dependency]:
        """
        Get all files that a given file imports/includes.

        Args:
            file_path: Source file to analyze.

        Returns:
            List of dependencies (what this file imports).
        """
        try:
            raw = self.client.call_tool("get_imports", {"file_path": file_path})
        except (ServerUnavailableError, MemoryClientError):
            return []

        return self._parse_dependencies(raw, DependencyDirection.IMPORTS)

    def get_dependents(self, file_path: str) -> list[Dependency]:
        """
        Get all files that import/include a given file.

        Args:
            file_path: Target file to find dependents of.

        Returns:
            List of files that depend on this file.
        """
        try:
            raw = self.client.call_tool("get_dependents", {"file_path": file_path})
        except (ServerUnavailableError, MemoryClientError):
            return []

        return self._parse_dependencies(raw, DependencyDirection.IMPORTED_BY)

    def get_dependency_tree(self, file_path: str, depth: int = 3) -> DependencyNode:
        """
        Get the full dependency tree rooted at a file.

        Args:
            file_path: Root file.
            depth: Maximum recursion depth.

        Returns:
            DependencyNode with imports and imported_by lists.
        """
        try:
            raw = self.client.call_tool("dependency_tree", {
                "file_path": file_path,
                "depth": depth,
            })
        except (ServerUnavailableError, MemoryClientError):
            return DependencyNode(file_path=file_path)

        return DependencyNode(
            file_path=file_path,
            imports=raw.get("imports", []),
            imported_by=raw.get("imported_by", []),
            layer=self._get_layer_name(file_path),
        )

    def check_layer_violations(self, file_path: str | None = None) -> list[LayerViolation]:
        """
        Check for layered architecture violations.

        If file_path is given, only checks that file's dependencies.
        If None, checks the entire indexed codebase.

        RaceOS rule: app/ → middleware/ → drivers/ → core/ (one-way).
        Any dependency in the reverse direction is a violation.

        Args:
            file_path: Optional file to check (None = check all).

        Returns:
            List of detected violations.
        """
        violations: list[LayerViolation] = []

        if file_path:
            # Check single file
            imports = self.get_imports(file_path)
            for dep in imports:
                if not self.layer_config.is_valid_dependency(dep.source, dep.target):
                    violations.append(self._make_violation(dep))
        else:
            # Check all indexed dependencies
            try:
                raw = self.client.call_tool("all_dependencies", {})
                for item in raw.get("dependencies", []):
                    source = item.get("source", "")
                    target = item.get("target", "")
                    if not self.layer_config.is_valid_dependency(source, target):
                        violations.append(LayerViolation(
                            source=source,
                            target=target,
                            source_layer=self._get_layer_name(source),
                            target_layer=self._get_layer_name(target),
                            import_statement=item.get("import_statement", ""),
                        ))
            except (ServerUnavailableError, MemoryClientError):
                pass

        return violations

    def detect_cycles(self) -> list[list[str]]:
        """
        Detect circular dependencies in the codebase.

        Returns:
            List of cycles, where each cycle is a list of file paths
            forming the circular dependency chain.
        """
        try:
            raw = self.client.call_tool("detect_cycles", {})
        except (ServerUnavailableError, MemoryClientError):
            return []

        return raw.get("cycles", [])

    def get_impact_analysis(self, file_path: str) -> dict:
        """
        Analyze the impact of changing a file.

        Returns:
            Dict with:
                - direct_dependents: Files directly importing this file
                - transitive_dependents: All files affected (recursive)
                - layer: Which architecture layer
                - risk: "low" | "medium" | "high" based on dependent count
        """
        dependents = self.get_dependents(file_path)
        direct = [d.source for d in dependents]

        # Estimate transitive impact
        transitive: set[str] = set(direct)
        for dep_file in direct[:10]:  # Limit recursion
            second_level = self.get_dependents(dep_file)
            transitive.update(d.source for d in second_level)

        risk = "low"
        if len(transitive) > 10:
            risk = "high"
        elif len(transitive) > 3:
            risk = "medium"

        return {
            "file": file_path,
            "layer": self._get_layer_name(file_path),
            "direct_dependents": direct,
            "transitive_dependents": list(transitive),
            "total_impact": len(transitive),
            "risk": risk,
        }

    # --- Internal ---

    def _parse_dependencies(self, raw: dict, direction: DependencyDirection) -> list[Dependency]:
        """Parse raw server response into Dependency list."""
        deps: list[Dependency] = []
        for item in raw.get("dependencies", []):
            deps.append(Dependency(
                source=item.get("source", ""),
                target=item.get("target", ""),
                direction=direction,
                import_statement=item.get("import_statement", ""),
            ))
        return deps

    def _make_violation(self, dep: Dependency) -> LayerViolation:
        """Convert a bad dependency into a LayerViolation."""
        return LayerViolation(
            source=dep.source,
            target=dep.target,
            source_layer=self._get_layer_name(dep.source),
            target_layer=self._get_layer_name(dep.target),
            import_statement=dep.import_statement,
        )

    def _get_layer_name(self, file_path: str) -> str:
        """Get human-readable layer name for a file."""
        idx = self.layer_config.get_layer_index(file_path)
        if idx == -1:
            return "external"
        return self.layer_config.layers[idx].rstrip("/").split("/")[-1]
