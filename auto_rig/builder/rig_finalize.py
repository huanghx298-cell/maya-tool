

import maya.cmds as cmds

import data.rig_data as data
import rig.rig_schema as rig_schema

import utils.dag_utils as dag_utils
import utils.transform_utils as transform_utils


def biped_space():

    def spine_arm(key):
        fk_ctrls, ik_ctrls = data.body_ctrl["fk"], data.body_ctrl["ik"]
        fk_ctrl, ik_ctrl = fk_ctrls["spine"][-1], ik_ctrls["spine"][-1]
        spine_fk = dag_utils.group(fk_ctrl, f"fk_{key}_follow_GRP")
        spine_ik = dag_utils.group(ik_ctrl, f"ik_{key}_follow_GRP")
        clav_fk_grp = cmds.listRelatives(fk_ctrls[key][0], p=True, f=True)[0]
        con = cmds.parentConstraint(spine_fk, spine_ik, clav_fk_grp)[0]
        w0_attr = cmds.listAttr(con, string="*W0")[0]
        w1_attr = cmds.listAttr(con, string="*W1")[0]
        md = cmds.ls("spine_IKFKBlend_MD", long=True)[0]
        rev = cmds.ls("spine_IKFKBlend_REV", long=True)[0]
        cmds.connectAttr(f"{md}.outputX", f"{con}.{w0_attr}")
        cmds.connectAttr(f"{rev}.outputX", f"{con}.{w1_attr}")

    def arm_hand(key):
        hand_n = key.replace("arm", "hand")
        fk_ctrls = data.body_ctrl["fk"]
        fk_jnts, ik_jnts = data.body_jnt["fk"], data.body_jnt["ik"]
        arm_fk_jnt, arm_ik_jnt = fk_jnts[key][-1], ik_jnts[key][-1]
        arm_fk_grp = dag_utils.group(arm_fk_jnt, f"fk_{hand_n}_follow_GRP")
        arm_ik_grp = dag_utils.group(arm_ik_jnt, f"ik_{hand_n}_follow_GRP")
        cmds.matchTransform(arm_fk_grp, arm_fk_jnt)
        cmds.matchTransform(arm_ik_grp, arm_ik_jnt)
        transform_utils.to_opm(arm_fk_grp)
        transform_utils.to_opm(arm_ik_grp)
        hand_fk_grp = cmds.listRelatives(
            fk_ctrls[hand_n]["hand"], p=True, f=True)[0]
        ikfk_n = data.body_ctrl["ikfk"][key].split("|")[-1]
        con = cmds.parentConstraint(arm_fk_grp, arm_ik_grp, hand_fk_grp)[0]
        w0_attr = cmds.listAttr(con, string="*W0")[0]
        w1_attr = cmds.listAttr(con, string="*W1")[0]
        md = cmds.ls(f"{ikfk_n}_IKFKBlend_MD", long=True)[0]
        rev = cmds.ls(f"{ikfk_n}_IKFKBlend_REV", long=True)[0]
        cmds.connectAttr(f"{md}.outputX", f"{con}.{w0_attr}")
        cmds.connectAttr(f"{rev}.outputX", f"{con}.{w1_attr}")
        grp = dag_utils.group("constraints", f"constraint_{hand_n}_GRP")
        cmds.parent(con, grp)

    dag_utils.group("group", "driving_system", "constraints")
    for key in ["arm_l", "arm_r"]:
        spine_arm(key)
        arm_hand(key)

    def spine_leg(key):
        fk_ctrls, ik_ctrls = data.body_ctrl["fk"], data.body_ctrl["ik"]
        ik_jnts = data.body_jnt["ik"]
        spine_fk_ctrl, spine_ik_ctrl = fk_ctrls["spine"][0], ik_ctrls["spine"][0]
        spine_fk = dag_utils.group(spine_fk_ctrl, f"fk_{key}_follow_GRP")
        spine_ik = dag_utils.group(spine_ik_ctrl, f"ik_{key}_follow_GRP")
        leg_fk_ctrl = cmds.listRelatives(fk_ctrls[key][0], p=True, f=True)[0]
        leg_ik_jnt = cmds.listRelatives(ik_jnts[key][0], p=True, f=True)[0]
        md = cmds.ls("spine_IKFKBlend_MD", long=True)[0]
        rev = cmds.ls("spine_IKFKBlend_REV", long=True)[0]
        for target in [leg_fk_ctrl, leg_ik_jnt]:
            con = cmds.parentConstraint(spine_fk, spine_ik, target)[0]
            w0_attr = cmds.listAttr(con, string="*W0")[0]
            w1_attr = cmds.listAttr(con, string="*W1")[0]
            cmds.connectAttr(f"{md}.outputX", f"{con}.{w0_attr}")
            cmds.connectAttr(f"{rev}.outputX", f"{con}.{w1_attr}")

    for key in ["leg_l", "leg_r"]:
        spine_leg(key)

    def root_ik_fk_ctrl():
        root_ctrl = data.body_ctrl["root_ctrl"]
        root_grp = dag_utils.group(root_ctrl, f"root_follow_GRP")
        for system in ["FKSystem", "IKSystem", "IKFKSystem"]:
            grp = dag_utils.group("group", "controls", system)
            cmds.parentConstraint(root_grp, grp)

    def spine_ik_ctrl():
        ctrls = data.body_ctrl["ik"]["spine"]
        start, mid, end = ctrls
        start_grp = dag_utils.group(start, "ik_spine_02_start_follow_GRP")
        end_grp = dag_utils.group(end, "ik_spine_02_end_follow_GRP")
        ctrls_grp = cmds.listRelatives(mid, p=True, f=True)[0]
        mid_grp = dag_utils.group(ctrls_grp, f"ik_spine_02_offset_GRP")
        mid = dag_utils.parent(mid, mid_grp)
        data.body_ctrl["ik"]["spine"][1] = mid
        con = cmds.parentConstraint(start_grp, end_grp, mid_grp)[0]
        w0 = cmds.listAttr(con, string="*W0")[0]
        w1 = cmds.listAttr(con, string="*W1")[0]
        cmds.setAttr(f"{con}.{w0}", 0.5)
        cmds.setAttr(f"{con}.{w1}", 0.5)

    root_ik_fk_ctrl()
    spine_ik_ctrl()


