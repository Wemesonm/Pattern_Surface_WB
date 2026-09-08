"""Architecture guards for MAP-REQ-026, PAT-REQ-001, and TRIM-REQ-001."""

import ast
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]


def imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                modules.add("." * node.level + (node.module or ""))
            elif node.module:
                modules.add(node.module)
    return modules


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_boleado_is_registered_and_does_not_import_diamond(self):
        from pattern_surface.patterns import registry

        item = registry.get("boleado")
        self.assertEqual("PatternSurface_Pattern_Boleado", item["command_id"])
        imports = imported_modules(ROOT / "pattern_surface/patterns/boleado/engine.py")
        self.assertEqual(set(), {module for module in imports
                                 if "diamond" in module.lower()})

    def test_map_faces_does_not_import_pattern_packages(self):
        """MAP-REQ-026: mapping stays independent of optional patterns."""
        violations = []
        for path in (ROOT / "pattern_surface/mapping").glob("*.py"):
            for module in imported_modules(path):
                if "patterns" in module.lower():
                    violations.append((path.name, module))
        self.assertEqual([], violations)

    def test_trim_surface_does_not_import_diamond(self):
        """TRIM-REQ-001: trimming is pattern-independent."""
        violations = []
        for path in (ROOT / "pattern_surface/trimming").glob("*.py"):
            for module in imported_modules(path):
                if "diamond" in module.lower() or "patterns" in module.lower():
                    violations.append((path.name, module))
        self.assertEqual([], violations)

    def test_patterns_do_not_import_mapping_implementation(self):
        """PAT-REQ-001: patterns consume contracts, not mapping internals."""
        violations = []
        for path in (ROOT / "pattern_surface/patterns").rglob("*.py"):
            for module in imported_modules(path):
                if "mapping" in module.lower():
                    violations.append((str(path.relative_to(ROOT)), module))
        self.assertEqual([], violations)

    def test_common_does_not_import_tool_packages(self):
        """DATA-REQ-001: shared helpers remain below tool ownership layers."""
        violations = []
        for path in (ROOT / "pattern_surface/common").glob("*.py"):
            for module in imported_modules(path):
                if any(name in module.lower() for name in ("mapping", "patterns", "trimming")):
                    violations.append((path.name, module))
        self.assertEqual([], violations)


if __name__ == "__main__":
    unittest.main()
