

import os

import maya.cmds as cmds

from rig import rig_schema
from anim import animation_runtime


class AnimationPath:

    def __init__(self):

        self.rig_ctx = RIG_CTX
        self.anim_ctx = ANIM_CTX

        self.animhelper = Animhelpers()

    def setup_root_motion_curve_locator(self):

        locator_group = RigHelpers.get_or_create_group_chain(
            "retarget_group", "root_motion_curve", "root_motion_curve_ref")
        root_ctrl = self.rig_ctx.control_registry.get("fk", {}).get("root")

        back_loc = cmds.spaceLocator(name="root_motion_back_loc")[0]
        cmds.move(0, 0, -40, back_loc)
        cmds.parent(back_loc, locator_group)
        back_loc = cmds.ls(back_loc, long=True)[0]

        mid_loc = cmds.spaceLocator(name="root_motion_mid_loc")[0]
        cmds.parent(mid_loc, locator_group)
        mid_loc = cmds.ls(mid_loc, long=True)[0]

        front_loc = cmds.spaceLocator(name="root_motion_front_loc")[0]
        cmds.move(0, 0, 60, front_loc)
        cmds.parent(front_loc, locator_group)
        front_loc = cmds.ls(front_loc, long=True)[0]

        cmds.parentConstraint(root_ctrl, locator_group)

        self.anim_ctx.path_registry["root_motion_refs"] = (
            back_loc, mid_loc, front_loc)

    def setup_root_motion_edit(self, file_name):

        original_start_time = cmds.playbackOptions(query=True, minTime=True)
        original_end_time = cmds.playbackOptions(query=True, maxTime=True)
        self.anim_ctx.retarget_time_registry["scene"] = [
            original_start_time, original_end_time]

        cache_group = RigHelpers.get_or_create_group_chain(
            "retarget_group", "root_motion_curve", "root_motion_position_cache")
        locator_group = cmds.group(
            empty=True, name=file_name, parent=cache_group)
        self.anim_ctx.path_registry["current_root_motion_group"] = locator_group

        groups = cmds.listRelatives(
            cache_group, children=True, type="transform") or []
        index = len(groups)
        meta_node = cmds.createNode(
            "network", name=f"{locator_group}_animMeta")
        cmds.addAttr(meta_node, ln="order", at="long")
        cmds.setAttr(f"{meta_node}.order", index-1)
        cmds.addAttr(meta_node,
                     longName="owner", attributeType="message")
        cmds.addAttr(locator_group,
                     longName="animMeta", attributeType="message")
        cmds.connectAttr(f"{meta_node}.owner",
                         f"{locator_group}.animMeta")

        groups = self.animhelper.get_ordered_groups(groups)
        self.anim_ctx.path_registry["root_motion_groups"] = groups

        start, end = self.anim_ctx.retarget_time_registry.get(file_name)
        cmds.playbackOptions(minTime=start, maxTime=end)
        cmds.currentTime(start)

        root_ctrl = self.rig_ctx.control_registry.get("fk", {}).get("root")

        root_short = root_ctrl.split("|")[-1]
        mp = cmds.ls(f"{root_short}_followPath_MP")
        if mp:
            cmds.delete(mp)
            cmds.makeIdentity(root_ctrl,
                              translate=True, rotate=True, scale=True)
        cmds.select(root_ctrl)
        cmds.setToolTo("moveSuperContext")
        # cmds.viewFit(all=True)

    def get_root_motion_positions(self, file_name):

        back_loc, mid_loc, front_loc = self.anim_ctx.path_registry["root_motion_refs"]

        back_pos = cmds.xform(
            back_loc, query=True, worldSpace=True, translation=True)
        mid_pos = cmds.xform(
            mid_loc, query=True, worldSpace=True, translation=True)
        front_pos = cmds.xform(
            front_loc, query=True, worldSpace=True, translation=True)

        self.anim_ctx.path_registry.setdefault(
            "root_motion_positions", {})[file_name] = [back_pos, mid_pos, front_pos]

    def cache_root_motion_positions(self, file_name):

        locator_group = self.anim_ctx.path_registry["current_root_motion_group"]
        mesh_node = f"{locator_group}_pose_reference"

        back_loc = cmds.spaceLocator(
            name=f"{locator_group}_root_motion_back_loc")[0]
        mid_loc = cmds.spaceLocator(
            name=f"{locator_group}_root_motion_mid_loc")[0]
        front_loc = cmds.spaceLocator(
            name=f"{locator_group}_root_motion_front_loc")[0]

        positions = self.anim_ctx.path_registry.get(
            "root_motion_positions", {}).get(file_name)
        cmds.xform(back_loc, worldSpace=True, translation=positions[0])
        cmds.xform(mid_loc, worldSpace=True, translation=positions[1])
        cmds.xform(front_loc, worldSpace=True, translation=positions[2])
        cmds.parent(back_loc, mesh_node)
        cmds.parent(mid_loc, mesh_node)
        cmds.parent(front_loc, mesh_node)

        current_frame = cmds.currentTime(query=True)
        meta_node = cmds.ls(f"{locator_group}_animMeta", type="network")[0]
        cmds.addAttr(meta_node,
                     longName="sampleFrame", attributeType="double")
        cmds.setAttr(f"{meta_node}.sampleFrame", current_frame)
        self.anim_ctx.path_registry.setdefault(
            "root_motion_sample_frames", {})[locator_group] = current_frame

        cmds.select(clear=True)

    def build_root_motion_curve(self):

        groups = self.anim_ctx.path_registry.get("root_motion_groups", [])
        positions = []
        for group in groups:
            locators = cmds.listRelatives(
                group, allDescendents=True, type="transform")
            for loc in locators:
                shapes = cmds.listRelatives(loc, shapes=True)
                if shapes and cmds.nodeType(shapes[0]) == "locator":
                    pos = cmds.xform(
                        loc, query=True, worldSpace=True, translation=True)
                    positions.append(pos)
        curve_points = [[0, 0, 0]] + positions

        curve_name = "rootMotionTrajectory_CRV"
        if cmds.objExists(curve_name):
            cmds.delete(curve_name)
        self.curve = cmds.curve(
            degree=3, editPoint=curve_points, name=curve_name,)
        cmds.setAttr(f"{self.curve}.overrideEnabled", 1)
        cmds.setAttr(f"{self.curve}.overrideColor", 21)

    def apply_root_motion_pathsssss(self):

        root_ctrl = self.rig_ctx.control_registry.get("fk", {}).get("root")

        self.curve = cmds.ls("curve1", long=True)[0]

        curve_info = cmds.createNode("curveInfo", name="curveInfo")
        cmds.connectAttr(f"{self.curve}.worldSpace[0]",
                         f"{curve_info}.inputCurve")
        curve_length = cmds.getAttr(f"{curve_info}.arcLength")

        root_short = root_ctrl.split("|")[-1]
        mp_node = cmds.createNode(
            "motionPath", name=f"{root_short}_followPath_MP")
        cmds.setAttr(f"{mp_node}.follow", 1)
        cmds.setAttr(f"{mp_node}.frontAxis", 2)
        cmds.setAttr(f"{mp_node}.upAxis", 1)

        cmds.connectAttr(f"{self.curve}.worldSpace[0]",
                         f"{mp_node}.geometryPath")
        cmds.connectAttr(f"{mp_node}.allCoordinates",
                         f"{root_ctrl}.translate")
        cmds.connectAttr(f"{mp_node}.rotate",
                         f"{root_ctrl}.rotate")
        cmds.setAttr(f"{mp_node}.fractionMode", 1)

        per_frame_distance = self.anim_ctx.locomotion_registry["per_frame_distance"]
        per_frame_fraction = per_frame_distance / curve_length

        accumulated_distance = 0.0
        start_time = cmds.playbackOptions(query=True, minTime=True)
        end_time = cmds.playbackOptions(query=True, maxTime=True)
        frame = start_time
        u_value = 0
        while accumulated_distance <= 1:
            if frame > end_time:
                cmds.playbackOptions(maxTime=frame)
            cmds.setKeyframe(mp_node,
                             attribute="uValue", time=frame, value=u_value)
            accumulated_distance += per_frame_fraction
            u_value = accumulated_distance
            frame += 1

        cmds.keyTangent(mp_node, attribute="uValue",
                        inTangentType="linear", outTangentType="linear")

    def setup_root_motion_path(self):

        root_ctrl = self.rig_ctx.control_registry.get("fk", {}).get("root")

        curve_info = cmds.createNode("curveInfo", name="curveInfo")
        cmds.connectAttr(f"{self.curve}.worldSpace[0]",
                         f"{curve_info}.inputCurve")
        self.curve_length = cmds.getAttr(f"{curve_info}.arcLength")

        root_short = root_ctrl.split("|")[-1]
        self.mp_node = cmds.createNode(
            "motionPath", name=f"{root_short}_followPath_MP")
        cmds.setAttr(f"{self.mp_node}.follow", 1)
        cmds.setAttr(f"{self.mp_node}.frontAxis", 2)
        cmds.setAttr(f"{self.mp_node}.upAxis", 1)
        cmds.setAttr(f"{self.mp_node}.fractionMode", 1)

        cmds.connectAttr(f"{self.curve}.worldSpace[0]",
                         f"{self.mp_node}.geometryPath")
        cmds.connectAttr(f"{self.mp_node}.allCoordinates",
                         f"{root_ctrl}.translate")
        cmds.connectAttr(f"{self.mp_node}.rotate",
                         f"{root_ctrl}.rotate")

    def apply_root_motion_path(self, file_name):

        groups = self.anim_ctx.path_registry.get("root_motion_groups")
        per_frame_distance = self.anim_ctx.locomotion_registry["per_frame_distance"]
        per_frame_fraction = per_frame_distance / self.curve_length

        start_time = int(cmds.playbackOptions(query=True, minTime=True))
        end_time = int(cmds.playbackOptions(query=True, maxTime=True))
        start_index = start_time
        last_value = 0
        last_time = start_time
        prev_sample_frame = 0
        for group in groups:

            key_value = self._get_root_motion_keypose_ratio(group)
            closest_time = int(round((key_value - last_value) / per_frame_fraction
                                     )) + last_time
            key_time = self._get_key_time(group, file_name,
                                          closest_time, last_time, prev_sample_frame)

            frame_count = key_time - last_time
            expected_value = per_frame_fraction * frame_count + last_value
            delta = key_value - expected_value
            step = delta / frame_count
            for i, frame in enumerate(range(start_index, key_time)):
                if last_value != 0:
                    i += 1
                base_value = last_value + (i * per_frame_fraction)
                offset = step * i
                new_value = min(base_value + offset, 1.0)
                cmds.setKeyframe("root_followPath_MP", attribute="uValue",
                                 time=frame, value=new_value)
            cmds.setKeyframe("root_followPath_MP", attribute="uValue",
                             time=key_time, value=key_value)

            start_index = key_time + 1
            last_value = key_value
            last_time = key_time
            prev_sample_frame = self.anim_ctx.path_registry[
                "root_motion_sample_frames"][group]
            final_frame = last_time

        if final_frame < end_time:
            cmds.playbackOptions(maxTime=final_frame)
        elif final_frame > end_time:
            cmds.playbackOptions(maxTime=final_frame)

        cmds.hide(cmds.ls("positionMarker*"))

        cmds.keyTangent(self.mp_node, attribute="uValue",
                        inTangentType="linear", outTangentType="linear")

    def _get_root_motion_keypose_ratio(self, group):

        locator = cmds.ls(f"{group}_root_motion_mid_loc")[0]
        curve_shape = cmds.listRelatives(
            "rootMotionTrajectory_CRV", shapes=True)[0]

        npc = cmds.createNode("nearestPointOnCurve")
        cmds.connectAttr(f"{curve_shape}.worldSpace[0]",
                         f"{npc}.inputCurve")
        pos = cmds.xform(locator, query=True,
                         worldSpace=True, translation=True)
        cmds.setAttr(f"{npc}.inPosition", *pos)
        u = cmds.getAttr(f"{npc}.parameter")

        arc_node = cmds.createNode("arcLengthDimension")
        cmds.connectAttr(f"{curve_shape}.worldSpace[0]",
                         f"{arc_node}.nurbsGeometry")
        cmds.setAttr(f"{arc_node}.uParamValue", u)
        current_length = cmds.getAttr(f"{arc_node}.arcLength")

        curve_info = cmds.createNode("curveInfo")
        cmds.connectAttr(f"{curve_shape}.worldSpace[0]",
                         f"{curve_info}.inputCurve")
        total_length = cmds.getAttr(f"{curve_info}.arcLength")

        ratio = current_length / total_length
        ratio = min(ratio, 1.0)

        arc_transform = cmds.listRelatives(arc_node, parent=True)[0]
        cmds.delete(npc, arc_transform, curve_info)

        return ratio

    def _get_key_time(self, group, file_name,
                      closest_time, last_time, prev_sample_frame):

        sample_frame = self.anim_ctx.path_registry.get(
            "root_motion_sample_frames")[group]

        _, loop_length = self.anim_ctx.retarget_time_registry[file_name]
        loop_offset = round(
            (closest_time - last_time - sample_frame) / loop_length)
        key_time = sample_frame + loop_offset * loop_length + last_time
        key_time -= prev_sample_frame

        return int(key_time)


RigHelpers = rig_schema.RigHelpers
Animhelpers = animation_runtime.Animhelpers
RIG_CTX = rig_schema.RIG_CTX
ANIM_CTX = animation_runtime.ANIM_CTX
UE5_SCHEMA = rig_schema.UE5_SCHEMA
