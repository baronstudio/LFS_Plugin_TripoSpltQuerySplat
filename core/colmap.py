"""Ecriture d'une reconstruction au format COLMAP, sans dependance native.

Pourquoi ce module existe : l'exportateur de MapAnything s'appuie sur
`pycolmap` et `open3d`. Sur Windows / Python 3.12, `pycolmap` n'existe qu'en
version 3.10.0 et sa roue echoue a l'import (« DLL load failed while importing
pycolmap »). Or aucun algorithme de COLMAP n'est utilise : il ne s'agit que de
**serialiser** des cameras, des poses et un nuage de points.

Ce module remplace donc les deux dependances par environ 200 lignes de numpy et
de `struct`. Il retire du meme coup ~450 Mo d'installation et les deux seuls
composants natifs fragiles de la chaine.

Format binaire COLMAP, tel que lu par LichtFeld Studio et par la chaine 3DGS de
reference. Les entiers sont en petit-boutiste.
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

#: Identifiant du modele de camera PINHOLE dans COLMAP : fx, fy, cx, cy.
_PINHOLE_MODEL_ID = 1


# --------------------------------------------------------------------- geometrie


def invert_pose(cam2world: np.ndarray) -> np.ndarray:
    """Passe d'une pose camera->monde a monde->camera, attendue par COLMAP.

    Pour une transformation rigide, l'inverse est analytique :
    `R^-1 = R^T` et `t' = -R^T @ t`. Aucune inversion numerique n'est requise.
    """
    rotation = cam2world[:3, :3]
    translation = cam2world[:3, 3]
    inverse = np.empty((3, 4), dtype=np.float64)
    inverse[:3, :3] = rotation.T
    inverse[:3, 3] = -rotation.T @ translation
    return inverse


def rotmat_to_quat(rotation: np.ndarray) -> tuple[float, float, float, float]:
    """Matrice de rotation -> quaternion (qw, qx, qy, qz), convention COLMAP.

    Methode de Shepperd : on choisit la branche associee au plus grand terme
    diagonal, ce qui evite la division par une valeur proche de zero dont
    souffre la formule directe quand la trace est negative.
    """
    m = np.asarray(rotation, dtype=np.float64)
    trace = m[0, 0] + m[1, 1] + m[2, 2]

    if trace > 0.0:
        s = np.sqrt(trace + 1.0) * 2.0
        qw = 0.25 * s
        qx = (m[2, 1] - m[1, 2]) / s
        qy = (m[0, 2] - m[2, 0]) / s
        qz = (m[1, 0] - m[0, 1]) / s
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2.0
        qw = (m[2, 1] - m[1, 2]) / s
        qx = 0.25 * s
        qy = (m[0, 1] + m[1, 0]) / s
        qz = (m[0, 2] + m[2, 0]) / s
    elif m[1, 1] > m[2, 2]:
        s = np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2.0
        qw = (m[0, 2] - m[2, 0]) / s
        qx = (m[0, 1] + m[1, 0]) / s
        qy = 0.25 * s
        qz = (m[1, 2] + m[2, 1]) / s
    else:
        s = np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2.0
        qw = (m[1, 0] - m[0, 1]) / s
        qx = (m[0, 2] + m[2, 0]) / s
        qy = (m[1, 2] + m[2, 1]) / s
        qz = 0.25 * s

    quat = np.array([qw, qx, qy, qz], dtype=np.float64)
    quat /= np.linalg.norm(quat)
    # COLMAP attend un quaternion unitaire ; on fixe le signe pour que deux
    # rotations identiques donnent toujours la meme ecriture.
    if quat[0] < 0:
        quat = -quat
    return tuple(float(value) for value in quat)


def voxel_downsample(
    points: np.ndarray,
    colors: np.ndarray,
    voxel_fraction: float = 0.01,
    voxel_size: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Sous-echantillonne un nuage par grille de voxels.

    Sans `voxel_size` explicite, la taille est deduite de l'etendue de la scene
    mesuree par l'ecart interquartile : c'est robuste aux points aberrants, que
    la boite englobante brute laisserait dominer l'echelle.

    Chaque voxel occupe rend la moyenne des points et des couleurs qu'il
    contient.
    """
    points = np.asarray(points, dtype=np.float64)
    colors = np.asarray(colors)
    if points.size == 0:
        return points, colors

    if voxel_size is None:
        q25, q75 = np.percentile(points, (25, 75), axis=0)
        iqr_extent = float((q75 - q25).max())
        full_extent = float((points.max(axis=0) - points.min(axis=0)).max())
        # L'ecart interquartile ne couvre que la moitie des points : on le
        # double pour approcher l'etendue utile de la scene.
        scene_extent = iqr_extent * 2 if iqr_extent > 0 else full_extent
        voxel_size = scene_extent * voxel_fraction
    if voxel_size <= 0:
        voxel_size = 0.01  # Repli : scene degeneree (points confondus).

    grid = np.floor(points / voxel_size).astype(np.int64)
    _, inverse, counts = np.unique(grid, axis=0, return_inverse=True, return_counts=True)
    inverse = inverse.ravel()
    n_voxels = counts.size

    def _mean_per_voxel(values: np.ndarray) -> np.ndarray:
        sums = np.stack(
            [
                np.bincount(inverse, weights=values[:, axis], minlength=n_voxels)
                for axis in range(values.shape[1])
            ],
            axis=1,
        )
        return sums / counts[:, None]

    merged_points = _mean_per_voxel(points)
    merged_colors = _mean_per_voxel(colors.astype(np.float64))
    return merged_points, np.clip(np.round(merged_colors), 0, 255).astype(np.uint8)


