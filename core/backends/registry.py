"""Catalogue des moteurs disponibles.

Un seul point d'enregistrement : pour ajouter un moteur, importez-le et
ajoutez-le a `_BACKENDS`.
"""

from __future__ import annotations

from .base import Backend
from .mapanything_backend import MapAnythingBackend

_BACKENDS: dict[str, Backend] = {}


def _register(backend: Backend) -> None:
    _BACKENDS[backend.info.name] = backend


_register(MapAnythingBackend())


def names() -> list[str]:
    """Identifiants techniques, dans l'ordre d'enregistrement."""
    return list(_BACKENDS)


def labels() -> list[str]:
    """Libelles affichables, dans le meme ordre que `names()`."""
    return [backend.info.label for backend in _BACKENDS.values()]


def get(name: str) -> Backend:
    """Retourne un moteur par son identifiant."""
    try:
        return _BACKENDS[name]
    except KeyError:
        raise KeyError(f"Moteur inconnu : {name!r}. Disponibles : {names()}") from None


def default_name() -> str:
    """Moteur selectionne au premier lancement."""
    return names()[0]
