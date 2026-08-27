"""Contrat des moteurs et registre."""

import builtins
import unittest
from pathlib import Path
from unittest import mock

from core.backends import base, registry

#: Modules dont l'import coute des dizaines de secondes sur Windows.
HEAVY = {"torch", "torchvision", "mapanything", "pycolmap", "open3d", "uniception"}


def _no_heavy_import():
    """Contexte qui echoue si un module lourd est importe."""
    real_import = builtins.__import__

    def guard(name, *args, **kwargs):
        root = name.split(".")[0]
        if root in HEAVY:
            raise AssertionError(
                f"import de {root} sur le fil de l'interface : l'application figerait."
            )
        return real_import(name, *args, **kwargs)

    return mock.patch.object(builtins, "__import__", guard)


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

    def test_check_never_imports_heavy_modules(self):
        """Regression : `check()` est appele depuis le constructeur du panneau.

        Importer torch ou mapanything a cet endroit fige LichtFeld Studio
        pendant des dizaines de secondes, sans activite CPU visible.
        """
        with _no_heavy_import():
            for name in registry.names():
                with self.subTest(backend=name):
                    registry.get(name).check()

    def test_missing_modules_detects_absence_without_importing(self):
        self.assertEqual(base.missing_modules(("json", "pathlib")), [])
        self.assertEqual(
            base.missing_modules(("module_qui_nexiste_pas_du_tout",)),
            ["module_qui_nexiste_pas_du_tout"],
        )


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


class TestRequireModules(unittest.TestCase):
    """`require_modules` rattrape ce que `find_spec` laisse passer."""

    def test_modules_sains(self):
        base.require_modules(("json", "pathlib"))

    def test_module_absent(self):
        with self.assertRaises(RuntimeError) as ctx:
            base.require_modules(("module_absent_xyz",))
        self.assertIn("absent", str(ctx.exception))

    def test_module_present_mais_casse(self):
        """Cas reel : extension native installee dont l'import echoue."""
        import importlib

        def boom(name):
            raise ImportError("DLL load failed while importing " + name)

        with mock.patch.object(importlib, "import_module", boom):
            with self.assertRaises(RuntimeError) as ctx:
                base.require_modules(("pycolmap",))
        message = str(ctx.exception)
        self.assertIn("refuse de s'importer", message)
        self.assertIn("DLL load failed", message)
