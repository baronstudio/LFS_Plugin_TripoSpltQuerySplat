"""Contrat commun a tous les moteurs de generation.

Un moteur = une facon de transformer des photos en donnees exploitables par
LichtFeld Studio. Deux familles coexistent :

* `DATASET` : le moteur produit un dataset COLMAP (poses + nuage d'init).
  LichtFeld entraine ensuite un vrai 3DGS a partir des photos reelles.
* `SPLAT`   : le moteur produit directement un fichier .ply de gaussiennes,
  charge tel quel dans la scene.

Ajouter un moteur = ajouter un module dans `core/backends/` et l'enregistrer
dans `registry.py`. Rien d'autre a modifier.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

#: Signature du rappel de progression : (avancement 0.0-1.0, message court).
ProgressFn = Callable[[float, str], None]

#: Le moteur produit un dataset COLMAP a entrainer.
KIND_DATASET = "dataset"
#: Le moteur produit directement un nuage de gaussiennes.
KIND_SPLAT = "splat"


@dataclass(frozen=True)
class BackendInfo:
    """Carte d'identite d'un moteur, affichee dans le panneau."""

    name: str
    label: str
    kind: str
    min_images: int
    max_images: int
    model_id: str
    license: str
    commercial_ok: bool
    summary: str

    def license_line(self) -> str:
        mark = "usage commercial autorise" if self.commercial_ok else "USAGE NON COMMERCIAL"
        return f"{self.license} -- {mark}"


@dataclass
class RunResult:
    """Ce qu'un moteur rend a la fin d'une generation."""

    #: Dossier dataset COLMAP (`images/` + `sparse/0/`), pour les moteurs DATASET.
    dataset_dir: Path | None = None
    #: Nuage d'initialisation issu du moteur (points.ply), pour les moteurs DATASET.
    init_ply: Path | None = None
    #: Gaussiennes pretes a charger, pour les moteurs SPLAT.
    splat_ply: Path | None = None
    #: Messages destines au journal du panneau.
    log: list[str] = field(default_factory=list)

    def add(self, message: str) -> None:
        self.log.append(message)


class Cancelled(RuntimeError):
    """Levee quand l'utilisateur interrompt la generation."""


class Backend(Protocol):
    """Interface que chaque moteur doit respecter."""

    info: BackendInfo

    def check(self) -> list[str]:
        """Liste les problemes bloquants (dependance absente, pas de GPU...).

        Liste vide = le moteur est pret a tourner.
        """

    def run(
        self,
        images: list[Path],
        work_dir: Path,
        params: dict,
        report: ProgressFn,
        cancel: threading.Event,
    ) -> RunResult:
        """Execute la generation. Leve `Cancelled` si `cancel` est arme."""


def raise_if_cancelled(cancel: threading.Event) -> None:
    """Point de controle d'annulation, appele entre deux etapes longues."""
    if cancel.is_set():
        raise Cancelled("Generation interrompue par l'utilisateur.")


def unique_names(paths: list[Path]) -> list[str]:
    """Noms de fichiers uniques et stables pour COLMAP.

    Deux photos peuvent porter le meme nom dans deux sous-dossiers ; COLMAP
    indexe les vues par nom, une collision corromprait la reconstruction.
    """
    seen: set[str] = set()
    names: list[str] = []
    for index, path in enumerate(paths):
        name = path.name
        if name in seen:
            name = f"{index:04d}_{path.name}"
        seen.add(name)
        names.append(name)
    return names
