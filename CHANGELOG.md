# Journal des versions

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).
Versionnage : [SemVer](https://semver.org/lang/fr/) -- voir `docs/04-versionnage.md`.

## [Non publie]

## [0.1.3] - 2026-08-26

### Corrige
- **Le panneau restait invisible malgre un plugin actif** (suite de 0.1.2).
  Comparaison faite avec le gabarit genere par `lf.plugins.create()` et avec un
  plugin tiers fonctionnel, trois ecarts subsistaient :
  - **Coquille RML absente.** Le gabarit officiel comme les plugins existants
    fournissent tous un `panels/main_panel.rml` designe par l'attribut
    `template`. Sans lui, le panneau est enregistre mais ne s'affiche nulle
    part, sans erreur. Ajout de `main_panel.rml` (avec le point d'ancrage
    `<div id="im-root">` ou se monte le rendu immediat) et de `main_panel.rcss`.
  - **Imports absolus.** Le plugin est charge comme un paquet ; `__init__.py`
    et le panneau utilisent desormais des imports relatifs, comme le gabarit.
    En absolu, `core` et `panels` sont des noms assez generiques pour entrer en
    collision avec ceux d'un autre plugin charge dans le meme interpreteur.
  - **Journalisation.** `print()` remplace par `lf.log.info` / `lf.log.warn`,
    qui alimentent l'onglet Logging de LichtFeld Studio.

### Ajoute
- `panels/main_panel.rml` et `panels/main_panel.rcss` : coquille minimale du
  panneau, tout le contenu restant dessine en mode immediat.


## [0.1.2] - 2026-08-26

### Corrige
- **Le plugin passait « active » mais aucun panneau n'apparaissait.** Deux
  causes, alignees sur les plugins LichtFeld existants :
  - `MainPanel.__init__` appelait `super().__init__()`. La classe de base
    `lf.ui.Panel` est exposee depuis le C++ et son constructeur n'accepte pas
    cet appel : la construction du panneau echouait. Le plugin restant charge,
    l'echec ne remontait nulle part.
  - L'emplacement etait `PanelSpace.SIDE_PANEL`. Le panneau est desormais en
    `PanelSpace.MAIN_PANEL_TAB`, dans la zone a onglets principale, aux cotes
    de « Rendering » et « Training ».

### Modifie
- Ajout de `order = 230` pour un rang stable parmi les onglets.


## [0.1.1] - 2026-08-26

### Corrige
- **LichtFeld Studio figeait au chargement du plugin, sans activite CPU.**
  `MapAnythingBackend.check()` faisait `import torch` puis `import mapanything`,
  et `gpu.detect()` importait torch. Ces deux appels ont lieu dans le
  constructeur du panneau, donc sur le fil de l'interface : la chaine d'imports
  (torch, uniception, timm, torchvision, rerun-sdk, tensorboard) prend des
  dizaines de secondes sous Windows, essentiellement en chargement de DLL --
  d'ou une application figee sans charge machine visible.
  - `check()` utilise desormais `importlib.util.find_spec`, qui constate la
    presence d'un module sans l'executer.
  - `gpu.detect()` s'appuie sur `nvidia-smi` seul.
  - La disponibilite reelle de CUDA est verifiee au lancement de la generation,
    dans `run()`, avec un message citant `torch.__version__` et
    `torch.version.cuda`.
  - Deux tests de non-regression echouent si un import lourd revient sur le
    chemin de l'interface.

### Modifie
- `core/gpu.py` ne depend plus de torch. La detection constate la presence d'un
  GPU et d'un pilote, pas l'utilisabilite de CUDA par torch : compromis assume
  et documente.


### Corrige
- Documentation : recuperation apres une interruption de `uv sync`. Un arret de
  LichtFeld pendant la synchronisation laisse des verrous orphelins ; le
  chargement suivant attend indefiniment, sans consommer aucune ressource.
  Procedure de nettoyage dans `docs/05-depannage.md` (entree 2).
- Documentation : `lf.plugins.install()` exige un depot public et le code sur
  la branche par defaut. L'installeur de LichtFeld telecharge l'archive GitHub
  sans authentification ; sur un depot prive, l'echec se presente comme une
  panne reseau (trace terminee sur `urlopen`). Procedure de repli par clone
  documentee dans le README, `docs/03-installation.md` et `docs/05-depannage.md`.

## [0.1.0] - 2026-08-26

Premiere version. Chaine complete « quelques photos -> splat » sans etape
d'alignement prealable.

### Ajoute
- Panneau lateral PhotoSplat : selection du dossier de photos, choix du moteur,
  reglages, generation, journal.
- Moteur `mapanything` : estimation des poses et de la geometrie metrique a
  partir de photos non calibrees, puis export d'un dataset COLMAP
  (`images/` + `sparse/0/`) et d'un nuage d'initialisation.
- Passage de relais a LichtFeld Studio : chargement du dataset avec
  `init_path`, puis lancement de l'entrainement natif 3DGS.
- Detection automatique du GPU et de la VRAM, avec plafond de vues derive.
- Registre de moteurs extensible (`core/backends/`).
- Reglages persistants hors du dossier d'installation.
- Documentation technique (`docs/`) et analyse de stack.
- Systeme de version tracable : source unique, verification automatisee,
  script de montee de version, CI.

### Choix techniques notables
- Checkpoint `facebook/map-anything-apache` (Apache 2.0) impose : le
  checkpoint par defaut de MapAnything est CC-BY-NC et reste inaccessible
  depuis le plugin, l'usage vise etant commercial.
- AnySplat, QuerySplat et VGGT-Omega ecartes pour contamination de licence
  non commerciale. Detail dans `docs/01-analyse-stack.md`.

[Non publie]: https://github.com/baronstudio/LFS_Plugin_TripoSpltQuerySplat/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/baronstudio/LFS_Plugin_TripoSpltQuerySplat/releases/tag/v0.1.3
[0.1.2]: https://github.com/baronstudio/LFS_Plugin_TripoSpltQuerySplat/releases/tag/v0.1.2
[0.1.1]: https://github.com/baronstudio/LFS_Plugin_TripoSpltQuerySplat/releases/tag/v0.1.1
[0.1.0]: https://github.com/baronstudio/LFS_Plugin_TripoSpltQuerySplat/releases/tag/v0.1.0
