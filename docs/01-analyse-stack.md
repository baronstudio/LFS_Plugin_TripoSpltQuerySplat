# Analyse et challenge de la stack — Plugin LichtFeld Studio « photos → 3DGS »

| | |
|---|---|
| **Document** | `docs/01-analyse-stack.md` |
| **Version doc** | 1.0.0 |
| **Date** | 2026-08-26 |
| **Statut** | Aide à la décision — **la stack n'est pas encore figée** |
| **Public** | Technicien 3D / dev plugin |

---

## 1. Résumé exécutif

Le brief initial est : *« reproduire `lyehe/lichtfeld-querysplat-plugin` mais avec TripoSplat à la place de VGGT-Omega »*.

Trois constats remettent en cause ce brief tel quel :

1. **TripoSplat ne peut pas remplacer VGGT-Omega : ce ne sont pas des briques de même nature.**
   VGGT-Ω est un *backbone géométrique* interne (il sort caméras + profondeurs, pas un splat).
   TripoSplat est un *générateur terminal* (il sort directement le splat, sans notion de caméra).
   Substituer l'un à l'autre ne modifie pas le pipeline : cela le supprime.

2. **TripoSplat ne prend qu'UNE seule image.**
   Le concept annoncé — « à partir de quelques photos d'un sujet, lieu, objet » — n'est pas
   couvert par TripoSplat, qui est mono-vue et objet-centré (fond détouré, objet normalisé).
   Les « lieux » sont hors de son domaine d'entraînement.

3. **Le plugin existe déjà.**
   `lyehe/lichtfeld-triposplat-plugin` (MIT) fait exactement « 1 photo → TripoSplat → splat
   inséré dans la scène », et il est **référencé au registre officiel LichtFeld Studio**.
   Le refaire à l'identique produit zéro valeur.

**Conclusion : il faut choisir un axe de différenciation.** Les options sont détaillées en §5.
La recommandation de l'auteur du document est l'**Option C** (§6).

---

## 2. Qui fait quoi, réellement

