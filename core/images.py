"""Collecte et validation des images d'entree.

Module volontairement sans dependance externe : il est testable sans GPU,
sans torch et sans LichtFeld Studio.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

#: Extensions proposees a l'utilisateur (minuscules, point inclus).
#:
#: Plus large que ce que les moteurs lisent nativement : les formats absents de
#: `BackendInfo.native_suffixes` sont convertis en PNG avant l'inference. Mieux
#: vaut convertir un TIFF -- courant en production photo -- que le rejeter.
SUPPORTED_SUFFIXES = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".heif"}
)


@dataclass(frozen=True)
class ImageSet:
    """Resultat d'un scan de dossier."""

    paths: tuple[Path, ...]
    ignored: tuple[Path, ...]

    @property
    def count(self) -> int:
        return len(self.paths)

    def __bool__(self) -> bool:
        return bool(self.paths)


def scan_folder(folder: str | Path, recursive: bool = False) -> ImageSet:
    """Liste les images d'un dossier, triees par nom.

    Le tri par nom est volontaire : il rend la generation reproductible d'un
    run a l'autre, ce que l'ordre de parcours du systeme de fichiers ne garantit pas.
    """
    root = Path(folder).expanduser()
    if not root.is_dir():
        return ImageSet(paths=(), ignored=())

    entries = sorted(root.rglob("*") if recursive else root.glob("*"))
    kept: list[Path] = []
    ignored: list[Path] = []
    for entry in entries:
        if not entry.is_file():
            continue
        if entry.suffix.lower() in SUPPORTED_SUFFIXES:
            kept.append(entry)
        else:
            ignored.append(entry)
    return ImageSet(paths=tuple(kept), ignored=tuple(ignored))


def validate(images: ImageSet, min_images: int, max_images: int) -> list[str]:
    """Retourne la liste des problemes bloquants. Liste vide = pret a lancer."""
    problems: list[str] = []
    if images.count < min_images:
        problems.append(
            f"{images.count} image(s) trouvee(s), ce moteur en exige au moins {min_images}."
        )
    if images.count > max_images:
        problems.append(
            f"{images.count} images trouvees, au-dela du maximum de {max_images} "
            "pour ce moteur. Reduisez la selection ou augmentez la limite."
        )
    empty = [p.name for p in images.paths if p.stat().st_size == 0]
    if empty:
        problems.append("Fichier(s) vide(s) : " + ", ".join(empty[:5]))
    return problems


def summarize(images: ImageSet, max_names: int = 6) -> str:
    """Resume court affiche dans le panneau."""
    if not images:
        return "Aucune image"
    names = [p.name for p in images.paths[:max_names]]
    suffix = "" if images.count <= max_names else f" (+{images.count - max_names})"
    return f"{images.count} image(s) : " + ", ".join(names) + suffix
