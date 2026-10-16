

import maya.cmds as cmds

from rig import rig_schema
from anim import animation_runtime


class AnimationLocomotion:

    def __init__(self):

        self.rig_ctx = RIG_CTX
        self.anim_ctx = ANIM_CTX

    def create_pose_reference(self):

        locator_group = self.anim_ctx.path_registry["current_root_motion_group"]

        node = cmds.ls("SKM_Manny_Simple_LOD2", long=True)[0]
        node = cmds.duplicate(node, name=f"{locator_group}_pose_reference")[0]
        cmds.parent(node, locator_group)
        cmds.delete(node, constructionHistory=True)

        attrs = cmds.listAttr(node, locked=True)
        for attr in attrs:
            cmds.setAttr(f"{node}.{attr}", lock=False)
        cmds.setAttr(f"{node}.rotateX", -90)

        cmds.xform(node, centerPivots=True)
        cmds.makeIdentity(node, apply=True, translate=True,
                          rotate=True, scale=True)

    def locomotion_base_distance(self, file_name):

        schema = UE5_SCHEMA.get("limb", {})
        motion_distance_group = RigHelpers.get_or_create_group_chain(
            "retarget_group", "locomotionsystem", "MotionDistance_GRP")
        ik_ctrls = self.rig_ctx.control_registry.get("ik", {})

        retarget_joints = self.anim_ctx.retarget_joint_registry.get(
            f"{file_name}", {})

        foot_distances = {}
        start_frame, end_frame = self.anim_ctx.retarget_time_registry.get(
            f"{file_name}")
        for side, side_dict in schema.items():
            for limb_name, chain in side_dict.items():
                if limb_name == "upperarm":
                    continue
                ik_ctrl = ik_ctrls.get(chain[2])
                retarget_joint = retarget_joints.get(chain[2])

                follow_group = cmds.group(
                    empty=True, name=f"{chain[2]}_DistFollow_GRP",
                    parent=motion_distance_group)
                cmds.matchTransform(follow_group, ik_ctrl, position=True)
                cmds.parentConstraint(retarget_joint, follow_group,
                                      maintainOffset=True, skipRotate=("x", "y", "z"))

                start_loc = cmds.spaceLocator(
                    name=f"{chain[2]}_DistStart_LOC")[0]
                cmds.parent(start_loc, motion_distance_group)
                cmds.matchTransform(start_loc, ik_ctrl,
                                    positionX=True, positionY=True)
                cmds.move(0, 0, -80, start_loc,
                          relative=True, objectSpace=True)
                cmds.parentConstraint(follow_group, start_loc,
                                      maintainOffset=True,
                                      skipRotate=("x", "y", "z"),
                                      skipTranslate=("z"))

                end_loc = cmds.spaceLocator(
                    name=f"{chain[2]}_DistEnd_LOC")[0]
                cmds.parent(end_loc, follow_group)
                cmds.matchTransform(end_loc, ik_ctrl, position=True)

                dist_node = cmds.createNode(
                    "distanceBetween", name=f"{chain[2]}_DistanceBetween")
                cmds.connectAttr(
                    f"{start_loc}.worldPosition[0]",
                    f"{dist_node}.point1")
                cmds.connectAttr(
                    f"{end_loc}.worldPosition[0]",
                    f"{dist_node}.point2")

                frame_distances = []
                for frame in range(int(start_frame), int(end_frame) + 1):
                    cmds.currentTime(frame, edit=True)
                    dist = cmds.getAttr(f"{dist_node}.distance")
                    frame_distances.append(dist)
                motion_distance = max(frame_distances) - min(frame_distances)

                foot_distances[side] = motion_distance

        left_distance = foot_distances.get("l", [])
        right_distance = foot_distances.get("r", [])
        per_frame_distance = (left_distance + right_distance) / end_frame
        self.anim_ctx.locomotion_registry["per_frame_distance"] = per_frame_distance
        meta_node = cmds.ls(f"{file_name}_group_animMeta", type="network")[0]
        cmds.addAttr(meta_node, ln="perFrameDistance", at="double")
        cmds.setAttr(f"{meta_node}.perFrameDistance", per_frame_distance)

        cmds.delete(motion_distance_group)

    def locomotion_setup_foot_lock_reference(self):

        schema = UE5_SCHEMA.get("limb", {})
        group = RigHelpers.get_or_create_group_chain(
            "retarget_group", "locomotionsystem", "footlock_GRP")
        ik_ctrls = self.rig_ctx.control_registry.get("ik", {})

        cmds.currentTime(-1)
        all_locs = []
        for side, side_dict in schema.items():
            for limb_name, chain in side_dict.items():
                if limb_name == "upperarm":
                    continue

                ik_ctrl = ik_ctrls.get(chain[2])

                offset_loc = cmds.spaceLocator(
                    name=f"{chain[2]}_footlock_offset_LOC")[0]
                cmds.parent(offset_loc, ik_ctrl)
                cmds.matchTransform(offset_loc, ik_ctrl, position=True)

                loc = cmds.spaceLocator(
                    name=f"{chain[2]}_footlock_LOC")[0]
                cmds.matchTransform(loc, ik_ctrl, position=True)
                cmds.parentConstraint(offset_loc, loc,
                                      maintainOffset=False, skipRotate=("x", "z"))
                cmds.parent(loc, group)

                all_locs.append(loc)

        self.anim_ctx.locomotion_registry["foot_lock"] = all_locs

    def locomotion_get_foot_lock_ranges(self):

        locs = self.anim_ctx.locomotion_registry.get("foot_lock", [])

        start_time = int(cmds.playbackOptions(query=True, minTime=True))
        end_time = int(cmds.playbackOptions(query=True, maxTime=True))

        threshold = 0.5
        min_frames = 3

        result = {loc: [] for loc in locs}
        current_ranges = {loc: None for loc in locs}
        prev_y = {loc: None for loc in locs}

        for frame in range(start_time, end_time + 1):
            for loc in locs:
                y = cmds.getAttr(f"{loc}.translateY", time=frame)
                if prev_y[loc] is None:
                    prev_y[loc] = y
                    continue

                delta = abs(y - prev_y[loc])
                if delta < threshold:
                    if current_ranges[loc] is None:
                        current_ranges[loc] = [frame - 1, frame]
                    else:
                        current_ranges[loc][1] = frame
                else:
                    if current_ranges[loc]:
                        length = current_ranges[loc][1] - \
                            current_ranges[loc][0] + 1
                        if length >= min_frames:
                            result[loc].append(tuple(current_ranges[loc]))
                        current_ranges[loc] = None

                prev_y[loc] = y

        for loc in locs:
            if current_ranges[loc]:
                length = current_ranges[loc][1] - current_ranges[loc][0] + 1
                if length >= min_frames:
                    result[loc].append(tuple(current_ranges[loc]))

        self.anim_ctx.locomotion_registry["foot_lock_ranges"] = result

    def foot_ik_lock(self):

        ik_ctrls = self.rig_ctx.control_registry.get("ik", {})

        result = self.anim_ctx.locomotion_registry["foot_lock_ranges"]
        print(result)

        left_ranges = result["foot_l_footlock_LOC"]
        right_ranges = result["foot_r_footlock_LOC"]

        start, end = left_ranges[0]

        ik_ctrl_l = ik_ctrls.get("foot_l")
        ik_ctrl_r = ik_ctrls.get("foot_r")

        lock_loc_l = cmds.spaceLocator(name=f"foot_l_lock_LOC")[0]
        lock_loc_r = cmds.spaceLocator(name=f"foot_r_lock_LOC")[0]

        attrs = [
            f"{ik_ctrl_l}.translateX", f"{ik_ctrl_r}.translateX",
            f"{ik_ctrl_l}.translateY", f"{ik_ctrl_r}.translateY",
            f"{ik_ctrl_l}.translateZ", f"{ik_ctrl_r}.translateZ",
            # f"{ik_ctrl_l}.rotateX", f"{ik_ctrl_r}.rotateX",
            # f"{ik_ctrl_l}.rotateY", f"{ik_ctrl_r}.rotateY",
            # f"{ik_ctrl_l}.rotateZ", f"{ik_ctrl_r}.rotateZ",
        ]
        layer = "foot_lock_layer"
        cmds.animLayer(layer, attribute=attrs)

        start_time = int(cmds.playbackOptions(query=True, minTime=True))
        end_time = int(cmds.playbackOptions(query=True, maxTime=True))

        legs_data = [
            {
                "ik_ctrl": ik_ctrl_l,
                "ranges": left_ranges,
                "lock_loc": lock_loc_l,
                "layer": layer,
            },
            {
                "ik_ctrl": ik_ctrl_r,
                "ranges": right_ranges,
                "lock_loc": lock_loc_r,
                "layer": layer,
            }
        ]

        for leg in legs_data:
            leg["start_frames"] = {start for start, end in leg["ranges"]}
            leg["release_frames"] = {end + 10 for start, end in leg["ranges"]}

            range_frames = set()
            for start, end in leg["ranges"]:
                range_frames.update(range(start, end + 1))
            leg["range_frames"] = range_frames

        cmds.refresh(suspend=True)
        for frame in range(start_time, end_time + 1):

            cmds.currentTime(frame)

            for leg in legs_data:
                ik_ctrl = leg["ik_ctrl"]
                lock_loc = leg["lock_loc"]
                layer = leg["layer"]

                if frame in leg["start_frames"]:
                    cmds.matchTransform(lock_loc, ik_ctrl,
                                        position=True, rotation=True)

                if frame in leg["range_frames"]:
                    cmds.matchTransform(ik_ctrl, lock_loc,
                                        position=True, rotation=True)
                    cmds.setKeyframe(ik_ctrl,
                                     attribute="translate", animLayer=layer)
                    # cmds.setKeyframe(ik_ctrl,
                    # attribute="rotate", animLayer=layer)

                if frame in leg["release_frames"]:
                    cmds.animLayer(layer, edit=True, mute=True)
                    cmds.setKeyframe(ik_ctrl,
                                     attribute="translate", animLayer=layer)
                    # cmds.setKeyframe(ik_ctrl,
                    # attribute="rotate", animLayer=layer)
                    cmds.animLayer(layer, edit=True, mute=False)

        cmds.refresh(suspend=False)


RigHelpers = rig_schema.RigHelpers
RIG_CTX = rig_schema.RIG_CTX
ANIM_CTX = animation_runtime.ANIM_CTX
UE5_SCHEMA = rig_schema.UE5_SCHEMA
