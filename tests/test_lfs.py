"""Adaptateur vers l'API de l'hote.

L'API de LichtFeld Studio varie d'une version a l'autre : `is_training_active`
existe sur `master` mais pas en 0.5.3. L'adaptateur doit absorber ces ecarts,
jamais les propager dans le rendu du panneau.
"""

import unittest
from types import SimpleNamespace
from unittest import mock

from core import lfs


class _Host(SimpleNamespace):
    """Faux module `lichtfeld`, dote uniquement des attributs demandes."""


class TestIsTrainingActive(unittest.TestCase):
    def test_api_recente(self):
        host = _Host(is_training_active=lambda: True)
        with mock.patch.object(lfs, "lf", host):
            self.assertTrue(lfs.is_training_active())

    def test_repli_sur_trainer_state(self):
        """0.5.3 : `is_training_active` n'existe pas, `trainer_state` oui."""
        for state, expected in [
            ("running", True),
            ("Paused", True),
            ("idle", False),
            ("completed", False),
            ("", False),
        ]:
            host = _Host(trainer_state=lambda s=state: s)
            with mock.patch.object(lfs, "lf", host), self.subTest(state=state):
                self.assertIs(lfs.is_training_active(), expected)

    def test_aucune_des_deux_fonctions(self):
        with mock.patch.object(lfs, "lf", _Host()):
            self.assertFalse(lfs.is_training_active())

    def test_hors_lichtfeld(self):
        with mock.patch.object(lfs, "lf", None):
            self.assertFalse(lfs.is_training_active())

    def test_une_exception_de_l_hote_ne_remonte_pas(self):
        def boom():
            raise RuntimeError("panne native")

        with mock.patch.object(lfs, "lf", _Host(is_training_active=boom)):
            self.assertFalse(lfs.is_training_active())


class TestActionsSansHote(unittest.TestCase):
    """Sans hote, chaque action repond False au lieu de lever."""

    def setUp(self):
        patcher = mock.patch.object(lfs, "lf", None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_load_splat(self):
        self.assertFalse(lfs.load_splat(mock.MagicMock()))

    def test_load_dataset(self):
        self.assertFalse(lfs.load_dataset(mock.MagicMock(), None, mock.MagicMock()))

    def test_start_training(self):
        self.assertFalse(lfs.start_training())

    def test_available(self):
        self.assertFalse(lfs.available())


class TestActionsSurHoteIncomplet(unittest.TestCase):
    """Un hote depourvu de `load_file` ne doit pas faire lever le panneau."""

    def test_load_dataset_sans_load_file(self):
        with mock.patch.object(lfs, "lf", _Host()):
            self.assertFalse(lfs.load_dataset(mock.MagicMock(), None, mock.MagicMock()))

    def test_start_training_sans_fonction(self):
        with mock.patch.object(lfs, "lf", _Host()):
            self.assertFalse(lfs.start_training())

    def test_load_dataset_transmet_init_path(self):
        appels = []
        host = _Host(load_file=lambda path, **kwargs: appels.append((path, kwargs)))
        with mock.patch.object(lfs, "lf", host):
            self.assertTrue(lfs.load_dataset(mock.MagicMock(), mock.MagicMock(), mock.MagicMock()))
        self.assertTrue(appels[0][1]["is_dataset"])
        self.assertIn("init_path", appels[0][1])


if __name__ == "__main__":
    unittest.main()
