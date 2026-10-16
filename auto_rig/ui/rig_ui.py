

from PySide6 import QtCore, QtGui, QtWidgets
from builder import rig_builder as rb
from data import rig_data as data


def face_rig():

    def eye_preview():
        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(section_header("      Eye      "))
        layout.addWidget(QtWidgets.QLabel("Outer Eye"))
        layout.addLayout(selection_row("outer_eye"))
        layout.addWidget(QtWidgets.QLabel("Inner Eye"))
        layout.addLayout(selection_row("inner_eye"))
        return layout

    layout = QtWidgets.QVBoxLayout()
    btn_Preview = QtWidgets.QPushButton("Preview")
    layout.addLayout(eye_preview())
    layout.addWidget(btn_Preview)
    btn_Preview.clicked.connect(lambda: rb.eye_auto())
    return layout


def body_rig():

    def run():
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        btn_run = QtWidgets.QPushButton("Run Auto Rig")
        layout.addWidget(btn_run)
        btn_run.clicked.connect(rb.body_auto)
        btn_debug = QtWidgets.QPushButton("Debug")
        layout.addWidget(btn_debug)
        btn_debug.clicked.connect(rb.debug)
        return widget

    layout = QtWidgets.QVBoxLayout()
    layout.addLayout(fold_header("Body Rig", run()))
    return layout


def reload_scene():
    rb.reload_scene()
    layout = QtWidgets.QVBoxLayout()
    btn_reload = QtWidgets.QPushButton("Reload Scene")
    layout.addLayout(section_header("System"))
    layout.addWidget(btn_reload)
    btn_reload.clicked.connect(rb.reload_scene)
    return layout


def fold_header(text, widget):

    def toggle(checked, btn):
        widget.setVisible(checked)
        btn.setArrowType(QtCore.Qt.DownArrow if checked
                         else QtCore.Qt.RightArrow)

    def fold_button(text):
        btn = QtWidgets.QToolButton()
        btn.setText(text)
        btn.setCheckable(True)
        btn.setChecked(True)
        btn.setArrowType(QtCore.Qt.DownArrow)
        btn.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                          QtWidgets.QSizePolicy.Fixed)
        btn.setStyleSheet("""QToolButton {text-align: left;
        padding: 6px 8px;border: none;background-color: #626262;
        font-weight: bold;}""")
        btn.toggled.connect(lambda checked: toggle(checked, btn))
        return btn

    layout = QtWidgets.QVBoxLayout()
    layout.addWidget(fold_button(text))
    layout.addWidget(widget)
    return layout


def section_header(text):
    layout = QtWidgets.QHBoxLayout()
    line_left = QtWidgets.QFrame()
    label = QtWidgets.QLabel(f"{text}")
    line_right = QtWidgets.QFrame()
    for line in (line_left, line_right):
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFixedHeight(1.75)
        line.setStyleSheet("background-color: #B2B2B2;")
    layout.addWidget(line_left, 1)
    layout.addWidget(label)
    layout.addWidget(line_right, 1)
    return layout


def selection_row(key):

    def set_field():
        selected = rb.get_selection()
        short_names = [obj.split("|")[-1] for obj in selected]
        data.face[key] = selected
        field.setText(", ".join(short_names))

    layout = QtWidgets.QHBoxLayout()
    field = QtWidgets.QLineEdit()
    btn_set = QtWidgets.QPushButton("Set")
    field.setPlaceholderText("No objects selected")
    field.setReadOnly(True)
    field.setProperty("objects", [])
    layout.addWidget(field)
    layout.addWidget(btn_set)
    btn_set.clicked.connect(set_field)
    return layout


def selection_control(data):

    def update_eye_loop(step):
        vertex = data["loop"]
        min_i = vertex.index(data["min"])
        max_i = vertex.index(data["max"])
        data["min"] = vertex[(min_i + step) % len(vertex)]
        data["max"] = vertex[(max_i + step) % len(vertex)]

    layout = QtWidgets.QHBoxLayout()
    btn_left = QtWidgets.QToolButton()
    btn_right = QtWidgets.QToolButton()
    btn_left.setArrowType(QtCore.Qt.LeftArrow)
    btn_right.setArrowType(QtCore.Qt.RightArrow)
    btn_left.clicked.connect(lambda: update_eye_loop(-1))
    btn_right.clicked.connect(lambda: update_eye_loop(1))
    layout.addWidget(btn_left)
    layout.addWidget(btn_right)
    return layout
