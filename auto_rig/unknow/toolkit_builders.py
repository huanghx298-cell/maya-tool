

import random
import colorsys

import os
from PySide6 import QtWidgets, QtCore
from collections import defaultdict
import maya.cmds as cmds
import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma


import importlib


from rig import rig_schema as rbr
from rig import rig_ctrl
from rig import rig_body as rbb
from unknow import rig_builders_hand_foot
from rig import rig_builders_deformation
from rig import rig_builders_space

from anim import animation_runtime
from anim import animation_transfer
from anim import animation_path
from anim import animation_locomotion

import unknow.utils as utils
import unknow.curve_builders as curve_builders
import unknow.joint_builders as jb

importlib.reload(rbr)
importlib.reload(rig_ctrl)
importlib.reload(rbb)
importlib.reload(rig_builders_hand_foot)
importlib.reload(rig_builders_deformation)
importlib.reload(rig_builders_space)

importlib.reload(animation_runtime)
importlib.reload(animation_transfer)
importlib.reload(animation_path)
importlib.reload(animation_locomotion)


importlib.reload(utils)
importlib.reload(curve_builders)
importlib.reload(jb)


class RigBuilder:

    @staticmethod
    def create_curve():

        # Build curves and joint chains.
        sel = cmds.ls(sl=True, fl=True)
        curves = CurveBuilder.build_from_edges(sel)
        cv_data = {}
        for cv in curves:
            pos = cmds.pointOnCurve(cv, pr=0.5, top=True, p=True)
            jnts = jb.JointBuilder.build_from_curve_p(cv, [0.0, 0.5, 1.0])
            cv_data[cv] = {"pos": pos, "jnts": jnts}
            for src, dst in zip(jnts[:-1], jnts[1:]):
                m0, m1 = utils.Transform.orient_to_target(src, dst, "x", "y")
                rbr.RigHelpers.bake_transform_to_opm(src)
                cmds.parent(dst, src)
                utils.Math.bake_joint_orient_to_rotate(dst)
            rbr.RigHelpers.bake_transform_to_opm(dst)
            cmds.xform(dst, ws=True, matrix=m1)

        # Collect connected mesh components and assign IDs.
        mesh = cmds.polyListComponentConversion(sel[0])[0]
        groups = utils.Mesh.get_connected_groups(
            utils.Mesh.get_edges(mesh))
        centers = utils.Mesh.get_vertex_group_centers(
            [group["vertices"] for group in groups.values()])
        for group, center in zip(groups.values(), centers):
            group["center"] = center

        # Assign connected group ID to their nearest curves.
        for data in cv_data.values():
            data["ids"] = []
        for group_id, group in groups.items():
            center_pos = group["center"]
            nearest_cv = None
            nearest_dist = float("inf")
            for cv, data in cv_data.items():
                dist = utils.Math.distance_squared(center_pos, data["pos"])
                if dist < nearest_dist:
                    nearest_dist = dist
                    nearest_cv = cv
            cv_data[nearest_cv]["ids"].append(group_id)

        # Assign faces to materials based on grouping.
        sgs = utils.MaterialUtils.create_band_materials(len(curves))
        for cv, sg in zip(curves, sgs):
            faces_to_assign = []
            for id in cv_data[cv]["ids"]:
                faces_to_assign.extend(groups[id]["faces"])
            cmds.sets(faces_to_assign, e=True, forceElement=sg)

        vtx_id_grps = []
        jnt_grps = []
        for cv, data in cv_data.items():
            vtx_ids = []
            for id in data["ids"]:
                vtx_ids.extend(int(vtx.split("[")[-1].split("]")[0])
                               for vtx in groups[id]["vertices"])
            vtx_id_grps.append(vtx_ids)
            jnt_grps.append(data["jnts"])
        vtx_jntsw_map = utils.SkinWeight.jnt_hier_dist(
            mesh, vtx_id_grps, jnt_grps)
        all_jnts = [jnt for data in cv_data.values() for jnt in data["jnts"]]
        RigBuilder.set_skin_weights(mesh, vtx_jntsw_map, all_jnts)

    @staticmethod
    def set_skin_weights(mesh, weights_by_vertex, jnts):

        mesh_transform = cmds.listRelatives(mesh, p=True, f=True)[0]
        mesh_dag = om.MSelectionList().add(mesh).getDagPath(0)
        skin_cluster = cmds.skinCluster(jnts, mesh_transform, nw=False)[0]
        skin_fn = oma.MFnSkinCluster(
            om.MSelectionList().add(skin_cluster).getDependNode(0))

        vtx_count = cmds.polyEvaluate(mesh, vertex=True)
        comp_fn = om.MFnSingleIndexedComponent()
        comp = comp_fn.create(om.MFn.kMeshVertComponent)
        comp_fn.addElements(list(range(vtx_count)))

        inf_dags = skin_fn.influenceObjects()
        inf_names = [dag.partialPathName() for dag in inf_dags]
        jnts_indices = om.MIntArray()
        for jnt in jnts:
            idx = inf_names.index(jnt)
            jnts_indices.append(idx)

        # flatten weights: vertex-major, then influence order
        ws = om.MDoubleArray()
        for vtx_id in range(vtx_count):
            data = weights_by_vertex[vtx_id]
            for jnt in jnts:
                ws.append(data.get(jnt, 0.0))

        skin_fn.setWeights(mesh_dag, comp, jnts_indices, ws)


