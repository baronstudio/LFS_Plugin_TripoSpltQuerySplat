# Installation

| | |
|---|---|
| **Version doc** | 1.0.0 |
| **Public** | Technicien / intégrateur |

---

## 1. Vérifier les prérequis

```bash
nvidia-smi          # doit lister un GPU et une version de driver
```

| Élément | Exigence | Pourquoi |
|---|---|---|
| LichtFeld Studio | ≥ 0.5.0 | le système de plugins et le runtime Python embarqué n'existent qu'à partir de cette version |
| GPU NVIDIA | CUDA fonctionnel | l'inférence n'a pas de repli CPU exploitable |
| VRAM | 8 Go minimum conseillé | le plafond de vues est dérivé automatiquement de la VRAM détectée |
| Disque | ~6 Go | ~4 Go d'environnement Python isolé + ~2 Go de poids |
| Réseau | au premier lancement | téléchargement des poids depuis Hugging Face |

Aucun compte Hugging Face n'est nécessaire : le checkpoint utilisé
(`facebook/map-anything-apache`) est public et sans conditions à accepter.

---

## 2. Installer

### Option A — depuis LichtFeld Studio

Console Python de l'application :

```python
import lichtfeld as lf
lf.plugins.install("baronstudio/LFS_Plugin_TripoSpltQuerySplat")
```

> **Deux conditions, sans quoi cette commande échoue :**
>
> 1. **Le dépôt doit être public.** L'installeur télécharge
>    `https://api.github.com/repos/<owner>/<repo>/tarball` en n'envoyant qu'un
>    en-tête `User-Agent` : aucun jeton d'authentification n'est transmis
>    (`lfs_plugins/installer.py`, `_download_url_to_temp`). Sur un dépôt privé,
>    GitHub répond **404** et la trace s'arrête sur `urlopen`.
> 2. **Le code doit être sur la branche par défaut.** Sans référence explicite,
>    `github_archive_url()` interroge l'endpoint `tarball` sans ref, que GitHub
>    résout vers la branche par défaut du dépôt (`master` ici).
>
> Une branche précise peut être visée avec la syntaxe `owner/repo@branche`,
> mais cela ne contourne pas la condition 1.
>
> Dépôt privé ? Utilisez l'option B : `git` s'authentifie avec vos identifiants,
> et `load()` construit l'environnement isolé exactement de la même façon.

### Option B — développement, par lien

```bash
git clone https://github.com/baronstudio/LFS_Plugin_TripoSpltQuerySplat.git
cd LFS_Plugin_TripoSpltQuerySplat
./scripts/install.sh
```

Windows, PowerShell en administrateur (ou mode développeur activé) :

```powershell
.\scripts\install.ps1
```

Le script crée un lien de `~/.lichtfeld/plugins/photosplat` vers le dépôt. Il
refuse d'écraser un dossier réel : à vous de le déplacer si besoin.

Puis :

```python
import lichtfeld as lf
lf.plugins.discover()
lf.plugins.load("photosplat")
```

---

## 3. Ce qui se passe au premier chargement

1. **Construction de l'environnement isolé.** LichtFeld exécute `uv venv` puis
   `uv sync` dans `<plugin>/.venv`, à partir de `[project].dependencies`.
   Compter plusieurs minutes : PyTorch CUDA pèse lourd.
2. **Chargement du panneau.** Immédiat : aucun modèle n'est chargé tant que
   vous ne cliquez pas sur `Générer`.
3. **Téléchargement des poids.** Au premier `Générer`, dans le cache Hugging
   Face (`~/.cache/huggingface` par défaut).

### Roue PyTorch

`pyproject.toml` épingle `torch==2.11.0` / `torchvision==0.26.0` depuis l'index
CUDA 13.0 :

```toml
[[tool.uv.index]]
name = "pytorch-cu130"
url = "https://download.pytorch.org/whl/cu130"
explicit = true
```

Ces versions correspondent au runtime de LichtFeld Studio 0.5. Si votre
installation embarque un autre Python ou si votre driver ne supporte pas
CUDA 13.0, ajustez l'URL de l'index (`cu126`, `cu128`…) **et les versions**, puis
réinstallez le plugin. C'est le point de rupture le plus probable — voir
`05-depannage.md`.

---

## 4. Emplacements sur le disque

| Chemin | Contenu | Versionné |
|---|---|---|
| `~/.lichtfeld/plugins/photosplat/` | le plugin (ou le lien vers le dépôt) | — |
| `~/.lichtfeld/plugins/photosplat/.venv/` | environnement Python isolé | non |
| `~/.lichtfeld/photosplat/settings.json` | préférences | non |
| `~/.lichtfeld/photosplat/runs/` | sorties de génération | non |
| `~/.cache/huggingface/` | poids des modèles | non |

Les réglages et les sorties sont volontairement **hors** du dossier
d'installation : une mise à jour ne les efface pas.

---

## 5. Mettre à jour

```python
import lichtfeld as lf
lf.plugins.check_updates()
```

En mode lien : `git pull`, puis rechargez le plugin depuis l'application. Si
`pyproject.toml` a changé, l'environnement isolé doit être reconstruit
(réinstallation du plugin).

---

## 6. Désinstaller

```python
import lichtfeld as lf
lf.plugins.unload("photosplat")
```

Puis supprimez `~/.lichtfeld/plugins/photosplat` (ou le lien). Pour effacer
aussi les données : `rm -rf ~/.lichtfeld/photosplat`.

---

## 7. Vérifier une installation de développement

Depuis le dépôt cloné, sans GPU ni LichtFeld :

```bash
python3 -m unittest discover -s tests -t . -v
python3 scripts/bump_version.py --check
ruff check . && ruff format --check .
```

Ces contrôles valident le noyau, pas la chaîne GPU. La recette matérielle reste
à faire sur le poste cible.
