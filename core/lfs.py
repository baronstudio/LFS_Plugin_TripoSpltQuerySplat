"""Adaptateur autour de l'API Python de LichtFeld Studio.

L'API de l'hote varie d'une version a l'autre : `is_training_active()` existe
sur `master` mais pas en 0.5.3, ou l'equivalent est `trainer_state()`. Un
plugin qui appelle directement une fonction absente leve une `AttributeError`
en plein `draw()`, et le panneau entier cesse de s'afficher.

Ce module est donc la seule frontiere avec l'hote, et **aucune de ses fonctions
ne leve**. Les appels absents retournent une valeur neutre, ce qui rend aussi
le reste du plugin testable hors de LichtFeld Studio.
"""

from __future__ import annotations

from pathlib import Path

try:  # pragma: no cover - depend de l'hote
    import lichtfeld as lf
except ImportError:  # pragma: no cover
    lf = None

#: Etats de `trainer_state()` consideres comme "un entrainement occupe le GPU".
_BUSY_STATES = frozenset({"running", "paused", "starting", "training"})


def _call(name: str, *args, default=None, **kwargs):
    """Appelle `lf.<name>` si elle existe, sinon retourne `default`.

    Toute exception est absorbee : un ecart d'API de l'hote ne doit jamais
    casser le rendu du panneau.
    """
    if lf is None:
        return default
    func = getattr(lf, name, None)
    if func is None:
        return default
    try:
        return func(*args, **kwargs)
    except Exception:  # noqa: BLE001 - frontiere avec du code natif
        return default


def available() -> bool:
    """Vrai si le plugin tourne bien dans LichtFeld Studio."""
    return lf is not None


def host_version() -> str:
    if lf is None:
        return "hors LichtFeld Studio"
    return getattr(lf, "PLUGIN_API_VERSION", "inconnue")


def load_splat(ply_path: Path) -> bool:
    """Charge un .ply de gaussiennes dans la scene courante."""
    if lf is None or not hasattr(lf, "load_file"):
        return False
    lf.load_file(str(ply_path))
    return True


def load_dataset(dataset_dir: Path, init_ply: Path | None, output_dir: Path) -> bool:
    """Charge un dataset COLMAP en vue d'un entrainement.

    `init_path` fournit le nuage d'initialisation issu du moteur : c'est lui qui
    remplace le nuage epars que COLMAP produisait.
    """
    if lf is None or not hasattr(lf, "load_file"):
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
    if lf is None or not hasattr(lf, "start_training"):
        return False
    lf.start_training()
    return True


def is_training_active() -> bool:
    """Un entrainement occupe-t-il le GPU ?

    Trois voies selon la version de l'hote, de la plus recente a la plus sure.
    En cas de doute, on repond « non » : au pire l'utilisateur rencontrera une
    erreur de memoire explicite au lancement, plutot qu'un bouton bloque sans
    raison visible.
    """
    direct = _call("is_training_active", default=None)
    if direct is not None:
        return bool(direct)
    state = _call("trainer_state", default=None)
    if state is not None:
        return str(state).strip().lower() in _BUSY_STATES
    return False


def log(message: str) -> None:
    """Journalise vers l'onglet Logging de l'hote, sinon sur la sortie standard."""
    logger = getattr(lf, "log", None) if lf is not None else None
    for level in ("info", "warn", "warning"):
        func = getattr(logger, level, None) if logger is not None else None
        if func is not None:
            try:
                func(message)
                return
            except Exception:  # noqa: BLE001 - journalisation best effort
                break
    print(message)