# ------------------------------------------------------------------ ecriture


def _write(handle, fmt: str, *values) -> None:
    handle.write(struct.pack("<" + fmt, *values))


def write_cameras_bin(path: Path, intrinsics: np.ndarray, width: int, height: int) -> None:
    """Une camera PINHOLE par vue : les intrinseques sont estimees par vue."""
    with path.open("wb") as handle:
        _write(handle, "Q", len(intrinsics))
        for index, matrix in enumerate(intrinsics):
            _write(handle, "iiQQ", index + 1, _PINHOLE_MODEL_ID, width, height)
            _write(
                handle,
                "dddd",
                float(matrix[0, 0]),
                float(matrix[1, 1]),
                float(matrix[0, 2]),
                float(matrix[1, 2]),
            )


def write_images_bin(path: Path, extrinsics: np.ndarray, names: list[str]) -> None:
    """Poses monde->camera. Aucune observation 2D n'est ecrite.

    MapAnything propose lui-meme cette configuration (`skip_point2d`) : les
    chaines 3DGS n'utilisent le nuage que pour l'initialisation, jamais les
    pistes d'observations.
    """
    with path.open("wb") as handle:
        _write(handle, "Q", len(extrinsics))
        for index, (pose, name) in enumerate(zip(extrinsics, names, strict=True)):
            qw, qx, qy, qz = rotmat_to_quat(pose[:3, :3])
            _write(handle, "I", index + 1)
            _write(handle, "dddd", qw, qx, qy, qz)
            _write(handle, "ddd", *(float(value) for value in pose[:3, 3]))
            _write(handle, "I", index + 1)  # camera_id : une camera par image
            handle.write(name.encode("utf-8") + b"\x00")
            _write(handle, "Q", 0)  # nombre de points 2D


def write_points3d_bin(path: Path, points: np.ndarray, colors: np.ndarray) -> None:
    """Nuage d'initialisation, sans piste d'observation."""
    with path.open("wb") as handle:
        _write(handle, "Q", len(points))
        for index, (point, color) in enumerate(zip(points, colors, strict=True)):
            _write(handle, "Q", index + 1)
            _write(handle, "ddd", *(float(value) for value in point))
            _write(handle, "BBB", *(int(channel) for channel in color))
            _write(handle, "d", 0.0)  # erreur de reprojection : inconnue
            _write(handle, "Q", 0)  # longueur de piste


def write_ply(path: Path, points: np.ndarray, colors: np.ndarray) -> None:
    """Nuage colore en PLY binaire, utilise comme `init_path` par LichtFeld."""
    header = (
        "ply\n"
        "format binary_little_endian 1.0\n"
        f"element vertex {len(points)}\n"
        "property float x\nproperty float y\nproperty float z\n"
        "property uchar red\nproperty uchar green\nproperty uchar blue\n"
        "end_header\n"
    )
    dtype = [
        ("x", "<f4"),
        ("y", "<f4"),
        ("z", "<f4"),
        ("red", "u1"),
        ("green", "u1"),
        ("blue", "u1"),
    ]
    vertices = np.empty(len(points), dtype=dtype)
    vertices["x"], vertices["y"], vertices["z"] = points[:, 0], points[:, 1], points[:, 2]
    vertices["red"], vertices["green"], vertices["blue"] = colors[:, 0], colors[:, 1], colors[:, 2]
    with path.open("wb") as handle:
        handle.write(header.encode("ascii"))
        handle.write(vertices.tobytes())


def write_reconstruction(
    output_dir: Path,
    points: np.ndarray,
    colors: np.ndarray,
    intrinsics: np.ndarray,
    extrinsics: np.ndarray,
    image_names: list[str],
    width: int,
    height: int,
) -> Path:
    """Ecrit `sparse/0/*.bin` et `sparse/points.ply`. Rend le chemin du PLY.

    `sparse/0/` est la disposition attendue par LichtFeld Studio et par COLMAP.
    """
    sparse = output_dir / "sparse"
    model_dir = sparse / "0"
    model_dir.mkdir(parents=True, exist_ok=True)

    write_cameras_bin(model_dir / "cameras.bin", intrinsics, width, height)
    write_images_bin(model_dir / "images.bin", extrinsics, image_names)
    write_points3d_bin(model_dir / "points3D.bin", points, colors)

    ply_path = sparse / "points.ply"
    write_ply(ply_path, points, colors)
    return ply_path
