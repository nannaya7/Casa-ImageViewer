import math
import os
import shutil
import sys
from pathlib import Path

import ezdxf
from ezdxf.math import Vec2, bulge_to_arc
from PyQt6.QtGui import QPainterPath


def load_dxf(file_path: str) -> QPainterPath:
    """Parse DXF/DWG modelspace and return a QPainterPath (Y-axis flipped for Qt)."""
    doc = _read_cad_file(file_path)
    msp = doc.modelspace()
    path = QPainterPath()
    for entity in msp:
        try:
            _add_entity(entity, path)
        except Exception:
            pass
    return path


def _read_cad_file(file_path: str):
    ext = Path(file_path).suffix.lower()
    if ext == ".dwg":
        return _read_dwg(file_path)
    return ezdxf.readfile(file_path)


def _read_dwg(file_path: str):
    try:
        from ezdxf.addons import odafc
    except ImportError as exc:
        raise RuntimeError(
            "DWG 파일을 열려면 ezdxf의 ODA 변환 기능이 필요합니다."
        ) from exc

    _configure_odafc_path(odafc)
    try:
        return odafc.readfile(file_path, audit=False)
    except odafc.ODAFCNotInstalledError as exc:
        raise RuntimeError(
            "DWG 파일은 직접 읽을 수 없어 ODA File Converter가 필요합니다.\n"
            "ODA File Converter를 설치한 뒤 다시 실행해 주세요.\n"
            "설치 후에도 인식되지 않으면 ODA_FILE_CONVERTER 환경 변수에 "
            "ODAFileConverter.exe 전체 경로를 지정하면 됩니다."
        ) from exc
    except odafc.ODAFCError as exc:
        raise RuntimeError(f"DWG 변환에 실패했습니다:\n{exc}") from exc


def _configure_odafc_path(odafc) -> None:
    exe = _find_odafc_exe()
    if exe is None:
        return
    key = "win_exec_path" if sys.platform == "win32" else "unix_exec_path"
    ezdxf.options.set("odafc-addon", key, str(exe))


def _find_odafc_exe() -> Path | None:
    for env_name in ("ODA_FILE_CONVERTER", "ODAFC_PATH"):
        value = os.environ.get(env_name)
        if value:
            path = Path(value).expanduser()
            if path.is_dir():
                path = path / _odafc_exe_name()
            if path.is_file():
                return path

    found = shutil.which("ODAFileConverter")
    if found:
        return Path(found)

    if sys.platform == "win32":
        candidates: list[Path] = []
        for root in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
            if not root:
                continue
            base = Path(root)
            candidates.extend(base.glob("ODA/ODAFileConverter*/ODAFileConverter.exe"))
            candidates.extend(base.glob("Open Design Alliance/ODAFileConverter*/ODAFileConverter.exe"))
        for path in candidates:
            if path.is_file():
                return path

    return None


def _odafc_exe_name() -> str:
    return "ODAFileConverter.exe" if sys.platform == "win32" else "ODAFileConverter"


def _add_entity(entity, path: QPainterPath) -> None:
    t = entity.dxftype()

    if t == "LINE":
        s, e = entity.dxf.start, entity.dxf.end
        path.moveTo(s.x, -s.y)
        path.lineTo(e.x, -e.y)

    elif t == "CIRCLE":
        c, r = entity.dxf.center, entity.dxf.radius
        _add_arc_points(path, c.x, c.y, r, 0.0, 2 * math.pi)

    elif t == "ARC":
        pts = list(entity.flattening(0.5))
        _add_vec3_sequence(path, pts, closed=False)

    elif t == "LWPOLYLINE":
        _add_lwpolyline(entity, path)

    elif t == "POLYLINE":
        _add_polyline(entity, path)

    elif t == "SPLINE":
        pts = list(entity.flattening(0.5))
        closed = _entity_is_closed(entity)
        _add_vec3_sequence(path, pts, closed=closed)

    elif t == "ELLIPSE":
        pts = list(entity.flattening(0.5))
        _add_vec3_sequence(path, pts, closed=_entity_is_closed(entity))

    elif t == "INSERT":
        for sub in entity.virtual_entities():
            try:
                _add_entity(sub, path)
            except Exception:
                pass


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _add_arc_points(path: QPainterPath, cx: float, cy: float, r: float,
                    start_rad: float, end_rad: float) -> None:
    """Sample an arc and append to path, applying Y-flip."""
    if end_rad <= start_rad:
        end_rad += 2 * math.pi
    span = end_rad - start_rad
    n = max(36, int(math.degrees(span) / 5))
    first = True
    for i in range(n + 1):
        a = start_rad + span * i / n
        x = cx + r * math.cos(a)
        y = -(cy + r * math.sin(a))
        if first:
            path.moveTo(x, y)
            first = False
        else:
            path.lineTo(x, y)


