# Versionnage et publication

| | |
|---|---|
| **Version doc** | 1.0.0 |
| **Public** | Mainteneur du dépôt |

---

## Convention

**SemVer** — `MAJEUR.MINEUR.CORRECTIF` :

| Incrément | Quand | Exemples |
|---|---|---|
| **MAJEUR** | rupture | un moteur est retiré, le format des sorties change, l'API plugin de l'hôte passe à 2 |
| **MINEUR** | ajout compatible | nouveau moteur, nouveau réglage, nouvelle sortie |
| **CORRECTIF** | correction | bug, documentation, packaging, épinglage de dépendance |

Tant que la version majeure vaut `0`, l'interface publique peut évoluer sur un
incrément mineur. C'est le cas aujourd'hui.

---

## Où vit la version

| Emplacement | Rôle |
|---|---|
| `core/version.py` → `__version__` | **source unique de vérité** |
| `pyproject.toml` → `[project].version` | consommée par l'installateur de LichtFeld |
| `CHANGELOG.md` | section datée par version |
| Tag git `vX.Y.Z` | point de référence immuable |

Ces quatre valeurs doivent concorder. Deux garde-fous l'imposent :

- `tests/test_version.py` compare `version.py`, `pyproject.toml` et le
  changelog ;
- la CI exécute `python scripts/bump_version.py --check` à chaque push.

La version est également affichée dans le panneau et journalisée au
chargement : un utilisateur peut toujours dire quelle version il exécute.

---

## Monter de version

```bash
python3 scripts/bump_version.py patch     # 0.1.0 -> 0.1.1
python3 scripts/bump_version.py minor     # 0.1.1 -> 0.2.0
python3 scripts/bump_version.py major     # 0.2.0 -> 1.0.0
```

Le script met à jour `core/version.py`, `pyproject.toml`, insère une section
`## [X.Y.Z] - AAAA-MM-JJ` dans le changelog et met à jour les liens de
comparaison. Il ne touche pas à git.

---

## Procédure de publication

```bash
# 1. Le tronc est propre et vert
python3 -m unittest discover -s tests -t .
ruff check . && ruff format --check .

# 2. Monter la version
python3 scripts/bump_version.py minor

# 3. Rédiger la section de changelog (remplacer le « - TODO »)
$EDITOR CHANGELOG.md

# 4. Vérifier
python3 scripts/bump_version.py --check

# 5. Publier
git commit -am "release: v0.2.0"
git tag -a v0.2.0 -m "v0.2.0"
git push && git push origin v0.2.0
```

Créez ensuite une *release* GitHub sur le tag, en reprenant la section du
changelog comme corps.

---

## Rédiger le changelog

Format [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) :
`Ajouté`, `Modifié`, `Déprécié`, `Retiré`, `Corrigé`, `Sécurité`.

Deux règles propres à ce projet :

1. **Tout changement de moteur ou de checkpoint est mentionné explicitement**,
   avec sa licence. C'est une information juridique, pas un détail technique.
2. **Tout épinglage de dépendance modifié est mentionné.** Une montée de
   PyTorch ou de MapAnything peut casser une installation qui fonctionnait.

---

## Compatibilité avec l'hôte

`pyproject.toml` déclare le contrat vis-à-vis de LichtFeld Studio :

```toml
[tool.lichtfeld]
plugin_api = ">=1,<2"
lichtfeld_version = ">=0.5.0"
```

`plugin_api` vise l'API publique des plugins, **pas** la version de ce plugin.
Si LichtFeld publie une API 2, ce plugin doit être testé puis publié en version
majeure avec la nouvelle borne.
