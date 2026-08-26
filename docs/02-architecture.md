# Architecture interne

| | |
|---|---|
| **Version doc** | 1.0.0 |
| **Public** | Développeur du plugin |

---

## Principe directeur : KISS

Une seule abstraction existe dans ce plugin : **le moteur** (`Backend`). Tout le
reste est du code direct. Concrètement :

- pas de couche d'injection de dépendances, pas d'événements, pas de registre
  générique de services ;
- un fichier = une responsabilité ;
- l'interface ne contient aucune logique métier, et le métier n'importe jamais
  l'interface ;
- toute complexité qui n'est pas justifiée par un besoin actuel est refusée.

L'abstraction `Backend` est justifiée : la stack de modèles bouge vite (voir
`01-analyse-stack.md`), et changer de moteur ne doit pas imposer de réécrire
l'interface.

---

## Flux de données

```
  panels/main_panel.py                      core/                          hôte
  ────────────────────                      ─────                          ────
  dossier de photos ──► core.images.scan_folder ──► ImageSet
                                  │
                                  ├── core.images.validate ──► problèmes bloquants
                                  │
                     core.gpu.detect ──► GpuInfo ──► plafond de vues
                                  │
  bouton « Générer » ──► core.pipeline.Job.start
                                  │  (thread)
                                  ▼
                      backend.run(images, work_dir, params, report, cancel)
                                  │
                                  ▼
                             RunResult
                       (dataset_dir, init_ply, splat_ply)
                                  │
  bouton « Charger » ──► core.lfs.load_dataset ──────────────────► lf.load_file
  bouton « Entraîner » ─► core.lfs.start_training ────────────────► lf.start_training
```

Le panneau ne connaît du travail en cours qu'un instantané immuable
(`JobState`), relu à chaque frame. Aucun état mutable n'est partagé entre le
thread d'interface et le thread de génération.

---

## Modules

| Module | Rôle | Dépendances lourdes |
|---|---|---|
| `core/version.py` | numéro de version, nom, identifiant | aucune |
| `core/images.py` | scan, tri, validation des photos | aucune |
| `core/gpu.py` | détection VRAM, dérivation des plafonds | torch *optionnel* |
| `core/settings.py` | préférences persistantes JSON | aucune |
| `core/pipeline.py` | exécution en tâche de fond, progression, annulation | aucune |
| `core/lfs.py` | adaptateur de l'API LichtFeld | `lichtfeld` *optionnel* |
| `core/backends/base.py` | contrat `Backend`, `RunResult`, utilitaires | aucune |
| `core/backends/registry.py` | catalogue des moteurs | — |
| `core/backends/mapanything_backend.py` | moteur multi-vues | torch, mapanything |
| `panels/main_panel.py` | interface | `lichtfeld` |

**Règle d'or** : tout import lourd (torch, mapanything) se fait *à l'intérieur
des fonctions*, jamais au niveau du module. C'est ce qui permet d'exécuter la
suite de tests sur un runner CI sans GPU, et de charger le plugin instantanément
sans attendre l'initialisation de CUDA.

**Corollaire, appris à la dure (bug corrigé en 0.1.1)** : « à l'intérieur d'une
fonction » ne suffit pas si cette fonction est appelée depuis le fil de
l'interface. `check()` et `gpu.detect()` sont invoqués par le constructeur du
panneau ; y importer torch figeait LichtFeld Studio des dizaines de secondes,
sans charge CPU visible — le temps passe en chargement de DLL.

La règle exacte est donc : **rien de lourd sur le chemin `__init__` /
`draw()` du panneau.** Pour constater la présence d'un module sans le charger,
utilisez `missing_modules()` (`core/backends/base.py`), qui repose sur
`importlib.util.find_spec`. Tout ce qui exige un vrai import appartient à
`run()`, qui s'exécute dans un thread de travail.

Deux tests verrouillent cette règle :
`test_check_never_imports_heavy_modules` et `test_detect_never_imports_torch`
remplacent `builtins.__import__` par une garde qui échoue si un module lourd
est chargé.

---

## Ajouter un moteur

Trois étapes, aucune autre modification.

### 1. Écrire le module

`core/backends/mon_moteur.py` :

```python
from .base import KIND_SPLAT, BackendInfo, ProgressFn, RunResult, raise_if_cancelled

INFO = BackendInfo(
    name="mon_moteur",              # identifiant technique, stable
    label="Mon moteur (1 photo)",   # libellé affiché
    kind=KIND_SPLAT,                # KIND_SPLAT ou KIND_DATASET
    min_images=1,
    max_images=1,
    model_id="org/mon-modele",
    license="MIT",
    commercial_ok=True,             # un test échoue si False sans décision explicite
    summary="Ce que fait le moteur, en une phrase.",
)


class MonMoteur:
    info = INFO

    def check(self) -> list[str]:
        """Liste vide = prêt. Sinon, chaque chaîne s'affiche en rouge."""
        return []

    def run(self, images, work_dir, params, report, cancel) -> RunResult:
        report(0.1, "Chargement du modèle")
        raise_if_cancelled(cancel)
        ...
        result = RunResult(splat_ply=work_dir / "sortie.ply")
        result.add("Message pour le journal")
        return result
```

### 2. L'enregistrer

`core/backends/registry.py` :

```python
from .mon_moteur import MonMoteur
_register(MonMoteur())
```

### 3. Déclarer ses dépendances

Dans `pyproject.toml`, section `[project].dependencies`, **avec version
épinglée**. LichtFeld reconstruit le venv isolé du plugin à l'installation.

Le panneau s'adapte seul : le moteur apparaît dans la liste déroulante, sa
licence s'affiche, ses contraintes de nombre d'images sont appliquées, et la
section « Résultat » s'ajuste selon `kind`.

---

## Contrats à respecter

- **`check()` ne lève jamais.** Un moteur mal installé doit s'afficher en rouge,
  pas planter le panneau.
- **`run()` appelle `report()` régulièrement.** Sans quoi la barre de
  progression reste figée et l'utilisateur croit à un blocage.
- **`run()` appelle `raise_if_cancelled()` entre les étapes longues.** Une
  inférence GPU en cours n'est pas interruptible : c'est documenté à
  l'utilisateur, ne prétendez pas le contraire.
- **`run()` libère la VRAM avant de rendre la main** (`del model`,
  `torch.cuda.empty_cache()`), dans un `finally`. L'entraînement natif démarre
  juste après et a besoin de toute la mémoire disponible.
- **Les poids ne sont jamais versionnés dans le dépôt.** Téléchargement à la
  demande, et licence affichée dans l'interface.

---

## Choix assumés

**Pourquoi produire un dataset COLMAP plutôt que directement un splat ?**
Parce que le splat final doit être fidèle au sujet. Un modèle feed-forward
plafonne en résolution et invente les zones non observées ; l'optimiseur de
LichtFeld, lui, travaille sur les pixels réels. Le modèle sert à supprimer
l'alignement, pas à remplacer l'entraînement.

**Pourquoi dupliquer `sparse/*.bin` dans `sparse/0/` ?**
MapAnything écrit selon une convention, LichtFeld et COLMAP en attendent une
autre. Copier trois fichiers coûte quelques kilo-octets et évite un dossier
inutilisable par l'un ou l'autre des outils.

**Pourquoi `hot_reload = false` ?**
Le plugin lance des threads et charge des modèles en VRAM. Un rechargement à
chaud laisserait des threads orphelins et de la mémoire GPU non libérée.
