"""Reglages persistants du plugin.

Stockes hors du dossier d'installation : une mise a jour du plugin (ou un
`git pull`) ne doit pas effacer les preferences de l'utilisateur.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .version import PLUGIN_ID


def data_dir() -> Path:
    """Dossier de travail du plugin (reglages, runs, sorties)."""
    return Path.home() / ".lichtfeld" / PLUGIN_ID


def settings_path() -> Path:
    return data_dir() / "settings.json"


def runs_dir() -> Path:
    return data_dir() / "runs"


@dataclass
class Settings:
    """Preferences utilisateur. Tout champ ajoute ici est persiste tel quel."""

    #: Dossier contenant les photos d'entree.
    images_dir: str = ""
    #: Inclure les sous-dossiers lors du scan.
    recursive: bool = False
    #: Moteur selectionne (identifiant technique).
    backend: str = "mapanything"
    #: Graine, pour rendre une generation reproductible.
    seed: int = 42
    #: Finesse du nuage d'initialisation (fraction de l'etendue de la scene).
    voxel_fraction: float = 0.01
    #: Plafond de vues envoyees au moteur ; 0 = deduit de la VRAM detectee.
    max_views: int = 0
    #: Enchainer automatiquement sur l'entrainement natif apres generation.
    auto_train: bool = False

    def save(self) -> None:
        path = settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls) -> Settings:
        """Charge les reglages ; toute valeur illisible retombe sur le defaut."""
        path = settings_path()
        if not path.is_file():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        if not isinstance(raw, dict):
            return cls()
        known = {f.name: f.type for f in fields(cls)}
        clean = {key: value for key, value in raw.items() if key in known}
        try:
            return cls(**clean)
        except TypeError:
            return cls()
