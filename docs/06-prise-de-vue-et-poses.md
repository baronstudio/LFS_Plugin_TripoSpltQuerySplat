# Pourquoi les caméras se regroupent — et comment traiter le cas « produit studio »

| | |
|---|---|
| **Version doc** | 1.0.0 |
| **Date** | 2026-08-27 |
| **Statut** | Aide à la décision — options ouvertes |
| **Public** | Technicien prise de vue / dev plugin |

---

## 1. Le symptôme

Quatre photos studio d'un siège (dos 3/4, face 3/4, face, profil), fond blanc.
Le nuage produit contient bien le siège, mais :

- **les quatre caméras sont empilées au même endroit**, au lieu d'être réparties
  autour du sujet ;
- des **traînées blanches** flottent autour de l'objet ;
- la géométrie ressemble à une seule vue extrudée, pas à une fusion de quatre.

Ce n'est pas un défaut de réglage. C'est une **incompatibilité de fond** entre
le protocole de prise de vue et l'hypothèse sur laquelle repose le modèle.

---

## 2. Le diagnostic

### 2.1 L'objet tourne, pas la caméra

Sur les quatre images, le cadrage, l'éclairage, l'ombre portée et la position
à l'écran du piètement sont **identiques**. Seule l'orientation du siège change.
C'est une prise de vue sur plateau tournant : **la caméra n'a pas bougé**.

Or MapAnything — comme toute la famille VGGT, DUSt3R, π³ — répond à une seule
question : *« comment la caméra s'est-elle déplacée dans une scène immobile ? »*

Pour un plateau tournant, la réponse correcte à cette question est
**« elle n'a pas bougé »**. Le modèle n'a pas échoué : il a répondu juste à une
question qui n'était pas la nôtre. D'où les quatre caméras au même point.

### 2.2 Le fond blanc ne fournit aucun repère

Ces modèles trianguleront sur ce que deux vues **partagent**. Un cyclo blanc
n'a aucune texture : zéro point d'appui. Le seul contenu commun est l'objet
lui-même, vu sous des angles radicalement différents.

Pire, une zone uniforme reçoit une profondeur arbitraire : ce sont les
**traînées blanches** visibles dans le résultat.

### 2.3 Des pas de 90° dépassent le domaine du modèle

Ces modèles sont entraînés sur des séquences à fort recouvrement. Au-delà de
30 à 40° entre deux vues, l'appariement s'effondre — même avec un fond texturé.

### 2.4 Ce n'est pas leur domaine d'entraînement

MapAnything est entraîné sur des **scènes** : intérieurs, rues, paysages. Une
photo de produit détouré sur cyclo est à l'exact opposé de ces données.

> **En résumé** : le moteur actuel répond bien au cas « je marche autour d'un
> lieu en filmant ». Il ne peut pas répondre au cas « studio, plateau tournant,
> fond blanc, quatre vues à 90° ».

---

## 3. Les options

### Option A — Corriger le protocole de prise de vue *(aucun code)*

Rendre la capture compatible avec l'hypothèse du modèle :

- **faire tourner la caméra autour de l'objet**, et non l'objet ;
- garder du **contexte visible** : sol, mur, pied de studio — pas de détourage
  à la prise de vue ;
- **resserrer les pas** : 20 à 30°, soit 12 à 18 vues.

✅ Gratuit, immédiat, efficace.
❌ Contredit la promesse d'origine — « quelques photos, pas de recouvrement » —
et impose de refaire toutes les prises de vue produit existantes.

### Option B — Le tapis texturé solidaire du plateau *(aucun code)* ⭐

Une astuce qui rend le plateau tournant **licite** aux yeux du modèle : poser
l'objet sur un **support texturé qui tourne avec lui** (tapis à motif, journal,
damier imprimé).

L'ensemble « objet + tapis » devient alors un solide rigide, et sa rotation
relative à la caméra est **exactement équivalente** à une caméra qui orbite
autour d'une scène immobile. L'hypothèse du modèle est respectée, et le tapis
fournit en prime la texture partagée qui manquait.

✅ Coût nul, aucune ligne de code, testable dans l'heure.
✅ Conserve le plateau tournant, donc le studio existant.
❌ Le tapis apparaît dans le nuage — à masquer ou détourer ensuite.
❌ Ne règle pas à lui seul les pas de 90°.

### Option C — Fournir les poses au lieu de les estimer ⭐⭐

`MapAnything.infer()` accepte des **entrées géométriques optionnelles** par vue :

```python
'intrinsics':   (B, 3, 3)      # matrice de calibration
'camera_poses': (B, 4, 4)      # ou (quaternions, translations)
'depth_z':      (B, H, W, 1)
```

Sur un plateau tournant, **les poses sont connues d'avance** : c'est la
définition même du dispositif. Quatre vues à 90°, huit à 45°, douze à 30°, à
élévation et distance fixes — ce sont des paramètres du studio, pas une
inconnue à estimer.

