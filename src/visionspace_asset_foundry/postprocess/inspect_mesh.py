from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import trimesh

from visionspace_asset_foundry.schemas import Dimensions, MeshMetrics


def _iter_meshes(loaded: trimesh.Scene | trimesh.Trimesh) -> Iterable[trimesh.Trimesh]:
    if isinstance(loaded, trimesh.Trimesh):
        yield loaded
        return
    for mesh in loaded.dump(concatenate=False):
        if isinstance(mesh, trimesh.Trimesh):
            yield mesh


def inspect_mesh(path: Path) -> MeshMetrics:
    warnings: list[str] = []
    if not path.exists():
        return MeshMetrics(warnings=[f"File not found: {path}"])

    try:
        loaded = trimesh.load(path, force="scene")
    except Exception as exc:
        return MeshMetrics(file_size_bytes=path.stat().st_size, warnings=[f"Failed to load mesh: {exc}"])

    meshes = list(_iter_meshes(loaded))
    vertices = 0
    faces = 0
    watertight_values: list[bool] = []
    has_materials = False
    has_textures = False

    bounds: list[np.ndarray] = []
    for mesh in meshes:
        vertices += int(len(mesh.vertices))
        faces += int(len(mesh.faces))
        watertight_values.append(bool(mesh.is_watertight))
        if mesh.visual is not None:
            has_materials = has_materials or hasattr(mesh.visual, "material")
            material = getattr(mesh.visual, "material", None)
            image = getattr(material, "image", None)
            has_textures = has_textures or image is not None
        if mesh.vertices.size:
            bounds.append(mesh.bounds)

    bbox = None
    largest = None
    if bounds:
        stacked = np.stack(bounds)
        minimum = stacked[:, 0, :].min(axis=0)
        maximum = stacked[:, 1, :].max(axis=0)
        extents = np.maximum(maximum - minimum, 0)
        bbox = Dimensions(x=float(extents[0]), y=float(extents[1]), z=float(extents[2]))
        largest = float(extents.max())
        if largest == 0:
            warnings.append("Mesh has zero largest dimension.")
    else:
        warnings.append("No mesh geometry found.")

    return MeshMetrics(
        file_size_bytes=path.stat().st_size,
        vertices=vertices,
        faces=faces,
        mesh_count=len(meshes),
        bounding_box_m=bbox,
        largest_dimension_m=largest,
        is_watertight=all(watertight_values) if watertight_values else None,
        has_materials=has_materials,
        has_textures=has_textures,
        warnings=warnings,
    )