def biped_twistss():

    def limb_data(key, suffix):
        limb_n = "arm" if key.startswith(("arm", "hand")) else "leg"
        limb_key = f"{limb_n}_{key[-1]}"
        base_n, *_, end_n = rig_schema.UE5_BODY["twist"][key.rsplit("_", 1)[0]]
        base_i = rig_schema.UE5_BODY[limb_n].index(base_n)
        end_i = rig_schema.UE5_BODY[limb_n].index(end_n)
        jnts = data.body_jnt[suffix][limb_key]
        ikfk_n = data.body_ctrl["ikfk"][limb_key].rsplit("|", 1)[-1]
        return jnts[base_i], jnts[end_i], ikfk_n

    def ikfk_constraint(ikfk_n, *constraints):
        md = cmds.ls(f"{ikfk_n}_IKFKBlend_MD", long=True)[0]
        rev = cmds.ls(f"{ikfk_n}_IKFKBlend_REV", long=True)[0]
        for con in constraints:
            w0 = cmds.listAttr(con, st="*W0")[0]
            w1 = cmds.listAttr(con, st="*W1")[0]
            cmds.connectAttr(f"{md}.outputX", f"{con}.{w0}")
            cmds.connectAttr(f"{rev}.outputX", f"{con}.{w1}")

    def ikhandle(key, suffix):
        _, follow_01, follow_02, loc = data.body_jnt["twist_driver"][key][suffix]
        _, end_jnt, _ = limb_data(key, suffix)
        ikh = cmds.ikHandle(sj=follow_01, ee=follow_02, sol="ikRPsolver",
                            n=f"{key}_{suffix}_follow_IKH")[0]
        for axis in "XYZ":
            cmds.setAttr(f"{ikh}.poleVector{axis}", 0)
        ikh = dag_utils.parent(ikh, end_jnt)
        cmds.matchTransform(ikh, end_jnt)
        dag_utils.parent(loc, follow_01)

    def twist_joint(key, suffix):
        base_jnt, end_jnt, ikfk_n = limb_data(key, suffix)
        twist_jnt, *_, loc = data.body_jnt["twist_driver"][key][suffix]
        aim_x = 1 if key in ("arm_l", "leg_r") else -1
        cmds.pointConstraint(base_jnt, twist_jnt)[0]
        cmds.aimConstraint(end_jnt, twist_jnt, aim=(aim_x, 0, 0),
                           u=(0, 1, 0), wut="object", wuo=loc)[0]

    for key in ("arm_l", "arm_r"):
        for suffix in ("fk", "ik"):
            ikhandle(key, suffix)
            twist_joint(key, suffix)

    def update_deform_joint(key):
        fk_twist = data.body_jnt["twist_driver"][key]["fk"][0]
        ik_twist = data.body_jnt["twist_driver"][key]["ik"][0]
        *_, ikfk_n = limb_data(key, "fk")
        jnt = data.body_jnt["deform"]["twist"][key][0]
        con = cmds.listConnections(jnt, d=False, type="parentConstraint")[0]
        for axis in "XYZ":
            cmds.disconnectAttr(f"{con}.constraintRotate{axis}",
                                f"{jnt}.rotate{axis}")
        con = cmds.orientConstraint(fk_twist, ik_twist, jnt)[0]
        ikfk_constraint(ikfk_n, con)

    def twist_distribution(key):
        _, twist_01, twist_02, _ = data.body_jnt["deform"]["twist"][key]
        # twist_jnt = data.body_jnt["twist_driver"][key][0]
        twist_jnt, *_, loc = data.body_jnt["twist_driver"][key]["ik"]
        md = cmds.createNode("multiplyDivide", n=f"{key}_twistDistribution_MD")
        cmds.setAttr(f"{md}.input2X", 0.66)
        cmds.setAttr(f"{md}.input2Y", 0.33)
        cmds.connectAttr(f"{twist_jnt}.rotateX", f"{md}.input1X")
        cmds.connectAttr(f"{twist_jnt}.rotateX", f"{md}.input1Y")
        cmds.connectAttr(f"{md}.outputX", f"{twist_02}.rotateX")
        cmds.connectAttr(f"{md}.outputY", f"{twist_01}.rotateX")

    for key in ("arm_l", "arm_r"):
        update_deform_joint(key)
        # twist_distribution(key)


