"""PhotoSplat -- plugin LichtFeld Studio.

Quelques photos d'un sujet, aucune etape d'alignement prealable, un splat a
l'arrivee. Point d'entree du plugin : LichtFeld appelle `on_load` au
chargement et `on_unload` a la decharge.
"""

from __future__ import annotations

import lichtfeld as lf

from .core import lfs
from .core.version import __version__, banner
from .panels.main_panel import MainPanel

#: Classes enregistrees aupres de l'hote, dans l'ordre d'enregistrement.
_CLASSES = [MainPanel]


def on_load() -> None:
    """Enregistre les panneaux. Appele par LichtFeld Studio."""
    for cls in _CLASSES:
        lf.register_class(cls)
    lfs.log(f"{banner()} charge")


def on_unload() -> None:
    """Retire les panneaux et rend la main proprement."""
    for cls in reversed(_CLASSES):
        try:
            lf.unregister_class(cls)
        except Exception as exc:  # noqa: BLE001 - la decharge ne doit jamais echouer
            lfs.log(f"PhotoSplat : decharge partielle ({exc})")
    lfs.log(f"PhotoSplat v{__version__} decharge")
