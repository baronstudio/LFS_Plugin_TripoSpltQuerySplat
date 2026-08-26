# Journal des versions

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).
Versionnage : [SemVer](https://semver.org/lang/fr/) -- voir `docs/04-versionnage.md`.

## [Non publie]

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

[Non publie]: https://github.com/baronstudio/LFS_Plugin_TripoSpltQuerySplat/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/baronstudio/LFS_Plugin_TripoSpltQuerySplat/releases/tag/v0.1.0
