import os
import tempfile

from loaders.stl_loader import MeshData, load_stl


def load_step(file_path: str) -> MeshData:
    """Load a STEP file via OCP (cadquery-ocp) tessellation → temp STL → MeshData."""
    try:
        from OCP.BRepMesh import BRepMesh_IncrementalMesh
        from OCP.IFSelect import IFSelect_RetDone
        from OCP.STEPControl import STEPControl_Reader
        from OCP.StlAPI import StlAPI_Writer
    except ImportError as e:
        raise ImportError(
            "STEP 파일을 열려면 cadquery 패키지가 필요합니다.\n"
            f"설치: python -m pip install cadquery\n({e})"
        ) from e

    reader = STEPControl_Reader()
    status = reader.ReadFile(file_path)
    if status != IFSelect_RetDone:
        raise RuntimeError(f"STEP 파일을 읽을 수 없습니다: {file_path}")

    reader.TransferRoots()
    shape = reader.OneShape()

    # Tessellate: linear deflection 0.1 mm, angular deflection 0.5 rad
    mesh = BRepMesh_IncrementalMesh(shape, 0.1, False, 0.5)
    mesh.Perform()
    if not mesh.IsDone():
        raise RuntimeError("STEP 메시 생성에 실패했습니다.")

    fd, tmp_path = tempfile.mkstemp(suffix=".stl")
    os.close(fd)
    try:
        writer = StlAPI_Writer()
        writer.ASCIIMode = False
        writer.Write(shape, tmp_path)
        return load_stl(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
