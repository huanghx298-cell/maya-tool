

import os

import maya.cmds as cmds

from rig import rig_schema
from anim import animation_runtime


class AnimationTransfer:

    def __init__(self):

        self.rig_ctx = RIG_CTX
        self.anim_ctx = ANIM_CTX

    def import_retarget_skeleton(self, path):

        self.file_name = os.path.splitext(os.path.basename(path))[0]
        file_name = self.file_name

        retarget_group = RigHelpers.get_or_create_group_chain(
            "retarget_group", "animation_group", f"{file_name}_group")

        original_start_time = cmds.playbackOptions(query=True, minTime=True)
        original_end_time = cmds.playbackOptions(query=True, maxTime=True)
        self.anim_ctx.retarget_time_registry["scene"] = [
            original_start_time, original_end_time]

        new_nodes = cmds.file(path, i=True, namespace=f"{file_name}_cache",
                              importFrameRate=True, importTimeRange="override",
                              returnNewNodes=True)
        transform = cmds.ls(new_nodes, type="transform", long=True)[0]
        cmds.parent(transform, retarget_group)

        retarget_joints = cmds.listRelatives(
            retarget_group, allDescendents=True, type="joint", fullPath=True)
        for joint in retarget_joints:
            joint_name = joint.split("|")[-1].split(":")[-1]
            self.anim_ctx.retarget_joint_registry.setdefault(
                f"{file_name}", {})[joint_name] = joint

        start_time = cmds.playbackOptions(query=True, minTime=True)
        end_time = cmds.playbackOptions(query=True, maxTime=True)
        self.anim_ctx.retarget_time_registry[
            f"{file_name}"] = [start_time, end_time]
        meta_node = cmds.createNode(
            "network", name=f"{file_name}_group_animMeta")
        cmds.addAttr(meta_node,
                     longName="owner", attributeType="message")
        cmds.addAttr(meta_node,
                     longName="animEnd", attributeType="double")
        cmds.setAttr(f"{meta_node}.animEnd", end_time)

        cmds.addAttr(retarget_group,
                     longName="animMeta", attributeType="message")
        cmds.connectAttr(f"{meta_node}.owner",
                         f"{retarget_group}.animMeta")

        cmds.playbackOptions(maxTime=original_end_time)

    def build_retarget_fk_constraints(self):

        file_name = self.file_name

        retarget_group = RigHelpers.get_or_create_group_chain(
            "retarget_group", "animation_group")
        constraint_group = RigHelpers.get_or_create_group_chain(
            "retarget_group", "retarget_fk_constraints")

        fk_ctrls = self.rig_ctx.control_registry.get("fk", {})
        retarget_joints = self.anim_ctx.retarget_joint_registry.get(
            f"{file_name}", {})

        cmds.playbackOptions(minTime=-1)
        cmds.currentTime(-1)

        for joint_name, fk_ctrl in fk_ctrls.items():
            if joint_name == "root":
                continue
            retarget_joint = retarget_joints.get(joint_name)
            constraint = cmds.parentConstraint(retarget_joint, fk_ctrl)[0]
            cmds.parent(constraint, constraint_group)

        root_ctrl = self.rig_ctx.control_registry.get("fk", {}).get("root")
        constraint = cmds.parentConstraint(root_ctrl, retarget_group)
        cmds.parent(constraint, constraint_group)

    def build_limb_retarget_ik_constraints(self):

        schema = UE5_SCHEMA.get("limb", {})
        constraint_group = RigHelpers.get_or_create_group_chain(
            "retarget_group", "retarget_ik_constraints")
        ik_ctrls = self.rig_ctx.control_registry.get("ik", {})
        file_name = self.file_name
        retarget_joints = self.anim_ctx.retarget_joint_registry.get(
            f"{file_name}", {})

        for side, side_dict in schema.items():
            for limb_name, chain in side_dict.items():

                if limb_name == "upperarm":
                    mid_name = chain[2]
                    end_name = chain[3]
                else:
                    mid_name = chain[1]
                    end_name = chain[2]

                ik_mid_ctrl = ik_ctrls.get(mid_name)
                ik_end_ctrl = ik_ctrls.get(end_name)

                mid_joint = retarget_joints.get(mid_name)
                end_joint = retarget_joints.get(f"ik_{end_name}")

                cmds.select(ik_mid_ctrl)

                mid_offset_group = cmds.group(
                    empty=True, name=f"retarget_{mid_name}_offset_GRP")
                cmds.matchTransform(mid_offset_group, ik_mid_ctrl)
                cmds.parent(mid_offset_group, mid_joint)
                end_offset_group = cmds.group(
                    empty=True, name=f"retarget_{end_name}_offset_GRP")
                cmds.matchTransform(end_offset_group, ik_end_ctrl)
                cmds.parent(end_offset_group, end_joint)

                constraint1 = cmds.parentConstraint(
                    mid_offset_group, ik_mid_ctrl)
                constraint2 = cmds.parentConstraint(
                    end_offset_group, ik_end_ctrl)

                cmds.parent(constraint1, constraint_group)
                cmds.parent(constraint2, constraint_group)

        cmds.playbackOptions(minTime=0)

    def build_spine_retarget_ik_constraints(self):

        constraint_group = RigHelpers.get_or_create_group_chain(
            "retarget_group", "retarget_ik_constraints")
        ik_ctrls = self.rig_ctx.control_registry.get("ik", {})
        file_name = self.file_name
        retarget_joints = self.anim_ctx.retarget_joint_registry.get(
            f"{file_name}", {})

        mapping = {"spine_01": "pelvis",
                   "spine_03": "spine_04", }
        for ik_name, source_name in mapping.items():
            ik_ctrl = ik_ctrls.get(ik_name)
            retarget_joint = retarget_joints.get(source_name)
            offset_group = cmds.group(
                empty=True, name=f"retarget_{ik_name}_offset_GRP")
            cmds.matchTransform(offset_group, ik_ctrl)
            cmds.parent(offset_group, retarget_joint)
            constraint = cmds.parentConstraint(offset_group, ik_ctrl)[0]
            cmds.parent(constraint, constraint_group)

        cmds.playbackOptions(minTime=0)

    def build_retarget_bind_pose(self):

        deform_joints = self.rig_ctx.joint_registry.get("deform", {})
        file_name = self.file_name
        retarget_joints = self.anim_ctx.retarget_joint_registry.get(
            f"{file_name}", {})

        constraints = []
        for joint_name, deform_joint in deform_joints.items():
            retarget_joint = retarget_joints.get(joint_name)
            constraint = cmds.parentConstraint(deform_joint, retarget_joint)[0]
            constraints.append(constraint)

        joints = list(retarget_joints.values())

        cmds.bakeResults(joints, time=(-1, -1),
                         simulation=True, preserveOutsideKeys=True)

        attrs = ["rotateX", "rotateY", "rotateZ"]
        joint = retarget_joints.get("thigh_r")
        curves = cmds.listConnections(joint, connections=True, source=True)
        anim_curves = []
        for curve in curves:
            if any(curve.endswith(a) for a in attrs):
                anim_curves.append(curve)
        cmds.filterCurve(anim_curves, filter="euler")

        cmds.delete(constraints)

    def remove_retarget_bind_pose(self):

        file_name = self.file_name
        retarget_joints = self.anim_ctx.retarget_joint_registry.get(
            f"{file_name}", {})

        start_time, end_time = self.anim_ctx.retarget_time_registry.get(
            f"{file_name}")

        for retarget_joint in retarget_joints.values():
            anim_curves = cmds.listConnections(
                retarget_joint, type="animCurve", connections=True)
            for anim_curve in anim_curves:
                if not anim_curve.endswith(("X", "Y", "Z")):
                    continue
                cmds.setInfinity(anim_curve, postInfinite="cycle")
                cmds.cutKey(anim_curve, time=(-1, -1))
                cmds.cutKey(anim_curve, time=(end_time + 1, end_time + 1))

    @staticmethod
    def bake_ik_ctrl():

        schema = UE5_SCHEMA.get("limb", {})
        ik_ctrls = RIG_CTX.control_registry.get("ik", {})
        start = cmds.playbackOptions(query=True, minTime=True)
        end = cmds.playbackOptions(query=True, maxTime=True)

        for side, side_dict in schema.items():
            for limb_name, chain in side_dict.items():
                if limb_name == "upperarm":
                    continue
                ik_ctrl = ik_ctrls.get(chain[2])
                cmds.bakeResults(ik_ctrl, time=(start, end))
                anim_curves = cmds.listConnections(ik_ctrl, type="animCurve")
                cmds.filterCurve(anim_curves, filter="euler")


RigHelpers = rig_schema.RigHelpers
Animhelpers = animation_runtime.Animhelpers
RIG_CTX = rig_schema.RIG_CTX
ANIM_CTX = animation_runtime.ANIM_CTX
UE5_SCHEMA = rig_schema.UE5_SCHEMA
