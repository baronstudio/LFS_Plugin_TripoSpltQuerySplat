"""Preparation des images avant inference.

MapAnything ne lit que JPG, PNG et HEIC/HEIF. Les TIFF, courants en production
photo, doivent etre convertis plutot que rejetes.
"""

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from core.backends.mapanything_backend import _prepare_inputs


def _make_image(path: Path, mode: str = "RGB") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new(mode, (8, 6), color=128).save(path)
    return path


class TestPrepareInputs(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.staging = self.root / "input"
        self.addCleanup(self._tmp.cleanup)

    def test_formats_natifs_ne_sont_pas_recopies(self):
        images = [_make_image(self.root / "a.jpg"), _make_image(self.root / "b.png")]
        sources, names, converted = _prepare_inputs(images, self.staging)
        self.assertEqual(sources, images)
        self.assertEqual(names, ["a.jpg", "b.png"])
        self.assertEqual(converted, 0)
        self.assertFalse(self.staging.exists(), "aucun dossier de travail inutile")

    def test_tiff_converti_en_png(self):
        images = [_make_image(self.root / "photo.tif")]
        sources, names, converted = _prepare_inputs(images, self.staging)
        self.assertEqual(converted, 1)
        self.assertEqual(names, ["photo.png"])
        self.assertEqual(sources[0], self.staging / "photo.png")
        self.assertTrue(sources[0].is_file())
        with Image.open(sources[0]) as handle:
            self.assertEqual(handle.format, "PNG")

    def test_melange_de_formats(self):
        images = [
            _make_image(self.root / "a.tif"),
            _make_image(self.root / "b.jpg"),
            _make_image(self.root / "c.tiff"),
        ]
        sources, names, converted = _prepare_inputs(images, self.staging)
        self.assertEqual(converted, 2)
        self.assertEqual(names, ["a.png", "b.jpg", "c.png"])
        self.assertTrue(all(path.is_file() for path in sources))

    def test_collision_creee_par_la_conversion(self):
        """`a.tif` et `a.png` produiraient tous deux `a.png`."""
        images = [_make_image(self.root / "a.tif"), _make_image(self.root / "a.png")]
        _, names, _ = _prepare_inputs(images, self.staging)
        self.assertEqual(len(set(names)), 2, f"noms en collision : {names}")

    def test_tiff_niveaux_de_gris_converti_en_rvb(self):
        """Un TIFF 8 bits monochrome ne doit pas faire echouer l'ecriture PNG."""
        images = [_make_image(self.root / "gris.tif", mode="L")]
        sources, _, _ = _prepare_inputs(images, self.staging)
        with Image.open(sources[0]) as handle:
            self.assertEqual(handle.mode, "RGB")

    def test_extension_en_majuscules(self):
        images = [_make_image(self.root / "PHOTO.TIF")]
        sources, names, converted = _prepare_inputs(images, self.staging)
        self.assertEqual(converted, 1)
        self.assertEqual(names, ["PHOTO.png"])
        self.assertTrue(sources[0].is_file())

    def test_jpeg_majuscule_reste_natif(self):
        images = [_make_image(self.root / "A.JPG")]
        sources, names, converted = _prepare_inputs(images, self.staging)
        self.assertEqual(converted, 0)
        self.assertEqual(names, ["A.JPG"])
        self.assertEqual(sources, images)


if __name__ == "__main__":
    unittest.main()
