"""Adaptateur autour de l'API Python de LichtFeld Studio.

Toutes les fonctions restent appelables hors de l'application : elles
retournent alors `False` au lieu de lever. Cela permet de tester la logique du
plugin sans lancer LichtFeld, et evite qu'une API absente ne casse le panneau.
"""

from __future__ import annotations

from pathlib import Path

try:  # pragma: no cover - depend de l'hote
    import lichtfeld as lf
except ImportError:  # pragma: no cover
    lf = None


def available() -> bool:
    """Vrai si le plugin tourne bien dans LichtFeld Studio."""
    return lf is not None


def host_version() -> str:
    if lf is None:
        return "hors LichtFeld Studio"
    return getattr(lf, "PLUGIN_API_VERSION", "inconnue")


def load_splat(ply_path: Path) -> bool:
    """Charge un .ply de gaussiennes dans la scene courante."""
    if lf is None:
        return False
    lf.load_file(str(ply_path))
    return True


def load_dataset(dataset_dir: Path, init_ply: Path | None, output_dir: Path) -> bool:
    """Charge un dataset COLMAP en vue d'un entrainement.

    `init_path` fournit le nuage d'initialisation issu du moteur : c'est lui qui
    remplace le nuage epars que COLMAP produisait.
    """
    if lf is None:
        return False
    lf.load_file(
        str(dataset_dir),
        is_dataset=True,
        output_path=str(output_dir),
        init_path=str(init_ply) if init_ply else "",
    )
    return True


def start_training() -> bool:
    """Lance l'entrainement natif sur le dataset charge."""
    if lf is None:
        return False
    lf.start_training()
    return True


def is_training_active() -> bool:
    if lf is None:
        return False
    return bool(lf.is_training_active())


def log(message: str) -> None:
    """Journalise cote hote quand c'est possible, sinon sur la sortie standard."""
    if lf is not None and hasattr(lf, "log"):
        try:
            lf.log.info(message)
            return
        except Exception:  # pragma: no cover - journalisation best effort
            pass
    print(message)
