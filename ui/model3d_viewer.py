import math
from pathlib import Path

import numpy as np
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QSurfaceFormat, QVector3D, QQuaternion
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtWidgets import QMessageBox
import OpenGL.GL as gl
import OpenGL.GLU as glu

from loaders.stl_loader import load_stl, MeshData

_BG = (0.15, 0.15, 0.15, 1.0)
_MAT_AMBIENT  = [0.20, 0.20, 0.25, 1.0]
_MAT_DIFFUSE  = [0.70, 0.70, 0.75, 1.0]
_MAT_SPECULAR = [0.40, 0.40, 0.40, 1.0]
_SHININESS    = 40.0


class Model3DViewerWidget(QOpenGLWidget):
    def __init__(self, parent=None):
        fmt = QSurfaceFormat()
        fmt.setDepthBufferSize(24)
        fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile)
        super().__init__(parent)
        self.setFormat(fmt)

        self._mesh: MeshData | None = None
        self._rotation = QQuaternion()
        self._pan = QVector3D(0.0, 0.0, 0.0)
        self._zoom: float = 5.0
        self._last_pos = QPoint()
        self._mouse_mode: str = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_file(self, file_path: str) -> None:
        ext = Path(file_path).suffix.lower()
        try:
            if ext in (".step", ".stp"):
                from loaders.step_loader import load_step
                self._mesh = load_step(file_path)
            else:
                self._mesh = load_stl(file_path)
        except Exception as exc:
            QMessageBox.warning(self, "3D 모델 오류", f"파일을 열 수 없습니다:\n{exc}")
            self._mesh = None
        self.fit()
        self.update()

    def fit(self) -> None:
        self._rotation = QQuaternion()
        self._pan = QVector3D(0.0, 0.0, 0.0)
        self._zoom = self._mesh.radius * 3.0 if self._mesh else 5.0
        self.update()

    def zoom_in(self) -> None:
        self._zoom = max(0.001, self._zoom * 0.8)
        self.update()

    def zoom_out(self) -> None:
        self._zoom *= 1.25
        self.update()

    # ------------------------------------------------------------------
    # OpenGL callbacks
    # ------------------------------------------------------------------

    def initializeGL(self) -> None:
        gl.glClearColor(*_BG)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_LIGHTING)
        gl.glEnable(gl.GL_LIGHT0)
        gl.glEnable(gl.GL_NORMALIZE)
        gl.glShadeModel(gl.GL_FLAT)

        gl.glLightfv(gl.GL_LIGHT0, gl.GL_AMBIENT,  [0.25, 0.25, 0.25, 1.0])
        gl.glLightfv(gl.GL_LIGHT0, gl.GL_DIFFUSE,  [0.85, 0.85, 0.85, 1.0])
        gl.glLightfv(gl.GL_LIGHT0, gl.GL_SPECULAR, [0.30, 0.30, 0.30, 1.0])

        gl.glMaterialfv(gl.GL_FRONT_AND_BACK, gl.GL_AMBIENT,   _MAT_AMBIENT)
        gl.glMaterialfv(gl.GL_FRONT_AND_BACK, gl.GL_DIFFUSE,   _MAT_DIFFUSE)
        gl.glMaterialfv(gl.GL_FRONT_AND_BACK, gl.GL_SPECULAR,  _MAT_SPECULAR)
        gl.glMaterialf (gl.GL_FRONT_AND_BACK, gl.GL_SHININESS, _SHININESS)

    def resizeGL(self, w: int, h: int) -> None:
        gl.glViewport(0, 0, max(1, w), max(1, h))

    def paintGL(self) -> None:
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        if self._mesh is None:
            return

        w = max(1, self.width())
        h = max(1, self.height())

        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glLoadIdentity()
        glu.gluPerspective(45.0, w / h, max(0.001, self._zoom * 0.01), self._zoom * 100.0)

        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glLoadIdentity()
        glu.gluLookAt(0, 0, self._zoom, 0, 0, 0, 0, 1, 0)

        # Light fixed relative to camera
        gl.glLightfv(gl.GL_LIGHT0, gl.GL_POSITION, [1.5, 2.0, 2.0, 0.0])

        gl.glTranslatef(self._pan.x(), self._pan.y(), 0.0)
        gl.glMultMatrixf(_quat_to_rot4(self._rotation))

        c = self._mesh.center
        gl.glTranslatef(-float(c[0]), -float(c[1]), -float(c[2]))

        _draw_mesh(self._mesh)
        self._draw_axes()

    # ------------------------------------------------------------------
    # Axes overlay (bottom-left corner, 2-D ortho pass)
    # ------------------------------------------------------------------

    def _draw_axes(self) -> None:
        w, h = max(1, self.width()), max(1, self.height())

        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glPushMatrix()
        gl.glLoadIdentity()
        glu.gluOrtho2D(0, w, 0, h)

        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glPushMatrix()
        gl.glLoadIdentity()

        gl.glDisable(gl.GL_LIGHTING)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glLineWidth(2.5)

        cx, cy, ln = 55.0, 55.0, 40.0
        R = _quat_to_rot3(self._rotation)

        axes = (
            (R @ np.array([1, 0, 0], dtype=np.float32), (1.0, 0.25, 0.25)),
            (R @ np.array([0, 1, 0], dtype=np.float32), (0.25, 0.90, 0.25)),
            (R @ np.array([0, 0, 1], dtype=np.float32), (0.35, 0.55, 1.0)),
        )

        gl.glBegin(gl.GL_LINES)
        for vec, color in axes:
            gl.glColor3f(*color)
            gl.glVertex2f(cx, cy)
            gl.glVertex2f(cx + float(vec[0]) * ln, cy + float(vec[1]) * ln)
        gl.glEnd()

        gl.glLineWidth(1.0)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_LIGHTING)
        gl.glColor3f(1.0, 1.0, 1.0)

        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glPopMatrix()
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glPopMatrix()

    # ------------------------------------------------------------------
    # Mouse / wheel events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        self._last_pos = event.pos()
        btn  = event.button()
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        if btn == Qt.MouseButton.LeftButton and not ctrl:
            self._mouse_mode = "rotate"
        elif btn == Qt.MouseButton.MiddleButton or (btn == Qt.MouseButton.LeftButton and ctrl):
            self._mouse_mode = "pan"
        else:
            self._mouse_mode = ""

    def mouseMoveEvent(self, event) -> None:
        if not self._mouse_mode:
            return
        cur  = event.pos()
        last = self._last_pos
        self._last_pos = cur

        if self._mouse_mode == "rotate":
            p1 = _screen_to_sphere(last.x(), last.y(), self.width(), self.height())
            p2 = _screen_to_sphere(cur.x(),  cur.y(),  self.width(), self.height())
            axis = np.cross(p1, p2)
            dot  = float(np.clip(np.dot(p1, p2), -1.0, 1.0))
            angle = math.degrees(math.acos(dot)) * 2.5
            n = float(np.linalg.norm(axis))
            if n > 1e-7:
                axis = axis / n
                delta = QQuaternion.fromAxisAndAngle(
                    QVector3D(float(axis[0]), float(axis[1]), float(axis[2])), angle
                )
                self._rotation = delta * self._rotation

        elif self._mouse_mode == "pan":
            dx = cur.x() - last.x()
            dy = cur.y() - last.y()
            scale = self._zoom * 0.0015
            self._pan += QVector3D(dx * scale, -dy * scale, 0.0)

        self.update()

    def mouseReleaseEvent(self, event) -> None:
        self._mouse_mode = ""

    def wheelEvent(self, event) -> None:
        f = 0.85 if event.angleDelta().y() > 0 else 1.0 / 0.85
        self._zoom = max(0.001, self._zoom * f)
        self.update()


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _screen_to_sphere(x: int, y: int, w: int, h: int) -> np.ndarray:
    """Map a screen pixel to the unit hemisphere (arcball)."""
    sx = (2 * x - w) / min(w, h)
    sy = (h - 2 * y) / min(w, h)
    sq = sx * sx + sy * sy
    if sq <= 1.0:
        sz = math.sqrt(1.0 - sq)
    else:
        n = math.sqrt(sq)
        sx /= n
        sy /= n
        sz = 0.0
    return np.array([sx, sy, sz], dtype=np.float64)