def biped_twist():

    def limb_data(key):
        limb_n = "arm" if key.startswith(("arm", "hand")) else "leg"
        limb_key = f"{limb_n}_{key[-1]}"
        base_n, *_, end_n = rig_schema.UE5_BODY["twist"][key.rsplit("_", 1)[0]]
        base_i = rig_schema.UE5_BODY[limb_n].index(base_n)
        end_i = rig_schema.UE5_BODY[limb_n].index(end_n)
        fk = data.body_jnt["fk"][limb_key]
        ik = data.body_jnt["ik"][limb_key]
        ikfk_n = data.body_ctrl["ikfk"][limb_key].rsplit("|", 1)[-1]
        return (fk[base_i], fk[end_i], ik[base_i], ik[end_i], ikfk_n)

    def ikfk_constraint(ikfk_n, *constraints):
        md = cmds.ls(f"{ikfk_n}_IKFKBlend_MD", long=True)[0]
        rev = cmds.ls(f"{ikfk_n}_IKFKBlend_REV", long=True)[0]
        for con in constraints:
            w0 = cmds.listAttr(con, st="*W0")[0]
            w1 = cmds.listAttr(con, st="*W1")[0]
            cmds.connectAttr(f"{md}.outputX", f"{con}.{w0}")
            cmds.connectAttr(f"{rev}.outputX", f"{con}.{w1}")

    def ikhandle(key):
        _, follow_01, follow_02, loc, _ = data.body_jnt["twist_driver"][key]
        _, _, _, ik_end, _ = limb_data(key)
        ikh = cmds.ikHandle(sj=follow_01, ee=follow_02, sol="ikRPsolver",
                            n=f"{key}_follow_IKH")[0]
        for axis in "XYZ":
            cmds.setAttr(f"{ikh}.poleVector{axis}", 0)
        twist_grp = cmds.listRelatives(follow_01, p=True, f=True)[0]
        grp = dag_utils.group(twist_grp, f"{key}_follow_IKH_offset_GRP")
        ikh = dag_utils.parent(ikh, grp)
        cmds.matchTransform(grp, ik_end)
        cmds.matchTransform(ikh, grp)
        loc = dag_utils.parent(loc, follow_01)
        data.body_jnt["twist_driver"][key][3] = loc

    def twist_joint(key):
        fk_base, fk_end, ik_base, ik_end, ikfk_n = limb_data(key)
        twist_jnt, *_, loc, _ = data.body_jnt["twist_driver"][key]
        grp = cmds.listRelatives(twist_jnt, p=True, f=True)[0]
        ikh = cmds.listRelatives(grp, ad=True, type="ikHandle", f=True)[0]
        ikh_grp = cmds.listRelatives(ikh, p=True, f=True)[0]
        aim_x = 1 if key in ("arm_l", "leg_r") else -1
        point_con = cmds.pointConstraint(fk_base, ik_base, twist_jnt)[0]
        aim_con = cmds.aimConstraint(fk_end, ik_end, twist_jnt, aim=(aim_x, 0, 0),
                                     u=(0, 1, 0), wut="object", wuo=loc)[0]
        ikh_con = cmds.pointConstraint(fk_end, ik_end, ikh_grp)[0]
        ikfk_constraint(ikfk_n, point_con, aim_con, ikh_con)

    for key in ("arm_l", "arm_r"):
        ikhandle(key)
        twist_joint(key)

    def update_deform_joint(key):
        twist_jnt = data.body_jnt["twist_driver"][key][0]
        jnt = data.body_jnt["deform"]["twist"][key][0]
        con = cmds.listConnections(jnt, d=False, type="parentConstraint")[0]
        for axis in "XYZ":
            cmds.disconnectAttr(f"{con}.constraintRotate{axis}",
                                f"{jnt}.rotate{axis}")
        cmds.orientConstraint(twist_jnt, jnt)

    def twist_distributions(key):
        _, twist_01, twist_02, _ = data.body_jnt["deform"]["twist"][key]
        # twist_jnt = data.body_jnt["twist_driver"][key][0]
        twist_jnt, *_, loc = data.body_jnt["twist_driver"][key]["ik"]
        md = cmds.createNode("multiplyDivide", n=f"{key}_twistDistribution_MD")
        cmds.setAttr(f"{md}.input2X", 0.66)
        cmds.setAttr(f"{md}.input2Y", 0.33)
        cmds.connectAttr(f"{twist_jnt}.rotateX", f"{md}.input1X")
        cmds.connectAttr(f"{twist_jnt}.rotateX", f"{md}.input1Y")
        cmds.connectAttr(f"{md}.outputX", f"{twist_02}.rotateX")
        cmds.connectAttr(f"{md}.outputY", f"{twist_01}.rotateX")

    def twist_distribution(key):
        twist_delta = data.body_jnt["twist_driver"][key][-1]
        ik_jnt = data.body_jnt["ik"][key][1]
        _, twist_01, twist_02, _ = data.body_jnt["deform"]["twist"][key]

        # IK matrix inverse
        ik_inv = cmds.createNode("inverseMatrix", n=f"{key}_twist_IK_INV")
        cmds.connectAttr(f"{ik_jnt}.worldMatrix[0]", f"{ik_inv}.inputMatrix")
        # delta = ik.inverse() * twist_delta
        delta_mm = cmds.createNode("multMatrix", n=f"{key}_twistDelta_MM")
        cmds.connectAttr(f"{ik_inv}.outputMatrix", f"{delta_mm}.matrixIn[0]")
        cmds.connectAttr(f"{twist_delta}.worldMatrix[0]",
                         f"{delta_mm}.matrixIn[1]")
        # matrix -> rotate XYZ
        delta_dm = cmds.createNode("decomposeMatrix", n=f"{key}_twistDelta_DM")
        cmds.connectAttr(f"{delta_mm}.matrixSum", f"{delta_dm}.inputMatrix")
        cmds.setAttr(f"{delta_dm}.inputRotateOrder", 3)
        # 2/3
        twist_01_md = cmds.createNode(
            "multiplyDivide", n=f"{key}_l_twist01_MD")
        cmds.setAttr(f"{twist_01_md}.input2X", -2.0 / 3.0)
        cmds.connectAttr(f"{delta_dm}.outputRotateX", f"{twist_01_md}.input1X")
        cmds.connectAttr(f"{twist_01_md}.outputX", f"{twist_02}.rotateX")
        # 1/3
        twist_02_md = cmds.createNode(
            "multiplyDivide", n=f"{key}_l_twist02_MD")
        cmds.setAttr(f"{twist_02_md}.input2X", -1.0 / 3.0)
        cmds.connectAttr(f"{delta_dm}.outputRotateX", f"{twist_02_md}.input1X")
        cmds.connectAttr(f"{twist_02_md}.outputX", f"{twist_01}.rotateX")

    for key in ("arm_l", "arm_r"):
        update_deform_joint(key)
        twist_distribution(key)
