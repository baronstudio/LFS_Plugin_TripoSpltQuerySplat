"""Derivation des garde-fous a partir de la VRAM."""

import unittest

from core import gpu


class TestGpu(unittest.TestCase):
    def test_budget_is_monotonic(self):
        budgets = [gpu.max_views_for(v) for v in (4, 8, 12, 16, 24, 48)]
        self.assertEqual(budgets, sorted(budgets))

    def test_unknown_vram_is_conservative(self):
        """VRAM inconnue : on doit etre au moins aussi prudent que le plus petit palier connu."""
        known = min(gpu.max_views_for(v) for v in (8, 12, 16, 24))
        self.assertLessEqual(gpu.max_views_for(0), known)
        self.assertGreater(gpu.max_views_for(0), 0)

    def test_detect_never_raises(self):
        info = gpu.detect()
        self.assertIsInstance(info.describe(), str)

    def test_describe_mentions_missing_gpu(self):
        info = gpu.GpuInfo(available=False, name="x", vram_gb=0.0)
        self.assertIn("Aucun GPU", info.describe())


if __name__ == "__main__":
    unittest.main()
