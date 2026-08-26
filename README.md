# PhotoSplat — plugin LichtFeld Studio

**Quelques photos d'un objet → un 3D Gaussian Splatting, sans étape d'alignement.**

[![Version](https://img.shields.io/badge/version-0.1.2-blue)](CHANGELOG.md)
[![Licence](https://img.shields.io/badge/licence-MIT-green)](LICENSE)
[![LichtFeld Studio](https://img.shields.io/badge/LichtFeld%20Studio-%E2%89%A5%200.5.0-orange)](https://github.com/MrNeRF/LichtFeld-Studio)

---

## Le problème que ce plugin résout

La chaîne 3DGS classique impose une étape d'alignement (COLMAP, RealityScan) qui
exige un jeu d'images à fort recouvrement ou une vidéo, et qui consomme
l'essentiel du temps de traitement.

PhotoSplat supprime cette étape : un modèle *feed-forward* estime en une passe
les poses de caméra et la géométrie 3D à partir de photos non calibrées, puis
produit un **dataset COLMAP** que LichtFeld Studio entraîne nativement.

```
   quelques photos                      PhotoSplat                    LichtFeld Studio
  (non calibrées)  ──────────►  MapAnything (1 passe GPU)  ──────────►  entraînement 3DGS
                                 poses + géométrie métrique              sur les vraies photos
                                          │                                      │
                                          ▼                                      ▼
                                  images/ + sparse/0/                    splat final fidèle
                                  + nuage d'initialisation
```

**Ce que le plugin ne fait pas** : il n'invente rien. Le splat final est
optimisé sur vos photos réelles par le moteur de LichtFeld. Aucune face n'est
hallucinée par un modèle génératif — c'est un choix assumé, motivé par l'usage
commercial visé (voir [`docs/01-analyse-stack.md`](docs/01-analyse-stack.md)).

---

## Prérequis

| | |
|---|---|
| **LichtFeld Studio** | ≥ 0.5.0 (système de plugins et runtime Python embarqué) |
| **GPU** | NVIDIA avec CUDA. Le plugin détecte la VRAM et adapte le nombre de vues traitées |
| **Disque** | ~6 Go : environnement Python isolé + poids du modèle |
| **Réseau** | Requis au premier lancement (téléchargement des poids depuis Hugging Face) |
| **Compte** | Aucun. Pas de `hf auth login`, pas de conditions à accepter |

Les poids ne sont jamais redistribués par ce dépôt : ils sont téléchargés à la
demande depuis `facebook/map-anything-apache`.

---

## Installation

### Depuis LichtFeld Studio

Console Python de l'application :

```python
import lichtfeld as lf
lf.plugins.install("baronstudio/LFS_Plugin_TripoSpltQuerySplat")
```

> Nécessite un **dépôt public** et le code sur la **branche par défaut** :
> l'installeur télécharge l'archive GitHub sans authentification. Sur un dépôt
> privé, la commande échoue sur `urlopen` (404). Voir
> [`docs/03-installation.md`](docs/03-installation.md).

### Par clone (fonctionne aussi sur dépôt privé)

```bash
git clone https://github.com/baronstudio/LFS_Plugin_TripoSpltQuerySplat.git
cd LFS_Plugin_TripoSpltQuerySplat
./scripts/install.sh          # Linux / macOS
# .\scripts\install.ps1       # Windows (mode développeur ou admin)
```

Puis, dans LichtFeld Studio :

```python
import lichtfeld as lf
lf.plugins.discover()
lf.plugins.load("photosplat")
```

Détails et diagnostic : [`docs/03-installation.md`](docs/03-installation.md).

---

## Utilisation

Le panneau **PhotoSplat** apparaît dans la zone à onglets principale, à côté de « Rendering » et « Training ».

1. **Photos** — désignez le dossier. `Analyser` liste les images exploitables.
   Comptez **6 à 20 vues** autour du sujet ; deux vues suffisent techniquement,
   mais l'entraînement n'aura pas de quoi travailler.
2. **Moteur** — `MapAnything` par défaut. La licence et le modèle utilisés sont
   affichés en clair, ainsi que tout blocage détecté (GPU absent, dépendance
   manquante).
3. **Réglages** *(repliés)* — graine, finesse du nuage, plafond de vues.
4. **Générer** — la barre de progression suit les étapes ; `Annuler` est pris en
   compte au prochain point de contrôle (l'inférence en cours n'est pas
   interruptible).
5. **Résultat** — `Charger le dataset` l'importe dans la scène ;
   `Charger et entraîner` enchaîne directement sur l'entraînement natif.

Les sorties sont écrites dans `~/.lichtfeld/photosplat/runs/<horodatage>-<moteur>/` :

```
images/            photos ré-échantillonnées à la résolution du modèle
sparse/
  cameras.bin      convention MapAnything
  images.bin
  points3D.bin
  points.ply       nuage d'initialisation (passé en init_path)
  0/               même contenu, convention attendue par LichtFeld/COLMAP
output/            sortie de l'entraînement
```

---

## Réglages

| Réglage | Défaut | Effet |
|---|---|---|
| Graine | `42` | Mêmes photos + même graine = même résultat |
| Finesse du nuage | `0.01` | Taille du voxel en fraction de l'étendue de la scène. Plus petit = nuage d'init plus dense, entraînement plus lourd |
| Vues max | `0` (auto) | Plafond de vues envoyées au GPU. `0` = déduit de la VRAM détectée |
| Entraîner automatiquement | désactivé | Enchaîne l'entraînement dès la génération terminée |

Les réglages sont stockés dans `~/.lichtfeld/photosplat/settings.json`, hors du
dossier d'installation : une mise à jour du plugin ne les efface pas.

---

## Licences

Le code de ce plugin est sous **MIT**. Le point sensible est ailleurs — dans les
poids des modèles :

| Composant | Licence | Usage commercial |
|---|---|---|
| Ce plugin | MIT | ✅ |
| Code MapAnything | Apache 2.0 | ✅ |
| Poids `facebook/map-anything-apache` | Apache 2.0 | ✅ |
| ~~Poids `facebook/map-anything`~~ | CC-BY-NC 4.0 | ❌ — volontairement inaccessible depuis le plugin |
| ~~AnySplat~~ | MIT affiché, mais initialisé sur `facebook/VGGT-1B` (non commercial) et embarquant du code CroCo CC-BY-NC-SA | ❌ écarté |
| ~~QuerySplat / VGGT-Omega~~ | FAIR Noncommercial | ❌ écarté |

Un test automatisé (`tests/test_backends.py`) échoue si un moteur non
commercial est ajouté au registre sans décision explicite.

---

## Structure du dépôt

```
__init__.py              point d'entrée (on_load / on_unload)
pyproject.toml           dépendances + contrat [tool.lichtfeld]
core/                    logique métier — aucune dépendance à l'interface
  version.py             source unique du numéro de version
  images.py              scan et validation des photos
  gpu.py                 détection VRAM et garde-fous
  settings.py            préférences persistantes
  pipeline.py            exécution en tâche de fond
  lfs.py                 adaptateur de l'API LichtFeld
  backends/              moteurs — un fichier par moteur
panels/main_panel.py     interface (affichage uniquement)
tests/                   41 tests, sans GPU ni torch ni LichtFeld
scripts/                 installation et montée de version
docs/                    documentation technique
```

Le noyau est importable sans torch, sans CUDA et sans LichtFeld Studio : c'est
ce qui rend la CI possible sur un simple runner GitHub.

---

## Versionnage

SemVer, source unique dans `core/version.py`, cohérence vérifiée en CI.

```bash
python3 scripts/bump_version.py --check    # vérifie version.py / pyproject.toml / CHANGELOG
python3 scripts/bump_version.py minor      # 0.1.0 -> 0.2.0 + section de changelog
```

Voir [`docs/04-versionnage.md`](docs/04-versionnage.md).

---

## État de validation

Transparence sur ce qui est réellement testé à ce jour :

| Périmètre | État |
|---|---|
| Noyau (scan, validation, réglages, runner, registre, version) | ✅ 41 tests automatisés, verts en CI |
| Lint et format (`ruff`) | ✅ verts |
| Chaîne GPU complète (MapAnything → dataset → entraînement) | ⚠️ **non exécutée** : développée sans accès à un GPU NVIDIA ni à LichtFeld Studio |
| Chargement du plugin dans l'application | ✅ validé sur LichtFeld 0.5.3 / Windows (correctif 0.1.1) |
| Rendu du panneau dans l'application | ⚠️ **non exécuté** sans GPU ni application |

La première exécution sur votre poste est donc une recette à part entière.
[`docs/05-depannage.md`](docs/05-depannage.md) liste les points de rupture
probables et la marche à suivre.

---

## Feuille de route

| Version | Contenu |
|---|---|
| `0.1.0` | Chaîne MapAnything → dataset COLMAP → entraînement natif |
| `0.2.0` | Recette GPU, réglages issus du terrain, presets objet |
| `0.3.0` | Moteur `triposplat` (1 photo → splat direct, MIT) pour les objets isolés |
| `0.4.0` | Export `.ply` / `.splat`, traitement par lots |

---

## Documentation

- [`docs/01-analyse-stack.md`](docs/01-analyse-stack.md) — analyse concurrentielle des modèles et audit des licences
- [`docs/02-architecture.md`](docs/02-architecture.md) — architecture interne et ajout d'un moteur
- [`docs/03-installation.md`](docs/03-installation.md) — installation détaillée
- [`docs/04-versionnage.md`](docs/04-versionnage.md) — convention de version et procédure de publication
- [`docs/05-depannage.md`](docs/05-depannage.md) — diagnostic

## Références

- [LichtFeld Studio](https://github.com/MrNeRF/LichtFeld-Studio) · [système de plugins](https://github.com/MrNeRF/LichtFeld-Studio/blob/master/docs/plugin-system.md)
- [MapAnything](https://github.com/facebookresearch/map-anything) (Meta, Apache 2.0)
