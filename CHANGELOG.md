# Journal des versions

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).
Versionnage : [SemVer](https://semver.org/lang/fr/) -- voir `docs/04-versionnage.md`.

## [Non publie]

### Ajoute
- Evaluation de Spirula Studio (`docs/06`, section 5) : entraineur 3DGS
  autonome en C++/Vulkan, GPL-3.0. Son SfM est un SIFT incremental facon
  COLMAP, donc sujet aux memes deux obstacles que MapAnything sur une prise de
  vue plateau tournant a fond blanc. Il apporte en revanche une contre-expertise
  du diagnostic, la relecture directe de nos datasets, et surtout l'idee
  d'ecrire les masques dans `masks/` pour les fournir a l'entrainement plutot
  que de seulement nettoyer le nuage d'initialisation.
- Audit de licence de TRELLIS et Hunyuan3D (`docs/01-analyse-stack.md`, 8.4).
  Hunyuan3D est ecarte : sa licence exclut explicitement l'Union europeenne du
  territoire couvert. TRELLIS est exploitable commercialement a condition de
  rester sur le chemin gaussien, ses deux sous-modules non commerciaux etant un
  moteur de rendu et un extracteur de maillage, dont le plugin n'a pas besoin.
- `docs/06-prise-de-vue-et-poses.md` : analyse du cas « produit studio ». Une
  prise de vue sur plateau tournant a fond blanc met en echec l'estimation de
  pose -- le modele cherche le deplacement d'une camera qui n'a pas bouge. Six
  options chiffrees, du tapis texture solidaire du plateau (sans code) aux
  poses declarees par gabarit, jusqu'au moteur objet-centre.
- README : avertissement sur le protocole de prise de vue.

## [0.2.1] - 2026-08-26

### Corrige
- **`UnboundLocalError: cannot access local variable 'outputs'` masquait
  l'erreur reelle.** Le bloc `finally` referencait `outputs`, non encore liee
  lorsque l'echec survenait avant l'inference. L'utilisateur voyait donc une
  erreur de variable la ou le probleme etait tout autre. La variable est
  desormais initialisee avant le `try`.
- **`ValueError: No valid images found` sur des fichiers TIFF.** Le scan du
  plugin acceptait les TIFF, que `load_images` refuse : il ne lit que JPG, PNG
  et, via pillow-heif, HEIC/HEIF.

### Ajoute
- **Conversion automatique des formats non natifs.** TIFF, WebP et BMP sont
  convertis en PNG dans un dossier de travail avant l'inference, plutot que
  rejetes : le TIFF est courant en production photo, et le moteur re-encode de
  toute facon les images a sa propre resolution. Le nombre de conversions est
  annonce dans le panneau avant la generation, et journalise pendant.
- `BackendInfo.native_suffixes` : chaque moteur declare ce qu'il lit sans
  conversion. HEIC et HEIF sont natifs, pillow-heif arrivant avec mapanything.
- `dedupe_names()` : la conversion peut recreer une collision de noms
  (`a.tif` et `a.png` donneraient tous deux `a.png`), que COLMAP ne tolere pas.
- 7 tests de preparation des images : formats natifs laisses intacts, TIFF
  converti, melange de formats, collision apres conversion, TIFF en niveaux de
  gris, extensions en majuscules.


## [0.2.0] - 2026-08-26

Premiere chaine complete fonctionnelle : l'inference multi-vues sur GPU est
validee sur le poste cible, et l'export ne depend plus d'aucun composant natif.

### Retire
- **Dependances `pycolmap` et `open3d`.** Sur Windows / Python 3.12, `pycolmap`
  n'existe qu'en 3.10.0 -- les versions 4.x ne publient pas de roue pour cette
  combinaison -- et cette roue echoue a l'import : « DLL load failed while
  importing pycolmap: une routine d'initialisation d'une bibliotheque de liens
  dynamiques a echoue ». L'export s'arretait donc en toute fin de chaine, apres
  une inference reussie.

### Ajoute
- `core/colmap.py` : ecriture du format COLMAP binaire (`cameras.bin`,
  `images.bin`, `points3D.bin`), export PLY et sous-echantillonnage par voxels,
  en numpy et `struct` uniquement. Aucun algorithme de COLMAP n'etait utilise :
  il ne s'agissait que de serialiser cameras, poses et nuage de points.
- 16 tests d'aller-retour : les fichiers produits sont relus par un lecteur
  ecrit a partir de la specification du format, et non a partir du code teste,
  de sorte qu'une erreur d'ecriture ne puisse pas se compenser elle-meme.
  Conversions quaternion et inversion de pose verifiees sur des rotations
  aleatoires, y compris les cas a trace negative.

### Modifie
- Le dataset est ecrit directement dans `sparse/0/`, sans recopie apres coup.
- La VRAM est liberee avant l'ecriture du dataset, et non apres : tout est
  rapatrie sur le CPU des la fin de l'inference.
- Installation allegee d'environ 450 Mo, et privee de ses deux seuls composants
  natifs fragiles.


## [0.1.5] - 2026-08-26

### Ajoute
- **Echec rapide sur dependance defaillante.** `run()` importe reellement les
  modules requis avant tout travail couteux. Une dependance installee mais
  inutilisable -- DLL introuvable, extension native compilee contre une autre
  version de NumPy, runtime C++ absent -- se signale desormais en quelques
  secondes, au lieu d'apres le telechargement des poids et une inference
  complete.
  Constate sur `pycolmap` : `find_spec` le trouvait, l'import echouait a
  l'export, en toute fin de chaine.
- Message d'erreur distinguant le module absent du module present mais casse,
  et citant l'erreur d'import d'origine.


## [0.1.4] - 2026-08-26

### Corrige
- **`AttributeError: module 'lichtfeld' has no attribute 'is_training_active'`
  au clic sur « Generer ».** Cette fonction existe sur la branche `master` de
  LichtFeld Studio mais pas en 0.5.3, ou l'equivalent est `trainer_state()`.
  L'exception survenant pendant `draw()`, le panneau entier cessait de
  s'afficher.
  - `core/lfs.py` devient un adaptateur reellement defensif : aucune de ses
    fonctions ne leve, les appels absents retournent une valeur neutre.
  - `is_training_active()` essaie `is_training_active`, puis `trainer_state()`,
    puis repond « non ».
- **Plafond de vues errone sur une carte 8 Go.** `nvidia-smi` rapporte
  8188 Mio, soit 7,996 Gio : le seuil pose a `8.0` faisait retomber la carte au
  palier le plus prudent (6 vues au lieu de 12). Les seuils passent sous les
  capacites nominales.

### Ajoute
- `draw()` est protege : une erreur de rendu s'affiche dans le panneau et n'est
  journalisee qu'une fois, au lieu de faire disparaitre l'interface entiere.
- 13 tests supplementaires (54 au total) : adaptateur d'hote face a une API
  incomplete, et non-regression sur les paliers de VRAM.

### Modifie
- Toute la journalisation passe par `core.lfs.log`, qui s'adapte a `info`,
  `warn` ou `warning` selon ce qu'expose l'hote.


### Modifie
- README : le rendu du panneau passe de « non execute » a valide sur LichtFeld
  Studio 0.5.3 / Windows (RTX 4060 Laptop, 8 Go). La detection GPU, le registre
  des moteurs et la presence des dependances sont eux aussi constates sur le
  poste cible. Seule la chaine GPU complete reste a recetter.

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

[Non publie]: https://github.com/baronstudio/LFS_Plugin_TripoSpltQuerySplat/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/baronstudio/LFS_Plugin_TripoSpltQuerySplat/releases/tag/v0.2.1
[0.2.0]: https://github.com/baronstudio/LFS_Plugin_TripoSpltQuerySplat/releases/tag/v0.2.0
[0.1.5]: https://github.com/baronstudio/LFS_Plugin_TripoSpltQuerySplat/releases/tag/v0.1.5
[0.1.4]: https://github.com/baronstudio/LFS_Plugin_TripoSpltQuerySplat/releases/tag/v0.1.4
[0.1.3]: https://github.com/baronstudio/LFS_Plugin_TripoSpltQuerySplat/releases/tag/v0.1.3
[0.1.2]: https://github.com/baronstudio/LFS_Plugin_TripoSpltQuerySplat/releases/tag/v0.1.2
[0.1.1]: https://github.com/baronstudio/LFS_Plugin_TripoSpltQuerySplat/releases/tag/v0.1.1
[0.1.0]: https://github.com/baronstudio/LFS_Plugin_TripoSpltQuerySplat/releases/tag/v0.1.0