class AnimBuilder:

    def __init__(self):

        self.animtransfer = AnimTransfer()
        self.animpath = AnimPath()
        self.locomotion = AnimLocomotion()

    def build_retarget_fk_ik_ctrl(self, file_path, file_name):

        self.animtransfer.import_retarget_skeleton(file_path)
        self.animtransfer.build_retarget_bind_pose()
        self.animtransfer.build_retarget_fk_constraints()
        self.animtransfer.build_limb_retarget_ik_constraints()
        self.animtransfer.build_spine_retarget_ik_constraints()
        self.locomotion.locomotion_setup_foot_lock_reference()
        self.animpath.setup_root_motion_curve_locator()
        self.animtransfer.remove_retarget_bind_pose()
        self.locomotion.locomotion_base_distance(file_name)

    def setup_root_motion_edit(self, file_name):

        self.animpath.setup_root_motion_edit(file_name)

    def build_root_motion(self, file_name):

        self.locomotion.create_pose_reference()
        self.animpath.get_root_motion_positions(file_name)
        self.animpath.cache_root_motion_positions(file_name)
        self.animpath.build_root_motion_curve()

    def preview_root_motion(self, file_name):

        self.animpath.build_root_motion_curve()
        # self.animpath.apply_root_motion_pathsssss()
        self.animpath.setup_root_motion_path()
        self.animpath.apply_root_motion_path(file_name)

    def finalize_root_motion(self):

        self.locomotion.locomotion_get_foot_lock_ranges()
        self.locomotion.foot_ik_lock()


class UIbuilder:

    @staticmethod
    def debug():
        start_jnt, end_jnt = cmds.ls(sl=True, long=True, type="joint")[:2]
        src = start_jnt.split("|")
        dst = end_jnt.split("|")
        jnts = ["|".join(dst[:i]) for i in range(len(src), len(dst) + 1)]
        spine = {
            "jnts": jnts,
            "fk_jnts": SkeletonRig.build_skeleton(jnts, "fk"),
            "ik_jnts": SkeletonRig.build_skeleton(jnts, "ik"),
            "fk_ctrls": ControlBuilder.build_fk_controls(jnts, "large"),
            "ik_ctrls": ControlBuilder.build_curve_ik_controls(jnts, "large"),
            "ikfk_ctrl": ControlBuilder.build_ikfk_controls(jnts),
        }
        spine["follow_jnts"], spine["ik_ctrls"] = SpineRig.build_spine_ik_driver_system(
            spine["ik_jnts"], spine["ik_ctrls"])
        SpineRig.build_spine_ikfk_deform_drivers(spine)

        root = "|Group"

        nodes = [root] + (cmds.listRelatives(
            root,
            allDescendents=True,
            fullPath=True,
            type="transform"
        ) or [])

        for node in nodes:
            short_name = node.rsplit("|", 1)[-1]
            if short_name.endswith(("_CRV", "_JNT", "_LOC")):
                try:
                    cmds.setAttr(node + ".visibility", 0)
                except Exception:
                    pass

    @staticmethod
    def reload_scene(card_list):

        scene = cmds.file(query=True, sceneName=True)
        cmds.file(scene, open=True, force=True)

        RIG_CTX.rebuild()
        ANIM_CTX.rebuild()

        if card_list:
            card_list.clear()
        groups = ANIM_CTX.path_registry.get("root_motion_groups")
        for group in groups:
            item = QtWidgets.QListWidgetItem(group)
            item.setSizeHint(QtCore.QSize(100, 40))
            card_list.addItem(item)

        current_active_file = None

    def on_run_selected(self):

        # Warning:
        # Reopening the current scene here is safe when running manually.
        # But if this function is triggered automatically on scene load
        # (e.g. via userSetup or scriptJob), it may cause an infinite reload loop.

        folder = r"C:\Users\huang\Documents\maya\projects\auto_rig_Lite\assets\anim_retarget"

        files = os.listdir(folder)
        files = [f for f in files if f.endswith((".ma", ".mb"))]
        file_name = files[0]

        self.full_path = os.path.join(folder, file_name)
        file_name = os.path.splitext(os.path.basename(self.full_path))[0]

        self.run_with_undo(
            self.animbuilder.build_retarget_fk_ik_ctrl, self.full_path, file_name)

    @staticmethod
    def populate_dropdown_from_registry(dropdown):
        registry = ANIM_CTX.retarget_joint_registry
        names = list(registry.keys())
        dropdown.addItems(names)

    @staticmethod
    def place_animation(dropdown, current_active_file, card_list, btn_done, btn_preview):
        file_name = dropdown.currentText()
        if current_active_file:
            UIbuilder.run_with_undo(
                AnimBuilder.build_root_motion, current_active_file)
        UIbuilder.run_with_undo(AnimBuilder.setup_root_motion_edit, file_name)
        current_group = ANIM_CTX.path_registry["current_root_motion_group"]
        item = QtWidgets.QListWidgetItem(current_group)
        item.setSizeHint(QtCore.QSize(100, 40))
        card_list.addItem(item)
        current_active_file = file_name

        btn_done.setEnabled(True)
        btn_preview.setEnabled(False)

    def done(self):
        file_name = self.dropdown.currentText()
        self.run_with_undo(self.animbuilder.build_root_motion, file_name)
        self.btn_done.setEnabled(False)
        self.btn_preview.setEnabled(True)
        self.current_active_file = None

    def preview_root_motion(self):

        file_name = self.dropdown.currentText()

        order = []
        for i in range(self.card_list.count()):
            item = self.card_list.item(i)
            order.append(item.text())
        ANIM_CTX.path_registry["root_motion_groups"] = order

        for index, group in enumerate(order):
            meta = cmds.ls(f"{group}_animMeta", type="network")[0]
            cmds.setAttr(f"{meta}.order", index)

        self.run_with_undo(self.animbuilder.preview_root_motion, file_name)

    def finalize_root_motion(self):
        self.run_with_undo(self.animbuilder.finalize_root_motion)

    @staticmethod
    def run_with_undo(func, *args):
        cmds.undoInfo(openChunk=True)
        try:
            return func(*args)
        except Exception as e:
            cmds.warning(str(e))
            raise
        finally:
            cmds.undoInfo(closeChunk=True)