| Brique | Entrée | Sortie | Rôle | Licence poids |
|---|---|---|---|---|
| **VGGT-Omega** (Meta FAIR) | N images | caméras + profondeurs + tokens | backbone géométrie | **FAIR Noncommercial** + accès HF à accepter |
| **QuerySplat** (inspatio) | N images d'une même scène | **3DGS** + caméras + profondeurs | tête 3DGS pose-free | code Apache-2.0, **mais s'appuie sur VGGT-Ω** |
| **TripoSplat** (VAST-AI / Tripo) | **1 image** | **3DGS** (jusqu'à 262 144 gaussiennes) | générateur objet | **MIT** (code + poids) |

Le pipeline du plugin QuerySplat est donc : `images → VGGT-Ω (géométrie) → QuerySplat (apparence + 3DGS) → scène`.

Le pipeline TripoSplat est : `1 image → détourage → TripoSplat → scène`. **Il n'y a rien à remplacer dedans.**

### 2.1 Nature du modèle : reconstruction ≠ génération

TripoSplat s'utilise avec `seed`, `steps`, `guidance_scale`, `shift` : ce sont les paramètres d'un
modèle **génératif de type flow matching**, pas d'un régresseur déterministe.

Conséquences opérationnelles, à assumer explicitement auprès des utilisateurs :

- **La face non vue est inventée.** Le dos d'un objet photographié de face est une hypothèse
  plausible du modèle, pas une mesure.
- **Non déterministe** : deux runs avec des seeds différentes donnent deux géométries différentes.
- **Pas d'échelle métrique, pas de repère monde.** L'objet sort normalisé ; toute mesure,
  tout alignement sur une scène existante est à refaire à la main (gizmo).
- **Domaine = objet isolé sur fond propre.** Une pièce, une façade, un paysage sortent du domaine.

C'est un excellent outil de *création d'asset* et de *preview*. Ce n'est pas un outil de
*relevé*. Vendre TripoSplat comme un remplaçant de RealityScan / photogrammétrie serait faux
et se retournera contre le projet dès la première recette client.

### 2.2 Le vrai gain (celui qui tient)

En revanche, le point de départ du brief reste juste et mesurable :

- **plus d'alignement** (COLMAP / RealityScan) → suppression de l'étape la plus lente et la plus
  fragile de la chaîne ;
- **plus besoin d'un jeu d'images à fort recouvrement ni d'une vidéo** ;
- **temps de traitement** : secondes/minutes au lieu de dizaines de minutes à heures.

Ce gain n'est pas propre à TripoSplat : **toute la famille feed-forward** (§4) l'apporte,
y compris pour les scènes et le multi-vues. C'est là qu'il y a de la place.

---

## 3. Points de challenge à trancher

| # | Question | Impact |
|---|---|---|
| Q1 | Cible = **objet/produit isolé** ou **scène/lieu** ? | Détermine à lui seul la famille de modèles |
| Q2 | **1 photo** ou **N photos** ? | TripoSplat = 1 ; QuerySplat/AnySplat/DA3 = N |
| Q3 | Usage **commercial** du résultat ? | Élimine VGGT-Ω, DA3-LARGE/GIANT, MapAnything non-apache |
| Q4 | Sortie = **asset final** ou **initialisation** d'un entraînement LichtFeld ? | Change toute l'architecture (§5, option C) |
| Q5 | Tout **local** ou API cloud acceptée ? | Tripo propose une API payante, plus qualitative mais non locale |

---

## 4. Panorama concurrentiel des modèles (état au 08/2026)

### 4.1 Familles

- **Génératifs mono-image objet** : TripoSplat, TRELLIS, Hunyuan3D, TripoSG.
  → 1 photo, objet, hallucination assumée, pas d'échelle.
- **Reconstruction géométrique multi-vues feed-forward** : VGGT / VGGT-Ω, MapAnything,
  Depth Anything 3, π³, Fast3R, CUT3R, DUSt3R/MASt3R.
  → N photos, caméras + nuage de points, **pas de splat** (sauf tête dédiée).
- **3DGS multi-vues feed-forward** : QuerySplat, AnySplat, DA3 (tête 3DGS), Splatt3R, NoPoSplat.
  → N photos, **splat + caméras**, pose-free. **C'est la famille qui correspond au concept annoncé.**

### 4.2 Tableau comparatif

| Modèle | Entrée | Sortie | Pose requise | Licence poids | Objet / Scène | Verdict pour ce projet |
|---|---|---|---|---|---|---|
| **TripoSplat** (VAST-AI) | 1 image | 3DGS | non | **MIT** | Objet | ✅ licence idéale, ❌ mono-image, ❌ déjà packagé |
| **QuerySplat** (inspatio) | N images | 3DGS + caméras | non | code Apache-2.0 / **backbone NC** | Scène + objet | ⚠️ qualité au top, licence bloquante |
| **VGGT-Omega** (Meta) | N images | caméras + depth | non | **FAIR NC** + gated HF | Scène | ❌ non commercial + friction install (`hf auth login`) |
| **AnySplat** (InternRobotics) | N images non calibrées | **3DGS + caméras** | non | **MIT** | Scène + objet | ✅ **meilleur compromis licence / concept** |
| **Depth Anything 3** (ByteDance) | N images | depth/rays (+ tête 3DGS) | opt. | **Apache** (S/B) — **CC-BY-NC** (L/G) | Scène | ✅ si on reste sur SMALL/BASE |
| **MapAnything** (Meta) | N images (+ priors) | géométrie **métrique** + caméras | non | **Apache** (`map-anything-apache`) | Scène | ✅ seul à donner l'**échelle métrique**, mais pas de splat |
| **HunyuanWorld-Mirror** (Tencent) | images/vidéo/COLMAP | 3D | non | licence communautaire Tencent à auditer | Scène | ⚠️ déjà packagé par lyehe |
| **TRELLIS** (Microsoft) | 1 image / texte | mesh **ou** 3DGS **ou** RF | non | MIT | Objet | ⚠️ concurrent direct de TripoSplat |
| **Hunyuan3D 2.x** (`2mv` = multi-vues) | 1 ou N images | mesh + texture | non | licence communautaire (restrictions territoriales / MAU) | Objet | ⚠️ sortie mesh, pas splat |
| **API Tripo (cloud)** | 1..N images | mesh / splat | non | service payant | Objet | ❌ hors périmètre « local » |

> ⚠️ Les licences des modèles Tencent (Hunyuan) comportent des restrictions d'usage
> (territoires, seuils d'utilisateurs). À auditer avant toute intégration commerciale.

### 4.3 Le point de douleur réel du plugin de référence

Le plugin `lichtfeld-querysplat-plugin` impose à l'utilisateur :

- d'aller **accepter les conditions FAIR** sur Hugging Face ;
- de faire un `hf auth login` en ligne de commande ;
- de télécharger **~9,1 Go** de poids ;
- et de **renoncer à tout usage commercial** du résultat (licence non-commerciale des poids).

**C'est là que se situe la valeur ajoutée disponible :** un plugin multi-photos, sans compte,
sans gate, sous licence 100 % permissive, ça n'existe pas encore au registre LichtFeld.

---

## 5. Options de stack

### Option A — TripoSplat seul (le brief littéral)
`1 photo → détourage → TripoSplat → splat dans la scène`

- ✅ Licence MIT de bout en bout, ~3,8 Go de poids, pas de compte HF, install simple.
- ✅ Le plus simple à maintenir (KISS maximal).
- ❌ **Doublon strict** d'un plugin officiel existant.
- ❌ Mono-image : ne répond pas au concept « quelques photos ».
- ❌ Objets uniquement.

### Option B — Multi-photos licence propre
`N photos → AnySplat (MIT) → splat + caméras → scène`

- ✅ Répond **exactement** au concept annoncé (quelques photos, aucun alignement préalable).
- ✅ MIT de bout en bout, aucun gate, usage commercial possible.
- ✅ Couvre objets **et** scènes/lieux.
- ✅ Aucun plugin LichtFeld équivalent à ce jour.
- ❌ Qualité en retrait par rapport à QuerySplat (modèle plus ancien, résolution d'entrée 448 px).
- ⚠️ Empreinte VRAM à qualifier sur banc.

### Option C — Multi-photos + raffinement LichtFeld  ← **recommandée**
`N photos → AnySplat → splat + caméras → export dataset COLMAP → entraînement LichtFeld sur les vraies photos`

Le modèle feed-forward ne sert **pas** de rendu final : il sert à produire ce que COLMAP /
RealityScan produisaient (poses + nuage d'initialisation), et l'optimiseur natif de LichtFeld
Studio fait le reste **à partir des vraies photos**.

- ✅ **Supprime réellement l'étape d'alignement** — la promesse d'origine, tenue.
- ✅ **Qualité finale = celle d'un vrai 3DGS optimisé** (plus d'hallucination : les pixels
  viennent des photos), là où le feed-forward seul plafonne.
- ✅ Utilise le cœur de métier de LichtFeld au lieu de le contourner → plugin *complémentaire*
  de l'app, pas concurrent.
- ✅ Faisable avec l'API publique : `lf.load_file(path, is_dataset=True, init_path=...)`,
  `lf.start_training()`, `lf.export_scene(format=COLMAP, ...)`.
- ❌ Plus de code que l'option A/B (deux modes : *instantané* et *raffiné*).
- ⚠️ Nécessite quand même un minimum de recouvrement entre photos pour que le raffinement
  apporte quelque chose. À doser : 6–20 photos.

### Option D — QuerySplat avec backbone permissif
`N photos → DA3-BASE / MapAnything-apache → QuerySplat → splat`

- ✅ Meilleure qualité théorique du panorama.
- ❌ **Non supporté en amont** : QuerySplat est entraîné conjointement à VGGT-Ω, changer de
  backbone impose un ré-entraînement. Hors budget. **À écarter.**

### Option E — TripoSplat en module optionnel
Garder TripoSplat comme *mode objet* (1 photo) à côté du mode multi-photos.

- ✅ Conserve l'intention initiale, coût marginal faible (le code d'appel TripoSplat est
  ~2 000 lignes, quasi sans dépendances).
- ❌ Double la surface de test et le volume de poids à télécharger.
- → À traiter comme un **extra de v0.3+**, pas comme le cœur de la v0.1.

---

## 6. Recommandation

**Option C, livrée par paliers, avec l'option E en extension ultérieure.**

| Version | Contenu | Objectif |
|---|---|---|
| `v0.1.0` | Squelette plugin + panneau + import de N photos + AnySplat → splat inséré dans la scène | Prouver la chaîne bout en bout |
| `v0.2.0` | Export dataset COLMAP (poses estimées) + `init_path` + lancement de l'entraînement natif | Tenir la promesse « zéro alignement, qualité 3DGS » |
| `v0.3.0` | Mode objet TripoSplat (1 photo) + détourage | Couvrir le cas produit/objet |
| `v0.4.0` | Réglages avancés, presets, export `.ply`/`.splat`, télémétrie de perf | Industrialisation |

**Nom proposé pour éviter toute confusion avec le plugin de lyehe** :
`lfs-fewshot-splat` (ou tout autre nom validé par le porteur du projet).

Si la cible réelle est **exclusivement l'objet produit isolé**, alors l'Option A/E est la bonne
et le projet doit se différencier autrement (batch, presets métier, post-traitement, export),
car le plugin de référence est déjà disponible et gratuit.

---

## 7. Points de vigilance licence (à relire avant toute mise en prod)

- **Ne jamais redistribuer les poids** : téléchargement à la demande depuis Hugging Face.
- **VGGT-Omega et QuerySplat → usage non commercial.** Interdit pour un livrable client payant.
- **Depth Anything 3** : uniquement `DA3-SMALL` / `DA3-BASE` (Apache) pour un usage commercial.
- **MapAnything** : uniquement le checkpoint `facebook/map-anything-apache`.
- **AnySplat, TripoSplat, TRELLIS** : MIT — pas de contrainte.
- Le code du plugin lui-même reste **MIT** (cf. `LICENSE` du dépôt).

---

## 8. Sources

- TripoSplat — <https://github.com/VAST-AI-Research/TripoSplat>
- TripoSplat (poids) — <https://huggingface.co/VAST-AI/TripoSplat>
- Plugin TripoSplat existant — <https://github.com/lyehe/lichtfeld-triposplat-plugin>
- Plugin QuerySplat de référence — <https://github.com/lyehe/lichtfeld-querysplat-plugin>
- Plugin VGGT-Omega — <https://github.com/lyehe/lichtfeld-vggt-omega>
- QuerySplat — <https://github.com/inspatio/querysplat> · <https://arxiv.org/abs/2608.01186>
- AnySplat — <https://github.com/InternRobotics/AnySplat> · <https://arxiv.org/abs/2505.23716>
- MapAnything — <https://github.com/facebookresearch/map-anything> · <https://arxiv.org/abs/2509.13414>
- Depth Anything 3 — <https://github.com/ByteDance-Seed/Depth-Anything-3> · <https://arxiv.org/abs/2511.10647>
- LichtFeld Studio — <https://github.com/MrNeRF/LichtFeld-Studio>
- Système de plugins — <https://github.com/MrNeRF/LichtFeld-Studio/blob/master/docs/plugin-system.md>
- API Python (stubs) — `src/python/stubs/lichtfeld/__init__.pyi` du dépôt LichtFeld Studio
- Doc officielle plugins — <https://lichtfeld.io/docs/>
