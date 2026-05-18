from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QCheckBox, QPushButton, QFormLayout,
)
from PyQt6.QtCore import Qt


class ResizeDialog(QDialog):
    def __init__(self, width: int, height: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("크기 조정")
        self.setFixedWidth(300)
        self._orig_w = width
        self._orig_h = height
        self._ratio = width / height if height else 1.0
        self._updating = False
        self._setup_ui(width, height)

    def _setup_ui(self, width: int, height: int) -> None:
        layout = QVBoxLayout(self)

        info = QLabel(f"현재 크기:  {width} × {height} px")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)
        layout.addSpacing(8)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._spin_w = QSpinBox()
        self._spin_w.setRange(1, 32000)
        self._spin_w.setValue(width)
        self._spin_w.setSuffix(" px")
        form.addRow("너비:", self._spin_w)

        self._spin_h = QSpinBox()
        self._spin_h.setRange(1, 32000)
        self._spin_h.setValue(height)
        self._spin_h.setSuffix(" px")
        form.addRow("높이:", self._spin_h)

        layout.addLayout(form)
        layout.addSpacing(4)

        self._chk_lock = QCheckBox("가로세로 비율 유지")
        self._chk_lock.setChecked(True)
        layout.addWidget(self._chk_lock)
        layout.addSpacing(12)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton("확인")
        btn_ok.setDefault(True)
        btn_ok.setFixedWidth(80)
        btn_cancel = QPushButton("취소")
        btn_cancel.setFixedWidth(80)
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        self._spin_w.valueChanged.connect(self._on_width_changed)
        self._spin_h.valueChanged.connect(self._on_height_changed)

    def _on_width_changed(self, value: int) -> None:
        if self._updating or not self._chk_lock.isChecked():
            return
        self._updating = True
        self._spin_h.setValue(max(1, round(value / self._ratio)))
        self._updating = False

    def _on_height_changed(self, value: int) -> None:
        if self._updating or not self._chk_lock.isChecked():
            return
        self._updating = True
        self._spin_w.setValue(max(1, round(value * self._ratio)))
        self._updating = False

    @property
    def result_size(self) -> tuple[int, int]:
        return self._spin_w.value(), self._spin_h.value()