class RigPipeline:

    @staticmethod
    def build_limb_ikfk():

        ControlBuilder.build_limb_iK_controls()
        ControlBuilder.build_limb_ikfk_controls()

        LimbRig.build_limb_ikfk_deform_drivers()
        LimbRig.build_limb_fk_ctrl_joint_drivers()
        LimbRig.build_limb_ik_ctrl_joint_drivers()

        LimbRig.build_clavicle_fk_ctrl_joint_drivers()

    @staticmethod
    def build_spine_ikfk():

        ControlBuilder.build_spine_iK_controls()
        ControlBuilder.build_spine_ikfk_controls()
        ControlBuilder.build_hip_controls()

        SpineRig.build_spine_ik_driver_system()
        SpineRig.build_spine_ikfk_deform_drivers()

    @staticmethod
    def build_hand():

        ControlBuilder.build_hand_controls()

        HandRig.build_hand_spread_attributes()
        HandRig.build_hand_curl_attributes()

        HandRig.build_finger_fk_deform_drivers()

    @staticmethod
    def build_foot():

        FootRig.build_roll_bank_skeleton()
        FootRig.build_roll_bank_iK_driver()
        FootRig.build_roll_driver()
        FootRig.build_bank_driver()

    @staticmethod
    def build_twist():

        TwistRig.build_twist_driver()
        TwistRig.build_twist_system()
        TwistRig.build_twist_direction_references()

    @staticmethod
    def build_head():

        ControlBuilder.build_head_controls()
        HeadRig.build_head_fk_deform_drivers()

    @staticmethod
    def build_space():

        SpaceSystem.build_clavicle_follow_spine_driver()
        SpaceSystem.build_thigh_follow_pelvis_drivers()
        SpaceSystem.build_head_follow_spine_driver()
        SpaceSystem.build_spine_start_end_mid_ctrl_driver()
        SpaceSystem.build_ik_fk_hand_ctrl_drivers()

        SpaceSystem.build_root_ik_fk_ctrl_drivers()


RIG_CTX = rbr.RIG_CTX
ANIM_CTX = animation_runtime.ANIM_CTX
UE5_SCHEMA = rbr.UE5_SCHEMA

Skeleton = rbb.Skeleton
SpineRig = rbb.SpineRig
LimbRig = rbb.LimbRig
HandRig = rig_builders_hand_foot.HandRig
FootRig = rig_builders_hand_foot.FootRig
TwistRig = rig_builders_deformation.TwistRig
HeadRig = rig_builders_hand_foot.HeadRig
SpaceSystem = rig_builders_space.SpaceSystem

AnimTransfer = animation_transfer.AnimationTransfer
AnimPath = animation_path.AnimationPath
AnimLocomotion = animation_locomotion.AnimationLocomotion

CurveBuilder = curve_builders.CurveBuilder
