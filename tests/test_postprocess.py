from __future__ import annotations

import numpy as np
import pytest
import trimesh

from visionspace_asset_foundry.postprocess.inspect_mesh import inspect_mesh
from visionspace_asset_foundry.postprocess.normalize import normalize_glb


def test_inspect_mesh_respects_scene_transforms(tmp_path) -> None:
    mesh = trimesh.creation.box(extents=(1.0, 2.0, 3.0))
    scene = trimesh.Scene()
    transform = np.eye(4)
    transform[:3, 3] = [10.0, -4.0, 2.0]
    scene.add_geometry(mesh, transform=transform)

    path = tmp_path / "translated-box.glb"
    scene.export(path)

    metrics = inspect_mesh(path)

    assert metrics.bounding_box_m is not None
    assert metrics.bounding_box_m.x == pytest.approx(1.0)
    assert metrics.bounding_box_m.y == pytest.approx(2.0)
    assert metrics.bounding_box_m.z == pytest.approx(3.0)


def test_normalize_glb_scales_largest_dimension_and_aligns_floor(tmp_path) -> None:
    mesh = trimesh.creation.box(extents=(1.0, 2.0, 3.0))
    scene = trimesh.Scene()
    transform = np.eye(4)
    transform[:3, 3] = [5.0, 6.0, 7.0]
    scene.add_geometry(mesh, transform=transform)

    input_path = tmp_path / "input.glb"
    output_path = tmp_path / "output.glb"
    scene.export(input_path)

    metrics = normalize_glb(input_path, output_path, target_largest_dimension_m=6.0)
    loaded = trimesh.load(output_path, force="scene")

    assert metrics.largest_dimension_m == pytest.approx(6.0)
    assert loaded.bounds[0][2] == pytest.approx(0.0)
