

import maya.cmds as cmds

from rig import rig_schema


class HeadRig:

    @staticmethod
    def build_head_fk_deform_drivers():

        schema = UE5_SCHEMA.get("head", {})

        constraint_system = RigHelpers.get_or_create_group_chain(
            "Group", "driving_system", "constraints")

        fk_ctrls = RIG_CTX.control_registry.get("fk", {})

        deform_joints = RIG_CTX.joint_registry.get("deform", {})

        for side, side_dict in schema.items():

            chain_group = cmds.group(
                empty=True, name=f"constraint_head_{side}_GRP",
                parent=constraint_system)

            for limb_name, chain in side_dict.items():
                for joint_name in chain:

                    fk_ctrl = fk_ctrls.get(joint_name)
                    deform_joint = deform_joints.get(joint_name)

                    constraint = cmds.parentConstraint(
                        fk_ctrl, deform_joint)

                    cmds.parent(constraint, chain_group)


RigHelpers = rig_schema.RigHelpers
RIG_CTX = rig_schema.RIG_CTX
UE5_SCHEMA = rig_schema.UE5_SCHEMA
