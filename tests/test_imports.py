import importlib
import unittest


class ImportTests(unittest.TestCase):
    def test_runtime_modules_import(self):
        modules = (
            "pattern_surface.core_engine",
            "pattern_surface.prototype_engine",
            "pattern_surface.common.contracts",
            "pattern_surface.mapping.parameters",
            "pattern_surface.mapping.service",
            "pattern_surface.patterns.registry",
            "pattern_surface.patterns.diamond.parameters",
            "pattern_surface.patterns.diamond.solids",
            "pattern_surface.patterns.diamond.prototype_command",
            "pattern_surface.patterns.diamond.v2_command",
            "pattern_surface.patterns.diamond.v2_engine",
            "pattern_surface.patterns.diamond.v2_parameters",
            "pattern_surface.patterns.boleado.metadata",
            "pattern_surface.patterns.boleado.parameters",
            "pattern_surface.patterns.boleado.engine",
            "pattern_surface.patterns.boleado.command",
            "pattern_surface.trimming.service",
        )
        for name in modules:
            with self.subTest(name=name):
                self.assertIsNotNone(importlib.import_module(name))


if __name__ == "__main__":
    unittest.main()