Le plugin proposerait donc un **gabarit de prise de vue** :

| Réglage | Exemple |
|---|---|
| Nombre de vues | 4, 8, 12, 16 |
| Pas angulaire | déduit, ou saisi |
| Élévation caméra | 0° (niveau), 15°, 30° |
| Ordre des vues | horaire / antihoraire |
| Vues nommées | face, profil D, dos, profil G, 3/4 avant D… |

Le modèle ne fait alors plus que ce qu'il sait très bien faire : **estimer la
profondeur**. L'estimation de pose, seule étape en échec, disparaît.

✅ Traite la cause, pas le symptôme.
✅ **Résultats reproductibles** d'un produit à l'autre — décisif en catalogue.
✅ Accepte les combinaisons libres (3/4 avant, profil, dos…) dès lors que
l'angle de chaque vue est déclaré.
❌ Impose un protocole de prise de vue rigoureux et documenté.
❌ Une erreur de saisie d'angle se traduit directement en géométrie fausse.

### Option D — Détourage et coque visuelle *(complément)*

Le fond blanc, handicap pour la pose, est un **atout** pour la silhouette : le
détourage est trivial et fiable.

- Il supprime les traînées blanches du nuage.
- Combiné aux poses connues (option C), les silhouettes donnent une **coque
  visuelle** (*visual hull*) par intersection des cônes de vue : un volume
  d'initialisation propre, obtenu sans apprentissage, entièrement déterministe.

✅ Déterministe, rapide, sans modèle.
✅ Excellent nuage d'initialisation pour l'entraînement LichtFeld.
❌ Une coque visuelle ignore les concavités (l'assise creuse, l'espace sous le
piètement).
❌ Ne remplace pas la profondeur : c'est un complément.

### Option E — Changer de famille : modèle objet-centré

TripoSplat (1 image) ou TRELLIS (multi-images), tous deux MIT.

**Ces modèles n'estiment aucune pose** : ils travaillent dans un repère
canonique de l'objet. Un produit détouré sur fond blanc est précisément leur
domaine d'entraînement — l'inverse exact de MapAnything.

C'était l'intuition de départ du projet. Elle se révèle **juste pour ce type
d'images**, là où mon analyse initiale l'avait écartée parce que le besoin
annoncé était « quelques photos » et que TripoSplat n'en prend qu'une.

✅ Domaine d'entraînement exactement adapté au produit détouré.
✅ Aucun problème de pose, par construction.
✅ Objet complet, sans trou.
❌ **Génératif** : les faces non vues sont inventées. Sur un livrable client,
c'est un risque à assumer explicitement.
❌ Échelle non métrique, repère arbitraire.
❌ TRELLIS : ~16 Go de VRAM recommandés, au-delà des 8 Go disponibles.

### Option F — Recalage par rendu *(hors budget)*

Reconstruire grossièrement, puis retrouver la pose de chaque photo en
minimisant l'écart entre rendu et image. Robuste et générique, mais c'est un
sujet de recherche à part entière. **À écarter.**

---

## 4. Lecture croisée

| Option | Code | Coût | Traite la cause | Fidélité | Adapté au studio existant |
|---|---|---|---|---|---|
| A — protocole caméra mobile | non | prise de vue à refaire | ✅ | ✅ | ❌ |
| B — tapis texturé solidaire | non | quasi nul | ✅ | ✅ | ✅ |
| C — poses déclarées | oui | moyen | ✅ | ✅ | ✅ |
| D — détourage / coque visuelle | oui | faible | partiel | ✅ | ✅ |
| E — modèle objet-centré | oui | moyen | contourne | ⚠️ génératif | ✅ |
| F — recalage par rendu | oui | élevé | ✅ | ✅ | ✅ |

---

## 5. Recommandation

**Court terme, aujourd'hui, sans code : l'option B.** Un tapis texturé posé sous
l'objet et tournant avec lui rend le plateau tournant compatible avec le modèle.
C'est une expérience d'une heure qui vaut toutes les analyses : si les caméras
se répartissent, la cause est confirmée et l'option C devient un simple
raffinement.

**Moyen terme : l'option C**, complétée par D. Les poses déclarées suppriment
l'unique étape en échec, et le détourage nettoie le nuage. C'est le vrai
produit : un mode « studio » où l'opérateur déclare son dispositif au lieu de
demander à un modèle de le deviner.

**En parallèle : l'option E comme second moteur.** L'architecture à moteurs
interchangeables est faite pour ça. Un mode « objet » servirait les cas où la
prise de vue ne peut pas être maîtrisée, en assumant sa nature générative.

**À ne pas faire** : accumuler les vues. Passer de 4 à 12 photos sur plateau
tournant à fond blanc ne changera rien — la question posée au modèle reste
mal posée.
