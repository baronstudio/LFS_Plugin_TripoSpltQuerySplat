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

import importlib
import importlib.util
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


def missing_modules(names: tuple[str, ...]) -> list[str]:
    """Modules absents de l'environnement, **sans les importer**.

    `find_spec` interroge les chemins d'import sans executer le module.
    C'est vital : `import torch` puis `import mapanything` coutent des dizaines
    de secondes sur Windows (chargement de DLL, sans CPU visible). Un `check()`
    est appele depuis le constructeur du panneau, donc sur le fil de
    l'interface : il doit rester instantane.

    La disponibilite reelle de CUDA n'est donc PAS verifiee ici -- elle exige
    d'importer torch. Elle l'est au lancement de la generation, dans `run()`.
    """
    missing: list[str] = []
    for name in names:
        try:
            if importlib.util.find_spec(name) is None:
                missing.append(name)
        except (ImportError, ValueError):
            # Paquet dont le parent est absent ou casse : traite comme manquant.
            missing.append(name)
    return missing


def require_modules(names: tuple[str, ...]) -> None:
    """Importe reellement chaque module, ou leve un message exploitable.

    `missing_modules()` ne constate que la presence d'un fichier : un module
    peut etre installe et malgre tout refuser de s'importer -- DLL introuvable,
    extension native compilee contre une autre version de NumPy, runtime C++
    absent. Ces pannes-la n'apparaissent qu'a l'import.

    A appeler au tout debut de `run()`, dans le thread de travail : l'echec
    tombe en quelques secondes, avant le telechargement des poids et
    l'inference, au lieu d'apres.
    """
    for name in names:
        try:
            importlib.import_module(name)
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                f"Le module « {name} » est absent de l'environnement du plugin.\n"
                "Reinstallez le plugin, ou voir docs/03-installation.md."
            ) from exc
        except Exception as exc:  # noqa: BLE001 - DLL, ABI native, runtime C++...
            raise RuntimeError(
                f"Le module « {name} » est installe mais refuse de s'importer.\n"
                f"{type(exc).__name__}: {exc}\n"
                "Diagnostic et correctifs : docs/05-depannage.md."
            ) from exc


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
