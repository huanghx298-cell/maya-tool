

import maya.cmds as cmds


class AnimContext:

    def __init__(self):

        self.retarget_joint_registry = {}
        self.retarget_time_registry = {}
        self.path_registry = {}
        self.locomotion_registry = {}

        self.animhelper = Animhelpers()

    def clear(self):

        self.retarget_joint_registry = {}
        self.retarget_time_registry = {}
        self.path_registry = {}
        self.locomotion_registry = {}

    def rebuild(self):

        self.retarget_joint_registry = {}
        self.retarget_time_registry = {}
        self.path_registry = {}
        self.locomotion_registry = {}

        self._rebuild_retarget_data()
        self._rebuild_root_motion_refs()
        self._rebuild_root_motion_groups()
        self._rebuild_foot_lock()

    def _rebuild_retarget_data(self):

        animation_group = cmds.ls("animation_group", long=True)
        if animation_group:
            joints = cmds.listRelatives(
                animation_group, allDescendents=True, type="joint", fullPath=True)
            for joint in joints:
                joint_name = joint.split("|")[-1].split(":")[-1]
                namespace = joint.split("|")[-1].split(":")[0]
                file_name = namespace[:-6]
                self.retarget_joint_registry.setdefault(
                    file_name, {})[joint_name] = joint

            meta = cmds.ls(f"{file_name}_group_animMeta", type="network")[0]
            end_time = cmds.getAttr(f"{meta}.animEnd")
            self.retarget_time_registry[file_name] = [0, end_time]

            distance = cmds.getAttr(f"{meta}.perFrameDistance")
            self.locomotion_registry["per_frame_distance"] = distance

    def _rebuild_root_motion_refs(self):

        back_loc = cmds.ls("root_motion_back_loc", long=True) or []
        mid_loc = cmds.ls("root_motion_mid_loc", long=True) or []
        front_loc = cmds.ls("root_motion_front_loc", long=True) or []

        back_loc = back_loc[0] if back_loc else None
        mid_loc = mid_loc[0] if mid_loc else None
        front_loc = front_loc[0] if front_loc else None

        self.path_registry["root_motion_refs"] = (back_loc, mid_loc, front_loc)

    def _rebuild_root_motion_groups(self):

        cache_groups = cmds.ls("root_motion_position_cache", long=True)
        motion_groups = cmds.listRelatives(
            cache_groups, children=True, type="transform") or []
        motion_groups = self.animhelper.get_ordered_groups(motion_groups)
        self.path_registry["root_motion_groups"] = motion_groups

        if motion_groups:
            for group in motion_groups:
                meta_node = cmds.ls(f"{group}_animMeta", type="network")[0]
                frame = cmds.getAttr(f"{meta_node}.sampleFrame")
                self.path_registry.setdefault(
                    "root_motion_sample_frames", {})[group] = frame

    def _rebuild_foot_lock(self):

        foot_lock_locs = cmds.ls("*_footlock_LOC", long=False)
        self.locomotion_registry["foot_lock"] = foot_lock_locs


class Animhelpers:

    def get_ordered_groups(self, groups):

        ordered = []
        for group in groups:
            meta = cmds.ls(f"{group}_animMeta", type="network")[0]
            order = cmds.getAttr(f"{meta}.order")
            ordered.append((group, order))
        ordered.sort(key=lambda x: x[1])

        result = []
        for group, _ in ordered:
            result.append(group)
        return result


ANIM_CTX = AnimContext()
