"""Persistance des reglages."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import settings as settings_mod


class TestSettings(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        patcher = mock.patch.object(Path, "home", return_value=Path(self._tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def test_roundtrip(self):
        original = settings_mod.Settings(images_dir="/photos", seed=7, auto_train=True)
        original.save()
        self.assertEqual(settings_mod.Settings.load(), original)

    def test_missing_file_returns_defaults(self):
        self.assertEqual(settings_mod.Settings.load(), settings_mod.Settings())

    def test_corrupted_file_returns_defaults(self):
        path = settings_mod.settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{ pas du json", encoding="utf-8")
        self.assertEqual(settings_mod.Settings.load(), settings_mod.Settings())

    def test_unknown_keys_are_ignored(self):
        """Un reglage retire dans une version ulterieure ne doit pas casser le chargement."""
        path = settings_mod.settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"seed": 3, "reglage_disparu": True}), encoding="utf-8")
        self.assertEqual(settings_mod.Settings.load().seed, 3)

    def test_data_dir_is_outside_the_plugin_folder(self):
        plugin_root = Path(__file__).resolve().parents[1]
        self.assertNotIn(plugin_root, settings_mod.data_dir().parents)


if __name__ == "__main__":
    unittest.main()
