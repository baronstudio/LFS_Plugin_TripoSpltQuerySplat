# Dépannage

| | |
|---|---|
| **Version doc** | 1.0.0 |
| **Public** | Technicien |

---

## Avertissement : ce qui n'a pas encore été exécuté

Le noyau du plugin est couvert par 38 tests automatisés verts. En revanche, la
**chaîne GPU complète** (chargement de MapAnything, inférence, export COLMAP,
reprise par l'entraînement natif) et le **rendu du panneau** n'ont jamais été
exécutés : le développement s'est fait sans accès à un GPU NVIDIA ni à
LichtFeld Studio.

La première exécution sur votre poste est donc une recette. Cette page liste,
par ordre de probabilité, les points de rupture attendus et la marche à suivre.

---

## Diagnostic de premier niveau

Dans la console Python de LichtFeld Studio :

```python
import lichtfeld as lf
lf.plugins.get_state("photosplat")       # ACTIVE attendu
lf.plugins.get_error("photosplat")
lf.plugins.get_traceback("photosplat")
```

---

## Points de rupture probables

### 1. L'environnement isolé ne se construit pas (`uv sync` échoue)

**Cause la plus probable** : les versions PyTorch épinglées
(`torch==2.11.0` / `torchvision==0.26.0`, index `cu130`) ne correspondent pas au
Python embarqué par votre build de LichtFeld ou à votre driver.

**Correctif** : dans `pyproject.toml`, alignez l'URL de l'index et les versions
sur votre configuration, puis réinstallez le plugin.

```toml
[[tool.uv.index]]
url = "https://download.pytorch.org/whl/cu126"   # à adapter
```

Vérifiez la version CUDA supportée par votre driver avec `nvidia-smi`
(coin supérieur droit).

### 2. `Paquet mapanything introuvable`

L'installation de `mapanything` depuis git a échoué (réseau, proxy, git absent
du PATH, ou compilation d'une dépendance). Relancez l'installation du plugin et
lisez le journal de `uv sync`. En dernier recours, installez manuellement dans
le venv du plugin :

```bash
~/.lichtfeld/plugins/photosplat/.venv/bin/pip install \
  "mapanything @ git+https://github.com/facebookresearch/map-anything.git@v1.1.3" \
  "pycolmap==3.10.0" open3d
```

### 3. `Aucun GPU CUDA disponible`

`torch.cuda.is_available()` renvoie faux. Soit le driver est trop ancien pour
la roue CUDA installée, soit une roue CPU a été résolue. Vérifiez dans le venv
du plugin :

```python
import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())
```

Un `torch.version.cuda` à `None` signifie roue CPU → point 1.

### 4. Mémoire GPU insuffisante pendant l'inférence

**Symptômes** : `CUDA out of memory`, ou l'application se fige puis reprend.

**Correctifs**, dans l'ordre :
1. Réglages → **Vues max** : imposez une valeur inférieure au plafond auto.
2. Fermez la scène en cours (`lf.clear_scene()`) avant de générer.
3. Arrêtez tout entraînement : le plugin le détecte et refuse de démarrer, mais
   un autre processus peut aussi occuper la VRAM.

Le plafond automatique est volontairement prudent (6 vues si la VRAM n'a pas pu
être détectée). Il est dérivé dans `core/gpu.py`, table `_VIEW_BUDGET`.

### 5. LichtFeld ne reconnaît pas le dataset généré

**Cause probable** : convention de dossier. MapAnything écrit `sparse/*.bin`,
LichtFeld attend `sparse/0/*.bin`. Le plugin duplique les fichiers dans
`sparse/0/` (`_arrange_colmap_layout`). Vérifiez que le dossier de run contient
bien :

```
images/           non vide
sparse/0/cameras.bin  images.bin  points3D.bin
sparse/points.ply
```

Si `sparse/0/` est vide, l'export a échoué avant : consultez le journal du
panneau.

### 6. Le panneau ne s'affiche pas / erreur d'appel d'un widget

L'API immédiate de LichtFeld peut évoluer d'une version à l'autre. Le panneau
n'utilise que des widgets documentés (`label`, `heading`, `button`,
`button_styled`, `checkbox`, `combo`, `input_int`, `input_float`, `path_input`,
`progress_bar`, `collapsing_header`, `separator`, `same_line`, `text_colored`,
`text_disabled`, `text_wrapped`, `set_tooltip`, `begin_disabled`).

En cas d'erreur sur l'un d'eux, `lf.plugins.get_traceback("photosplat")` donne
la ligne exacte. Le correctif est local à `panels/main_panel.py` : la logique
métier n'est pas concernée.

### 7. Le bouton `Annuler` ne réagit pas immédiatement

Comportement normal et documenté : l'annulation est prise en compte au prochain
point de contrôle. Une inférence GPU déjà lancée n'est pas interruptible.

### 8. Résultat de mauvaise qualité

Ce n'est pas nécessairement un bug. Par ordre de fréquence :

| Cause | Signe | Correctif |
|---|---|---|
| Trop peu de vues | géométrie trouée, faces manquantes | 6 à 20 vues autour du sujet |
| Vues trop dispersées | poses incohérentes | rapprochez les points de vue, gardez du recouvrement |
| Sujet réfléchissant ou transparent | bruit, géométrie fantôme | limite intrinsèque des modèles feed-forward |
| Nuage d'init trop grossier | splat mou après entraînement | baissez **Finesse du nuage** (0.005) |
| Entraînement trop court | flou général | augmentez les itérations côté LichtFeld |

Rappel : le plugin ne produit pas le splat final. La qualité finale dépend de
l'entraînement natif, réglé dans LichtFeld Studio.

---

## Remonter un problème

Ouvrez une *issue* sur le dépôt avec :

1. la version du plugin (affichée en haut du panneau) ;
2. la version de LichtFeld Studio ;
3. la sortie de `nvidia-smi` ;
4. `lf.plugins.get_traceback("photosplat")` ;
5. le contenu du journal du panneau (section repliable « Journal ») ;
6. le nombre de photos et, si possible, un exemple.
