

import importlib
import inspect

from builder import rig_builder
from builder import rig_setup
from builder import rig_build
from builder import rig_finalize

from data import rig_data

from rig import rig_schema
from rig import rig_skeleton
from rig import rig_ctrl
from rig import rig_spline

from ui import rig_ui

import utils.mesh_utils as mesh_utils
import utils.dag_utils as dag_utils
import utils.transform_utils as transform_utils


MODULES = [
    rig_ui,

    rig_builder,
    rig_setup,
    rig_build,
    rig_finalize,

    rig_data,
    rig_schema,
    rig_skeleton,
    rig_ctrl,
    rig_spline,

    mesh_utils,
    dag_utils,
    transform_utils,
]


def clean_reload(module):
    for name, obj in list(vars(module).items()):

        if (
            (inspect.isfunction(obj) or inspect.isclass(obj))
            and getattr(obj, "__module__", None) == module.__name__
        ):
            delattr(module, name)

    return importlib.reload(module)


def reload_all():
    for module in MODULES:
        clean_reload(module)
