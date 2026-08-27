"""Moteur multi-vues : MapAnything -> dataset COLMAP.

MapAnything estime en une passe les poses de camera, les profondeurs et un
nuage 3D metrique a partir de photos non calibrees. C'est ce qui remplace
COLMAP / RealityScan dans la chaine : l'etape d'alignement disparait.

Le splat final n'est PAS produit ici : il est entraine par LichtFeld Studio a
partir des vraies photos, avec ce dataset en entree. C'est ce qui garantit la
fidelite au sujet (aucune texture inventee).

L'export COLMAP n'utilise pas celui de MapAnything : il s'appuie sur
`pycolmap` et `open3d`, deux dependances natives. Sur Windows / Python 3.12,
`pycolmap` n'existe qu'en 3.10.0 et sa roue echoue a l'import (« DLL load
failed »). Comme aucun algorithme de COLMAP n'est necessaire -- il ne s'agit
que de serialiser cameras, poses et nuage --, l'ecriture est faite par
`core.colmap`. Voir docs/05-depannage.md.

Licence : code Apache 2.0, poids `facebook/map-anything-apache` Apache 2.0.
Le checkpoint par defaut `facebook/map-anything` est CC-BY-NC : il n'est
volontairement PAS propose ici, le plugin visant un usage commercial.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

from .base import (
    KIND_DATASET,
    BackendInfo,
    ProgressFn,
    RunResult,
    missing_modules,
    raise_if_cancelled,
    require_modules,
    unique_names,
)

#: Modules dont l'absence empeche toute generation.
REQUIRED_MODULES = ("torch", "mapanything", "numpy", "PIL")

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

        Voir `missing_modules` : importer torch ici figerait l'interface. La
        contrepartie est qu'un module present mais defaillant (DLL manquante,
        extension native incompatible) passe ce controle ; il est rattrape par
        `require_modules()` au debut de `run()`.
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
        report(0.02, "Verification des dependances")
        raise_if_cancelled(cancel)
        # Avant tout travail couteux : un module qui ne s'importe pas doit se
        # signaler en quelques secondes, pas apres plusieurs minutes d'inference.
        require_modules(REQUIRED_MODULES)

        report(0.05, "Preparation")
        import torch
        from mapanything.models import MapAnything
        from mapanything.utils.image import load_images
        from mapanything.utils.misc import seed_everything

        from .. import colmap

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

            report(0.78, "Assemblage du nuage et des poses")
            raise_if_cancelled(cancel)
            # Tout est rapatrie sur le CPU ici : la suite n'a plus besoin du
            # GPU, et `outputs` peut etre libere des la sortie du bloc.
            points, colors, intrinsics, extrinsics, frames, (width, height) = _collect(outputs)
            result.add(f"{len(points)} points avant sous-echantillonnage.")
        finally:
            # La VRAM doit etre rendue avant que LichtFeld ne lance l'entrainement.
            del model, outputs
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        report(0.85, "Sous-echantillonnage du nuage")
        raise_if_cancelled(cancel)
        points, colors = colmap.voxel_downsample(
            points,
            colors,
            voxel_fraction=float(params.get("voxel_fraction", 0.01)),
            voxel_size=params.get("voxel_size"),
        )
        result.add(f"{len(points)} points conserves.")

        report(0.92, "Ecriture du dataset COLMAP")
        work_dir.mkdir(parents=True, exist_ok=True)
        init_ply = colmap.write_reconstruction(
            work_dir,
            points=points,
            colors=colors,
            intrinsics=intrinsics,
            extrinsics=extrinsics,
            image_names=names,
            width=width,
            height=height,
        )

        report(0.96, "Enregistrement des images")
        _save_images(frames, names, work_dir / "images")

        result.dataset_dir = work_dir
        result.init_ply = init_ply
        result.add(f"Dataset COLMAP pret : {work_dir}")
        report(1.0, "Termine")
        return result


def _collect(outputs):
    """Extrait de la sortie du modele ce dont COLMAP a besoin.

    Chaque vue fournit un nuage `pts3d` en coordonnees monde, un masque de
    validite, une profondeur camera, l'image denormalisee, les intrinseques et
    la pose camera->monde. On ne garde que les pixels a la fois valides et de
    profondeur positive.
    """
    import numpy as np

    from .. import colmap

    all_points: list = []
    all_colors: list = []
    intrinsics: list = []
    extrinsics: list = []
    frames: list = []

    for pred in outputs:
        points = pred["pts3d"][0].cpu().numpy()
        mask = pred["mask"][0].squeeze(-1).cpu().numpy().astype(bool)
        depth_z = pred["depth_z"][0].squeeze(-1).cpu().numpy()
        keep = mask & (depth_z > 0)

        image = (pred["img_no_norm"][0].cpu().numpy() * 255).astype(np.uint8)
        frames.append(image)
        all_points.append(points[keep])
        all_colors.append(image[keep])

        intrinsics.append(pred["intrinsics"][0].cpu().numpy())
        # COLMAP attend des poses monde->camera.
        extrinsics.append(colmap.invert_pose(pred["camera_poses"][0].cpu().numpy()))

    height, width = frames[0].shape[:2]
    return (
        np.concatenate(all_points, axis=0),
        np.concatenate(all_colors, axis=0),
        np.stack(intrinsics),
        np.stack(extrinsics),
        frames,
        (int(width), int(height)),
    )


def _save_images(frames: list, names: list[str], images_dir: Path) -> None:
    """Ecrit les images telles que le modele les a vues.

    Ce sont ces images-la, et non les originales, qui correspondent aux
    intrinseques estimees et a la resolution du modele : l'entrainement doit
    s'appuyer sur elles.
    """
    from PIL import Image

    images_dir.mkdir(parents=True, exist_ok=True)
    for array, name in zip(frames, names, strict=True):
        Image.fromarray(array).save(images_dir / name)
