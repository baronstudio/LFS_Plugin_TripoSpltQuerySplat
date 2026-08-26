"""La version doit rester unique et coherente dans tout le depot."""

import re
import tomllib
import unittest
from pathlib import Path

from core import version

ROOT = Path(__file__).resolve().parents[1]


class TestVersion(unittest.TestCase):
    def test_semver_format(self):
        self.assertRegex(version.__version__, r"^\d+\.\d+\.\d+$")

    def test_matches_pyproject(self):
        """core/version.py et pyproject.toml ne doivent jamais diverger."""
        with (ROOT / "pyproject.toml").open("rb") as handle:
            data = tomllib.load(handle)
        self.assertEqual(data["project"]["version"], version.__version__)

    def test_version_tuple_is_comparable(self):
        self.assertGreaterEqual(version.version_tuple(), (0, 1, 0))

    def test_changelog_mentions_current_version(self):
        """Toute version publiee doit avoir son entree de changelog."""
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(f"[{version.__version__}]", changelog)

    def test_banner(self):
        self.assertTrue(re.match(r"^PhotoSplat v\d+\.\d+\.\d+$", version.banner()))


if __name__ == "__main__":
    unittest.main()
