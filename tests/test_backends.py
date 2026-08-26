"""Contrat des moteurs et registre."""

import unittest
from pathlib import Path

from core.backends import base, registry


class TestRegistry(unittest.TestCase):
    def test_default_is_registered(self):
        self.assertIn(registry.default_name(), registry.names())

    def test_labels_align_with_names(self):
        self.assertEqual(len(registry.labels()), len(registry.names()))

    def test_unknown_backend_raises_explicitly(self):
        with self.assertRaises(KeyError) as ctx:
            registry.get("inexistant")
        self.assertIn("inexistant", str(ctx.exception))

    def test_every_backend_honours_the_contract(self):
        for name in registry.names():
            backend = registry.get(name)
            with self.subTest(backend=name):
                self.assertIsInstance(backend.info, base.BackendInfo)
                self.assertIn(backend.info.kind, (base.KIND_DATASET, base.KIND_SPLAT))
                self.assertGreaterEqual(backend.info.min_images, 1)
                self.assertGreaterEqual(backend.info.max_images, backend.info.min_images)
                self.assertTrue(callable(backend.check))
                self.assertTrue(callable(backend.run))

    def test_shipped_backends_are_commercially_usable(self):
        """Garde-fou : aucun moteur non commercial ne doit entrer sans decision explicite."""
        for name in registry.names():
            with self.subTest(backend=name):
                self.assertTrue(registry.get(name).info.commercial_ok)

    def test_check_returns_a_list(self):
        for name in registry.names():
            self.assertIsInstance(registry.get(name).check(), list)


class TestHelpers(unittest.TestCase):
    def test_unique_names_resolves_collisions(self):
        names = base.unique_names([Path("a/x.jpg"), Path("b/x.jpg"), Path("c/y.png")])
        self.assertEqual(len(set(names)), 3)
        self.assertEqual(names[0], "x.jpg")

    def test_unique_names_is_stable(self):
        paths = [Path("a/x.jpg"), Path("b/x.jpg")]
        self.assertEqual(base.unique_names(paths), base.unique_names(paths))

    def test_raise_if_cancelled(self):
        import threading

        event = threading.Event()
        base.raise_if_cancelled(event)  # ne leve pas
        event.set()
        with self.assertRaises(base.Cancelled):
            base.raise_if_cancelled(event)

    def test_license_line_flags_non_commercial(self):
        info = base.BackendInfo(
            name="x",
            label="X",
            kind=base.KIND_SPLAT,
            min_images=1,
            max_images=1,
            model_id="m",
            license="CC-BY-NC",
            commercial_ok=False,
            summary="",
        )
        self.assertIn("NON COMMERCIAL", info.license_line())


if __name__ == "__main__":
    unittest.main()