def _quat_to_rot3(q: QQuaternion) -> np.ndarray:
    """QQuaternion → 3×3 rotation matrix (numpy float32)."""
    w = q.scalar()
    v = q.vector()
    x, y, z = v.x(), v.y(), v.z()
    return np.array([
        [1 - 2*(y*y + z*z),     2*(x*y - w*z),     2*(x*z + w*y)],
        [    2*(x*y + w*z), 1 - 2*(x*x + z*z),     2*(y*z - w*x)],
        [    2*(x*z - w*y),     2*(y*z + w*x), 1 - 2*(x*x + y*y)],
    ], dtype=np.float32)


def _quat_to_rot4(q: QQuaternion) -> list:
    """QQuaternion → 4×4 column-major float list for glMultMatrixf."""
    R = _quat_to_rot3(q)
    return [
        R[0, 0], R[1, 0], R[2, 0], 0.0,
        R[0, 1], R[1, 1], R[2, 1], 0.0,
        R[0, 2], R[1, 2], R[2, 2], 0.0,
        0.0,     0.0,     0.0,     1.0,
    ]


def _draw_mesh(mesh: MeshData) -> None:
    gl.glEnableClientState(gl.GL_VERTEX_ARRAY)
    gl.glEnableClientState(gl.GL_NORMAL_ARRAY)
    gl.glVertexPointer(3, gl.GL_FLOAT, 0, mesh.flat_vertices)
    gl.glNormalPointer(gl.GL_FLOAT, 0, mesh.flat_normals)
    gl.glDrawArrays(gl.GL_TRIANGLES, 0, len(mesh.flat_vertices))
    gl.glDisableClientState(gl.GL_VERTEX_ARRAY)
    gl.glDisableClientState(gl.GL_NORMAL_ARRAY)
