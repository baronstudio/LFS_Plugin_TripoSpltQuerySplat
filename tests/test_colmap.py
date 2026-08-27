"""Ecriture COLMAP : verification par relecture independante.

Ce module remplace `pycolmap`. Faute de pouvoir l'exercer sur un GPU, il est
verifie par aller-retour : les fichiers produits sont relus par un lecteur
ecrit ici **a partir de la specification du format**, et non a partir du code
teste. Une erreur de format ne peut donc pas se compenser elle-meme.
"""

import struct
import tempfile
import unittest
from pathlib import Path

import numpy as np

from core import colmap

# --------------------------------------------------------------- lecteur temoin


def _read_cameras(path: Path) -> list[dict]:
    """Lecteur ecrit depuis la specification COLMAP (cameras.bin)."""
    with path.open("rb") as handle:
        (count,) = struct.unpack("<Q", handle.read(8))
        cameras = []
        for _ in range(count):
            camera_id, model_id, width, height = struct.unpack("<iiQQ", handle.read(24))
            params = struct.unpack("<dddd", handle.read(32))
            cameras.append(
                {
                    "id": camera_id,
                    "model_id": model_id,
                    "width": width,
                    "height": height,
                    "params": params,
                }
            )
        self_check = handle.read()
    assert self_check == b"", "octets residuels : le format ne colle pas"
    return cameras


def _read_images(path: Path) -> list[dict]:
    """Lecteur ecrit depuis la specification COLMAP (images.bin)."""
    with path.open("rb") as handle:
        (count,) = struct.unpack("<Q", handle.read(8))
        images = []
        for _ in range(count):
            (image_id,) = struct.unpack("<I", handle.read(4))
            quat = struct.unpack("<dddd", handle.read(32))
            translation = struct.unpack("<ddd", handle.read(24))
            (camera_id,) = struct.unpack("<I", handle.read(4))
            name = b""
            while (char := handle.read(1)) != b"\x00":
                name += char
            (num_points2d,) = struct.unpack("<Q", handle.read(8))
            handle.read(num_points2d * 24)
            images.append(
                {
                    "id": image_id,
                    "quat": quat,
                    "translation": translation,
                    "camera_id": camera_id,
                    "name": name.decode("utf-8"),
                    "num_points2d": num_points2d,
                }
            )
        assert handle.read() == b"", "octets residuels : le format ne colle pas"
    return images


def _read_points3d(path: Path) -> list[dict]:
    """Lecteur ecrit depuis la specification COLMAP (points3D.bin)."""
    with path.open("rb") as handle:
        (count,) = struct.unpack("<Q", handle.read(8))
        points = []
        for _ in range(count):
            (point_id,) = struct.unpack("<Q", handle.read(8))
            xyz = struct.unpack("<ddd", handle.read(24))
            rgb = struct.unpack("<BBB", handle.read(3))
            (error,) = struct.unpack("<d", handle.read(8))
            (track_length,) = struct.unpack("<Q", handle.read(8))
            handle.read(track_length * 8)
            points.append({"id": point_id, "xyz": xyz, "rgb": rgb, "error": error})
        assert handle.read() == b"", "octets residuels : le format ne colle pas"
    return points


def _quat_to_rotmat(quat) -> np.ndarray:
    """Quaternion (w, x, y, z) -> matrice de rotation, formule de reference."""
    w, x, y, z = quat
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def _random_rotations(count: int, seed: int = 7) -> np.ndarray:
    """Rotations aleatoires via decomposition QR, determinant force a +1."""
    rng = np.random.default_rng(seed)
    rotations = []
    for _ in range(count):
        q, r = np.linalg.qr(rng.normal(size=(3, 3)))
        q = q @ np.diag(np.sign(np.diag(r)))
        if np.linalg.det(q) < 0:
            q[:, 0] = -q[:, 0]
        rotations.append(q)
    return np.stack(rotations)


# ------------------------------------------------------------------- geometrie


class TestQuaternion(unittest.TestCase):
    def test_identite(self):
        self.assertEqual(colmap.rotmat_to_quat(np.eye(3)), (1.0, 0.0, 0.0, 0.0))

    def test_aller_retour_sur_rotations_aleatoires(self):
        """La conversion doit tenir sur les quatre branches de la methode."""
        for index, rotation in enumerate(_random_rotations(64)):
            with self.subTest(rotation=index):
                rebuilt = _quat_to_rotmat(colmap.rotmat_to_quat(rotation))
                np.testing.assert_allclose(rebuilt, rotation, atol=1e-9)

    def test_rotations_a_trace_negative(self):
        """Cas ou la formule directe diverge : 180 degres autour de chaque axe."""
        for axis in range(3):
            rotation = -np.eye(3)
            rotation[axis, axis] = 1.0
            with self.subTest(axis=axis):
                rebuilt = _quat_to_rotmat(colmap.rotmat_to_quat(rotation))
                np.testing.assert_allclose(rebuilt, rotation, atol=1e-9)

    def test_quaternion_unitaire(self):
        for rotation in _random_rotations(16):
            self.assertAlmostEqual(np.linalg.norm(colmap.rotmat_to_quat(rotation)), 1.0)


class TestInvertPose(unittest.TestCase):
    def test_compose_a_l_identite(self):
        for rotation in _random_rotations(16):
            cam2world = np.eye(4)
            cam2world[:3, :3] = rotation
            cam2world[:3, 3] = [1.5, -2.0, 3.25]
            world2cam = np.eye(4)
            world2cam[:3, :4] = colmap.invert_pose(cam2world)
            np.testing.assert_allclose(world2cam @ cam2world, np.eye(4), atol=1e-12)