def _add_vec3_sequence(path: QPainterPath, pts, closed: bool = False) -> None:
    """Add a Vec3 sequence to path with Y-flip."""
    if not pts:
        return
    path.moveTo(pts[0].x, -pts[0].y)
    for p in pts[1:]:
        path.lineTo(p.x, -p.y)
    if closed and len(pts) > 2:
        path.closeSubpath()


def _entity_is_closed(entity) -> bool:
    if entity.dxftype() == "ELLIPSE":
        try:
            start = float(entity.dxf.get("start_param", 0.0))
            end = float(entity.dxf.get("end_param", 2 * math.pi))
            return abs(end - start) >= (2 * math.pi - 1e-6)
        except Exception:
            return False

    closed = getattr(entity, "closed", None)
    if closed is not None:
        return bool(closed)
    try:
        return bool(entity.dxf.get("closed", 0))
    except Exception:
        return False


def _add_lwpolyline(entity, path: QPainterPath) -> None:
    pts = list(entity.get_points(format="xyseb"))
    if not pts:
        return
    n = len(pts)
    count = n if entity.is_closed else n - 1

    # Collect all (x, y) positions, expanding bulge arcs into line segments
    xy: list[tuple[float, float]] = [(pts[0][0], pts[0][1])]
    for i in range(count):
        cx, cy = pts[i][0], pts[i][1]
        nxt = pts[(i + 1) % n]
        nx, ny = nxt[0], nxt[1]
        bulge = pts[i][4]

        _append_bulge_segment(xy, cx, cy, nx, ny, bulge)

    path.moveTo(xy[0][0], -xy[0][1])
    for x, y in xy[1:]:
        path.lineTo(x, -y)
    if entity.is_closed and len(xy) > 2:
        path.closeSubpath()


def _add_polyline(entity, path: QPainterPath) -> None:
    verts = list(entity.vertices)
    if not verts:
        return

    n = len(verts)
    loc0 = verts[0].dxf.location
    xy: list[tuple[float, float]] = [(loc0.x, loc0.y)]
    count = n if entity.is_closed else n - 1
    for i in range(count):
        loc = verts[i].dxf.location
        nxt = verts[(i + 1) % n].dxf.location
        try:
            bulge = float(verts[i].dxf.get("bulge", 0.0))
        except Exception:
            bulge = 0.0
        _append_bulge_segment(xy, loc.x, loc.y, nxt.x, nxt.y, bulge)

    path.moveTo(xy[0][0], -xy[0][1])
    for x, y in xy[1:]:
        path.lineTo(x, -y)
    if entity.is_closed:
        path.closeSubpath()


def _append_bulge_segment(
    xy: list[tuple[float, float]],
    cx: float,
    cy: float,
    nx: float,
    ny: float,
    bulge: float,
) -> None:
    if abs(bulge) < 1e-9:
        xy.append((nx, ny))
        return

    center, sa, ea, r = bulge_to_arc(Vec2(cx, cy), Vec2(nx, ny), bulge)
    if bulge < 0:
        sa, ea = ea, sa
        if sa <= ea:
            sa += 2 * math.pi
        span = sa - ea
    else:
        if ea <= sa:
            ea += 2 * math.pi
        span = ea - sa
    segs = max(8, int(math.degrees(span) / 5))
    for j in range(1, segs + 1):
        if bulge < 0:
            a = sa - span * j / segs
        else:
            a = sa + span * j / segs
        xy.append((center.x + r * math.cos(a), center.y + r * math.sin(a)))
