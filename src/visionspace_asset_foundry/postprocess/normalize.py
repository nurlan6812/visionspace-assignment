from __future__ import annotations

from pathlib import Path

import numpy as np
import trimesh

from visionspace_asset_foundry.postprocess.inspect_mesh import inspect_mesh
from visionspace_asset_foundry.schemas import MeshMetrics


def _worldspace_scene(loaded: trimesh.Scene | trimesh.Trimesh) -> trimesh.Scene:
    if isinstance(loaded, trimesh.Trimesh):
        return trimesh.Scene(loaded.copy())
    meshes = [
        mesh.copy()
        for mesh in loaded.dump(concatenate=False)
        if isinstance(mesh, trimesh.Trimesh) and mesh.vertices.size
    ]
    if not meshes:
        raise ValueError("No mesh geometry found.")
    return trimesh.Scene(meshes)


def _scene_bounds(scene: trimesh.Scene) -> tuple[np.ndarray, np.ndarray]:
    minimum, maximum = scene.bounds
    return minimum, maximum


def normalize_glb(
    input_path: Path,
    output_path: Path,
    target_largest_dimension_m: float = 2.0,
    align_floor: bool = True,
) -> MeshMetrics:
    """Normalize scale and floor alignment for simulation preview.

    The operation is intentionally conservative: it does not alter topology, and it keeps
    source materials where trimesh can preserve them.
    """

    loaded = trimesh.load(input_path, force="scene")
    scene = _worldspace_scene(loaded)

    minimum, maximum = _scene_bounds(scene)
    extents = np.maximum(maximum - minimum, 0)
    largest = float(extents.max())
    if largest <= 0:
        raise ValueError("Cannot normalize mesh with zero largest dimension.")

    scale = target_largest_dimension_m / largest
    transform = np.eye(4)
    transform[:3, :3] *= scale
    scene.apply_transform(transform)

    minimum, _ = _scene_bounds(scene)
    if align_floor:
        translation = np.eye(4)
        translation[:3, 3] = [-minimum[0], -minimum[1], -minimum[2]]
        scene.apply_transform(translation)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    scene.export(output_path)
    return inspect_mesh(output_path)


def convert_to_glb(input_path: Path, output_path: Path) -> MeshMetrics:
    loaded = trimesh.load(input_path, force="scene")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    loaded.export(output_path)
    return inspect_mesh(output_path)