class TestVoxelDownsample(unittest.TestCase):
    def test_fusionne_les_points_du_meme_voxel(self):
        points = np.array([[0.0, 0, 0], [0.1, 0, 0], [5.0, 5, 5]])
        colors = np.array([[10, 10, 10], [20, 20, 20], [30, 30, 30]], dtype=np.uint8)
        merged_points, merged_colors = colmap.voxel_downsample(points, colors, voxel_size=1.0)
        self.assertEqual(len(merged_points), 2)
        self.assertEqual(merged_colors.dtype, np.uint8)
        # Les deux premiers points fusionnent : couleur moyennee.
        self.assertIn(15, merged_colors[:, 0].tolist())

    def test_nuage_vide(self):
        empty = np.zeros((0, 3))
        points, colors = colmap.voxel_downsample(empty, empty)
        self.assertEqual(len(points), 0)

    def test_points_confondus_ne_divisent_pas_par_zero(self):
        points = np.ones((10, 3))
        colors = np.full((10, 3), 128, dtype=np.uint8)
        merged, _ = colmap.voxel_downsample(points, colors)
        self.assertEqual(len(merged), 1)

    def test_taille_de_voxel_adaptative_reduit_le_nuage(self):
        rng = np.random.default_rng(0)
        points = rng.normal(size=(5000, 3))
        colors = rng.integers(0, 256, size=(5000, 3)).astype(np.uint8)
        merged, _ = colmap.voxel_downsample(points, colors, voxel_fraction=0.05)
        self.assertLess(len(merged), len(points))
        self.assertGreater(len(merged), 0)


# ---------------------------------------------------------------- serialisation


class TestEcriture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

        self.rotations = _random_rotations(3)
        self.extrinsics = np.stack(
            [np.hstack([r, np.array([[1.0], [2.0], [3.0]])]) for r in self.rotations]
        )
        self.intrinsics = np.stack(
            [np.array([[500.0, 0, 256.0], [0, 510.0, 128.0], [0, 0, 1.0]])] * 3
        )
        self.points = np.array([[0.0, 1, 2], [3.0, 4, 5]])
        self.colors = np.array([[255, 0, 0], [0, 128, 64]], dtype=np.uint8)
        self.names = ["a.png", "b.png", "c.png"]

    def _write(self):
        return colmap.write_reconstruction(
            self.root,
            points=self.points,
            colors=self.colors,
            intrinsics=self.intrinsics,
            extrinsics=self.extrinsics,
            image_names=self.names,
            width=512,
            height=256,
        )

    def test_disposition_attendue_par_lichtfeld(self):
        ply = self._write()
        model = self.root / "sparse" / "0"
        for filename in ("cameras.bin", "images.bin", "points3D.bin"):
            self.assertTrue((model / filename).is_file(), filename)
        self.assertEqual(ply, self.root / "sparse" / "points.ply")
        self.assertTrue(ply.is_file())

    def test_cameras_relues(self):
        self._write()
        cameras = _read_cameras(self.root / "sparse" / "0" / "cameras.bin")
        self.assertEqual(len(cameras), 3)
        self.assertEqual(cameras[0]["model_id"], 1)  # PINHOLE
        self.assertEqual((cameras[0]["width"], cameras[0]["height"]), (512, 256))
        self.assertEqual(cameras[0]["params"], (500.0, 510.0, 256.0, 128.0))
        self.assertEqual([c["id"] for c in cameras], [1, 2, 3])

    def test_images_relues_et_poses_preservees(self):
        self._write()
        images = _read_images(self.root / "sparse" / "0" / "images.bin")
        self.assertEqual([i["name"] for i in images], self.names)
        self.assertEqual([i["camera_id"] for i in images], [1, 2, 3])
        for index, image in enumerate(images):
            with self.subTest(image=index):
                self.assertEqual(image["num_points2d"], 0)
                np.testing.assert_allclose(
                    _quat_to_rotmat(image["quat"]), self.rotations[index], atol=1e-9
                )
                np.testing.assert_allclose(image["translation"], (1.0, 2.0, 3.0))

    def test_points_relus(self):
        self._write()
        points = _read_points3d(self.root / "sparse" / "0" / "points3D.bin")
        self.assertEqual(len(points), 2)
        self.assertEqual([p["id"] for p in points], [1, 2])
        np.testing.assert_allclose(points[0]["xyz"], (0.0, 1.0, 2.0))
        self.assertEqual(points[1]["rgb"], (0, 128, 64))

    def test_noms_unicode(self):
        self.names = ["éclairage.png", "b.png", "c.png"]
        self._write()
        images = _read_images(self.root / "sparse" / "0" / "images.bin")
        self.assertEqual(images[0]["name"], "éclairage.png")

    def test_ply_binaire_relu(self):
        ply = self._write()
        raw = ply.read_bytes()
        header, _, body = raw.partition(b"end_header\n")
        self.assertIn(b"format binary_little_endian 1.0", header)
        self.assertIn(b"element vertex 2", header)
        # 2 sommets x (3 float32 + 3 uint8)
        self.assertEqual(len(body), 2 * (12 + 3))
        vertices = np.frombuffer(
            body,
            dtype=[
                ("x", "<f4"),
                ("y", "<f4"),
                ("z", "<f4"),
                ("r", "u1"),
                ("g", "u1"),
                ("b", "u1"),
            ],
        )
        np.testing.assert_allclose(vertices["x"], [0.0, 3.0])
        self.assertEqual(vertices["g"].tolist(), [0, 128])

    def test_nuage_vide_reste_lisible(self):
        self.points = np.zeros((0, 3))
        self.colors = np.zeros((0, 3), dtype=np.uint8)
        self._write()
        self.assertEqual(_read_points3d(self.root / "sparse" / "0" / "points3D.bin"), [])


if __name__ == "__main__":
    unittest.main()
