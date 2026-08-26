"""Source unique de verite pour le numero de version du plugin.

Convention : SemVer -- MAJEUR.MINEUR.CORRECTIF
  MAJEUR   : rupture (API du plugin, format de projet, moteur retire)
  MINEUR   : fonctionnalite ajoutee sans rupture (nouveau moteur, nouveau reglage)
  CORRECTIF: correction de bug, documentation, packaging

`pyproject.toml` doit porter exactement la meme valeur : le test
`tests/test_version.py` echoue si les deux divergent, et `scripts/bump_version.py`
met les deux a jour en une commande.
"""

__version__ = "0.1.2"

#: Nom court affiche dans l'interface et les logs.
PLUGIN_NAME = "PhotoSplat"

#: Identifiant technique (prefixe des ids de panneaux, dossier d'installation).
PLUGIN_ID = "photosplat"


def version_tuple() -> tuple[int, int, int]:
    """Retourne la version sous forme de tuple comparable."""
    major, minor, patch = (int(part) for part in __version__.split("."))
    return major, minor, patch


def banner() -> str:
    """Ligne d'identification utilisee dans les logs et le pied du panneau."""
    return f"{PLUGIN_NAME} v{__version__}"
