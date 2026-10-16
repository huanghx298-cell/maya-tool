

import importlib
import sys
import shiboken6
from PySide6 import QtWidgets
import maya.OpenMayaUI as omui
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

ROOT = r"C:\Users\huang\Desktop\auto_rig"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if True:
    import ui.rig_ui as rig_ui
    import data.rig_dev as rig_dev
importlib.reload(rig_dev)


class MySquareUI(MayaQWidgetDockableMixin, QtWidgets.QDialog):

    def __init__(self):
        super().__init__(get_maya_window())
        self.setWindowTitle("Auto Rig & Animation Toolkit")
        self.resize(300, 500)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel(
            "Rigging & Retargeting & Root Motion"))
        layout.addLayout(rig_ui.face_rig())
        layout.addSpacing(40)
        layout.addLayout(rig_ui.body_rig())
        layout.addSpacing(40)
        layout.addLayout(rig_ui.reload_scene())
        layout.addStretch()


def get_maya_window():
    ptr = omui.MQtUtil.mainWindow()
    return shiboken6.wrapInstance(int(ptr), QtWidgets.QWidget)


def show_ui():
    show_ui.instance = MySquareUI()
    show_ui.instance.show(dockable=True)
    return show_ui.instance


rig_dev.reload_all()
show_ui()
