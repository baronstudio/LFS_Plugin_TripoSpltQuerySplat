"""Moteur multi-vues : MapAnything -> dataset COLMAP.

MapAnything estime en une passe les poses de camera, les profondeurs et un
nuage 3D metrique a partir de photos non calibrees. C'est ce qui remplace
COLMAP / RealityScan dans la chaine : l'etape d'alignement disparait.

Le splat final n'est PAS produit ici : il est entraine par LichtFeld Studio a
partir des vraies photos, avec ce dataset en entree. C'est ce qui garantit la
fidelite au sujet (aucune texture inventee).

Licence : code Apache 2.0, poids `facebook/map-anything-apache` Apache 2.0.
Le checkpoint par defaut `facebook/map-anything` est CC-BY-NC : il n'est
volontairement PAS propose ici, le plugin visant un usage commercial.
"""

from __future__ import annotations

import os
import shutil
import threading
from pathlib import Path

from .base import (
    KIND_DATASET,
    BackendInfo,
    ProgressFn,
    RunResult,
    missing_modules,
    raise_if_cancelled,
    unique_names,
)

#: Modules dont l'absence empeche toute generation.
REQUIRED_MODULES = ("torch", "mapanything", "pycolmap", "open3d")

#: Seul checkpoint retenu : c'est le seul sous licence permissive.
MODEL_ID = "facebook/map-anything-apache"

INFO = BackendInfo(
    name="mapanything",
    label="MapAnything (multi-vues -> dataset)",
    kind=KIND_DATASET,
    min_images=2,
    max_images=200,
    model_id=MODEL_ID,
    license="Apache 2.0 (code et poids)",
    commercial_ok=True,
    summary=(
        "Estime poses et geometrie metrique a partir de plusieurs photos non "
        "calibrees, puis produit un dataset COLMAP que LichtFeld entraine."
    ),
)


class MapAnythingBackend:
    """Implementation du contrat `Backend` pour MapAnything."""

    info = INFO

    def check(self) -> list[str]:
        """Verification instantanee : presence des modules, sans les importer.

        Voir `missing_modules` : importer torch ici figerait l'interface.
        """
        missing = missing_modules(REQUIRED_MODULES)
        if missing:
            return [
                "Module(s) introuvable(s) dans l'environnement du plugin : "
                + ", ".join(missing)
                + ". Voir docs/03-installation.md."
            ]
        return []

    def run(
        self,
        images: list[Path],
        work_dir: Path,
        params: dict,
        report: ProgressFn,
        cancel: threading.Event,
    ) -> RunResult:
        # Doit etre pose avant le premier import de torch pour avoir un effet.
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

        result = RunResult()
        report(0.02, "Preparation")
        raise_if_cancelled(cancel)

        import torch
        from mapanything.models import MapAnything
        from mapanything.utils.colmap_export import export_predictions_to_colmap
        from mapanything.utils.image import load_images
        from mapanything.utils.misc import seed_everything

        # Verification authentique de CUDA : elle exige torch, donc elle a lieu
        # ici et non dans `check()`, qui doit rester instantane.
        if not torch.cuda.is_available():
            raise RuntimeError(
                "Aucun GPU CUDA disponible. torch "
                f"{torch.__version__} rapporte cuda={torch.version.cuda}. "
                "Voir docs/05-depannage.md."
            )

        seed_everything(int(params.get("seed", 42)))
        device = "cuda"

        report(0.10, f"Chargement du modele ({MODEL_ID})")
        raise_if_cancelled(cancel)
        model = MapAnything.from_pretrained(MODEL_ID).to(device)
        model.eval()
        result.add(f"Modele charge sur {device}.")

        try:
            report(0.25, f"Lecture de {len(images)} photo(s)")
            raise_if_cancelled(cancel)
            names = unique_names(images)
            views = load_images([str(path) for path in images])
            result.add(f"{len(views)} vue(s) preparee(s).")

            report(0.35, "Inference : poses, profondeurs, nuage 3D")
            raise_if_cancelled(cancel)
            with torch.no_grad():
                outputs = model.infer(
                    views,
                    memory_efficient_inference=True,
                    minibatch_size=1,
                    use_amp=True,
                    amp_dtype="bf16",
                    apply_mask=True,
                    mask_edges=True,
                )
            result.add("Inference terminee.")

            report(0.80, "Export du dataset COLMAP")
            raise_if_cancelled(cancel)
            work_dir.mkdir(parents=True, exist_ok=True)
            export_predictions_to_colmap(
                outputs=outputs,
                processed_views=views,
                image_names=names,
                output_dir=str(work_dir),
                voxel_fraction=float(params.get("voxel_fraction", 0.01)),
                voxel_size=params.get("voxel_size"),
                data_norm_type=model.encoder.data_norm_type,
                save_ply=True,
                save_images=True,
                skip_point2d=bool(params.get("skip_point2d", False)),
            )
        finally:
            # La VRAM doit etre rendue avant que LichtFeld ne lance l'entrainement.
            del model
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        report(0.95, "Mise en forme du dataset")
        init_ply = _arrange_colmap_layout(work_dir)
        result.dataset_dir = work_dir
        result.init_ply = init_ply
        result.add(f"Dataset COLMAP pret : {work_dir}")
        report(1.0, "Termine")
        return result


def _arrange_colmap_layout(work_dir: Path) -> Path | None:
    """Aligne la sortie MapAnything sur la convention attendue par LichtFeld.

    MapAnything ecrit `sparse/*.bin`, LichtFeld Studio (comme COLMAP) attend
    `sparse/0/*.bin`. On duplique les trois fichiers plutot que de les deplacer :
    le dossier reste utilisable par les outils qui suivent l'autre convention.
    """
    sparse = work_dir / "sparse"
    if not sparse.is_dir():
        return None

    model_dir = sparse / "0"
    model_dir.mkdir(exist_ok=True)
    for filename in ("cameras.bin", "images.bin", "points3D.bin"):
        source = sparse / filename
        if source.is_file():
            shutil.copy2(source, model_dir / filename)

    points = sparse / "points.ply"
    return points if points.is_file() else None
