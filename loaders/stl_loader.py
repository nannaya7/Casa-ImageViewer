from dataclasses import dataclass

import numpy as np
import trimesh


@dataclass
class MeshData:
    flat_vertices: np.ndarray  # (M*3, 3) float32  — one row per vertex, pre-expanded per face
    flat_normals: np.ndarray   # (M*3, 3) float32  — face normal repeated 3× per face
    center: np.ndarray         # (3,)    float32  — bounding-sphere centre
    radius: float              # bounding-sphere radius


def load_stl(file_path: str) -> MeshData:
    """Load an STL file and return flat vertex/normal arrays ready for GL_TRIANGLES."""
    mesh = trimesh.load(file_path, force="mesh")

    verts = np.array(mesh.vertices, dtype=np.float32)
    faces = np.array(mesh.faces, dtype=np.int32)

    flat_verts = np.ascontiguousarray(verts[faces].reshape(-1, 3))

    normals = np.array(mesh.face_normals, dtype=np.float32)
    flat_normals = np.ascontiguousarray(np.repeat(normals, 3, axis=0))

    # Bounding-box based bounding sphere (avoids optional scipy dependency)
    bbox_min = verts.min(axis=0)
    bbox_max = verts.max(axis=0)
    center = ((bbox_min + bbox_max) / 2.0).astype(np.float32)
    radius = float(np.linalg.norm(bbox_max - bbox_min) / 2.0)
    if radius < 1e-9:
        radius = 1.0

    return MeshData(
        flat_vertices=flat_verts,
        flat_normals=flat_normals,
        center=center,
        radius=radius,
    )
