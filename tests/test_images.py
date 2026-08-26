"""Scan et validation des photos d'entree."""

import tempfile
import unittest
from pathlib import Path

from core import images


class TestScanFolder(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        for name in ("b.jpg", "a.PNG", "c.txt", "d.webp"):
            (self.root / name).write_bytes(b"x")
        nested = self.root / "sub"
        nested.mkdir()
        (nested / "e.jpg").write_bytes(b"x")

    def tearDown(self):
        self._tmp.cleanup()

    def test_keeps_only_images(self):
        found = images.scan_folder(self.root)
        self.assertEqual([p.name for p in found.paths], ["a.PNG", "b.jpg", "d.webp"])
        self.assertEqual([p.name for p in found.ignored], ["c.txt"])

    def test_sorted_for_reproducibility(self):
        first = images.scan_folder(self.root).paths
        second = images.scan_folder(self.root).paths
        self.assertEqual(first, second)

    def test_recursive(self):
        flat = images.scan_folder(self.root, recursive=False)
        deep = images.scan_folder(self.root, recursive=True)
        self.assertEqual(flat.count, 3)
        self.assertEqual(deep.count, 4)

    def test_missing_folder_is_empty(self):
        self.assertFalse(images.scan_folder(self.root / "nope"))


class TestValidate(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _set(self, count, size=4):
        for index in range(count):
            (self.root / f"{index}.jpg").write_bytes(b"x" * size)
        return images.scan_folder(self.root)

    def test_too_few(self):
        self.assertTrue(images.validate(self._set(1), 2, 100))

    def test_too_many(self):
        self.assertTrue(images.validate(self._set(5), 2, 4))

    def test_ok(self):
        self.assertEqual(images.validate(self._set(3), 2, 100), [])

    def test_empty_file_detected(self):
        problems = images.validate(self._set(3, size=0), 2, 100)
        self.assertTrue(any("vide" in problem for problem in problems))

    def test_summarize_truncates(self):
        summary = images.summarize(self._set(9), max_names=2)
        self.assertIn("+7", summary)


if __name__ == "__main__":
    unittest.main()
