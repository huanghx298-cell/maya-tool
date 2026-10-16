

import maya.cmds as cmds
import maya.api.OpenMaya as om

import data.rig_data as data

import utils.dag_utils as dag_utils
import utils.transform_utils as transform_utils


def biped_limb():

    def limb_fk_ctrl_joint(key):
        ctrls = data.body_ctrl["fk"][key]
        jnts = data.body_jnt["fk"][key]
        for ctrl, jnt in zip(ctrls, jnts):
            cmds.parentConstraint(ctrl, jnt)

    def limb_ik_ctrl_joint(key):
        ctrls = data.body_ctrl["ik"][key]
        jnts = data.body_jnt["ik"][key]
        pole_ctrl, ik_ctrl = ctrls
        if key.startswith("arm"):
            start_i, mid_i, end_i = 1, 2, 3
        else:
            start_i, mid_i, end_i = 0, 1, 2
        start_joint = jnts[start_i]
        end_joint = jnts[end_i]
        end_name = end_joint.split("|")[-1]
        ik_handle = cmds.ikHandle(
            sj=start_joint, ee=end_joint,
            sol="ikRPsolver", n=f"{end_name}_IKH")[0]
        cmds.poleVectorConstraint(pole_ctrl, ik_handle)
        cmds.parent(ik_handle, ik_ctrl)

    for key in ["arm_l", "arm_r", "leg_l", "leg_r"]:
        limb_fk_ctrl_joint(key)
        limb_ik_ctrl_joint(key)

    def update_clavicle_ik_ctrl_joint(key):
        fk_ctrl = data.body_ctrl["fk"][key][0]
        fk_jnt = data.body_jnt["fk"][key][0]
        ik_jnt = data.body_jnt["ik"][key][0]
        cmds.parentConstraint(fk_ctrl, fk_jnt)
        cmds.parentConstraint(fk_ctrl, ik_jnt)

    for key in ["arm_l", "arm_r"]:
        update_clavicle_ik_ctrl_joint(key)


def biped_spine():

    def spine_fk_ctrl_joint():
        ctrls = data.body_ctrl["fk"]["spine"]
        jnts = data.body_jnt["fk"]["spine"]
        for ctrl, jnt in zip(ctrls, jnts):
            cmds.parentConstraint(ctrl, jnt)

    def spine_ik_ctrl_joint():
        cv = data.body_ctrl["ik"]["spine_curve"]
        ctrls = data.body_ctrl["ik"]["spine"]
        ik_jnts = data.body_jnt["ik"]["spine"]
        follow_jnts = data.body_jnt["ik"]["spine_follow"]
        driver_jnts = data.body_jnt["ik"]["spine_driver"]
        for ctrl, jnt in zip(ctrls, driver_jnts):
            cmds.parentConstraint(ctrl, jnt)
        cmds.skinCluster(driver_jnts, cv, toSelectedBones=True,
                         maximumInfluences=1, normalizeWeights=1,
                         name="spine_curve_skinCluster")[0]
        for ik_jnt, follow_jnt in zip(ik_jnts, follow_jnts):
            cmds.parentConstraint(follow_jnt, ik_jnt)
        for ctrl, jnt in zip((ctrls[0], ctrls[-1]), (follow_jnts[0], follow_jnts[-1])):
            cmds.orientConstraint(ctrl, jnt, mo=True)

    def ik_rotation_distribution():
        cv = data.body_ctrl["ik"]["spine_curve"]
        ctrls = data.body_ctrl["ik"]["spine"]
        driver_locs = data.body_ctrl["ik"]["spine_driver_loc"]
        locs_u, ctrls_u = [], []
        space = om.MSpace.kWorld
        cv_fn = om.MFnNurbsCurve(om.MSelectionList().add(cv).getDagPath(0))
        for loc, ctrl in zip(driver_locs, ctrls):
            loc_pos = om.MPoint(cmds.xform(loc, q=True, ws=True, t=True))
            ctrl_pos = om.MPoint(cmds.xform(ctrl, q=True, ws=True, t=True))
            loc_u = cv_fn.closestPoint(loc_pos, space=space)[1]
            ctrl_u = cv_fn.closestPoint(ctrl_pos, space=space)[1]
            locs_u.append(loc_u)
            ctrls_u.append(ctrl_u)
        constraints = []
        for i in range(len(ctrls) - 1):
            left_ctrl, right_ctrl = ctrls[i], ctrls[i + 1]
            left_u, right_u = ctrls_u[i], ctrls_u[i + 1]
            for target, target_u in zip(driver_locs, locs_u):
                if not (left_u <= target_u <= right_u):
                    continue
                ratio = (target_u - left_u) / (right_u - left_u)
                constraints.append({
                    "target": target,
                    "left_ctrl": left_ctrl,
                    "right_ctrl": right_ctrl,
                    "left_weight": 1 - ratio,
                    "right_weight": ratio,
                })
        for item in constraints:
            constraint = cmds.parentConstraint(
                item["left_ctrl"], item["right_ctrl"], item["target"], mo=True)[0]
            w0_attr = cmds.listAttr(constraint, string="*W0")[0]
            w1_attr = cmds.listAttr(constraint, string="*W1")[0]
            cmds.setAttr(f"{constraint}.{w0_attr}", item["left_weight"])
            cmds.setAttr(f"{constraint}.{w1_attr}", item["right_weight"])

    spine_fk_ctrl_joint()
    spine_ik_ctrl_joint()
    ik_rotation_distribution()


def biped_blend():

    def limb_ikfk_deform():

        def ikfk_deform(key):
            grp = dag_utils.group("constraints", f"constraint_{key}_GRP")
            n = data.body_ctrl["ikfk"][key].split("|")[-1]
            md = cmds.createNode("multiplyDivide", n=f"{n}_IKFKBlend_MD")
            cmds.setAttr(f"{md}.input2X", 0.1)
            cmds.connectAttr(f"{n}.IKFKBlend", f"{md}.input1X")
            rev = cmds.createNode("reverse", n=f"{n}_IKFKBlend_REV")
            cmds.connectAttr(f"{md}.outputX", f"{rev}.inputX")
            for fk_jnt, ik_jnt, deform_jnt in zip(
                    data.body_jnt["fk"][key],
                    data.body_jnt["ik"][key],
                    data.body_jnt["deform"][key]):
                con = cmds.parentConstraint(fk_jnt, ik_jnt, deform_jnt)[0]
                w0_attr = cmds.listAttr(con, string="*W0")[0]
                w1_attr = cmds.listAttr(con, string="*W1")[0]
                cmds.connectAttr(f"{md}.outputX", f"{con}.{w0_attr}")
                cmds.connectAttr(f"{rev}.outputX", f"{con}.{w1_attr}")
                cmds.parent(con, grp)
            for fk_ctrl in data.body_ctrl["fk"][key]:
                cmds.connectAttr(f"{md}.outputX", f"{fk_ctrl}.visibility")
            for ik_ctrl in data.body_ctrl["ik"][key]:
                cmds.connectAttr(f"{rev}.outputX", f"{ik_ctrl}.visibility")

        for key in ["arm_l", "arm_r", "leg_l", "leg_r"]:
            ikfk_deform(key)

    def spine_ikfk_deform():
        grp = dag_utils.group("constraints", f"constraint_spine_GRP")
        ikfk_ctrl_n = data.body_ctrl["ikfk"]["spine"].split("|")[-1]
        md = cmds.createNode("multiplyDivide", n="spine_IKFKBlend_MD")
        cmds.setAttr(f"{md}.input2X", 0.1)
        cmds.connectAttr(f"{ikfk_ctrl_n}.IKFKBlend", f"{md}.input1X")
        rev = cmds.createNode("reverse", n="spine_IKFKBlend_REV")
        cmds.connectAttr(f"{md}.outputX", f"{rev}.inputX")
        for fk_jnt, ik_jnt, deform_jnt in zip(
                data.body_jnt["fk"]["spine"],
                data.body_jnt["ik"]["spine"],
                data.body_jnt["deform"]["spine"]):
            con = cmds.parentConstraint(fk_jnt, ik_jnt, deform_jnt)[0]
            w0_attr = cmds.listAttr(con, string="*W0")[0]
            w1_attr = cmds.listAttr(con, string="*W1")[0]
            cmds.connectAttr(f"{md}.outputX", f"{con}.{w0_attr}")
            cmds.connectAttr(f"{rev}.outputX", f"{con}.{w1_attr}")
            cmds.parent(con, grp)
        for fk_ctrl in data.body_ctrl["fk"]["spine"]:
            cmds.connectAttr(f"{md}.outputX", f"{fk_ctrl}.visibility")
        for ik_ctrl in data.body_ctrl["ik"]["spine"]:
            cmds.connectAttr(f"{rev}.outputX", f"{ik_ctrl}.visibility")

    dag_utils.group("group", "driving_system", "constraints")
    limb_ikfk_deform()
    spine_ikfk_deform()


def biped_hand():

    def spread(key):
        hand_ctrl = data.body_ctrl["fk"][key]["hand"]
        finger_ctrls = data.body_ctrl["fk"][key]
        cmds.addAttr(hand_ctrl, longName="Spread", attributeType="double",
                     minValue=-5, maxValue=10, defaultValue=0, keyable=True)
        for attr in ("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"):
            cmds.setAttr(f"{hand_ctrl}.{attr}", lock=True,
                         keyable=False, channelBox=False)
        weights = {"index":  1.0, "middle": 0.0, "ring": -1.0, "pinky": -2.0}
        for finger in ["index", "middle", "ring", "pinky"]:
            ctrl = finger_ctrls[finger][0]
            weight = weights[finger]
            md = cmds.createNode(
                "multiplyDivide", n=f"{key}_{finger}_Spread_MD")
            cmds.setAttr(f"{md}.input2X", weight)
            cmds.connectAttr(f"{hand_ctrl}.Spread", f"{md}.input1X")
            cmds.connectAttr(f"{md}.outputX", f"{ctrl}.rotateY")

    def curl(key):
        hand_ctrl = data.body_ctrl["fk"][key]["hand"]
        finger_ctrls = data.body_ctrl["fk"][key]
        curl_weights = {
            "thumb": [4, 8, 8],
            "index": [9, 9, 9],
            "middle": [9, 9, 9],
            "ring": [9, 9, 9],
            "pinky": [9, 9, 9],
        }
        for finger in ["thumb", "index", "middle", "ring", "pinky"]:
            ctrls = finger_ctrls[finger]
            cmds.addAttr(hand_ctrl, longName=f"{finger}_Curl", attributeType="double",
                         minValue=-2, maxValue=10, defaultValue=0, keyable=True)
            md = cmds.createNode("multiplyDivide", n=f"{key}_{finger}_Curl_MD")
            for axis, ctrl, weight in zip("XYZ", ctrls, curl_weights[finger]):
                cmds.setAttr(f"{md}.input2{axis}", weight)
                cmds.connectAttr(
                    f"{hand_ctrl}.{finger}_Curl", f"{md}.input1{axis}")
                cmds.connectAttr(f"{md}.output{axis}", f"{ctrl}.rotateZ")

    def fk_deform(key):
        grp = dag_utils.group("constraints", f"constraint_{key}_GRP")
        finger_ctrls = data.body_ctrl["fk"][key]
        finger_jnts = data.body_jnt["deform"][key]
        for finger in ["thumb", "index", "middle", "ring", "pinky"]:
            ctrls = finger_ctrls[finger]
            jnts = finger_jnts[finger]
            for ctrl, jnt in zip(ctrls, jnts):
                con = cmds.parentConstraint(ctrl, jnt, mo=False)[0]
                cmds.parent(con, grp)

    def orient(key):
        arm_key = key.replace("hand", "arm")
        ik_ctrl = data.body_ctrl["ik"][arm_key][1]
        end_joint = data.body_jnt["ik"][arm_key][3]
        end_n = end_joint.split("|")[-1]
        orient_grp = cmds.group(em=True, n=f"{end_n}_orient_GRP", p=ik_ctrl)
        cmds.matchTransform(orient_grp, end_joint)
        transform_utils.to_opm(orient_grp)
        cmds.orientConstraint(orient_grp, end_joint)

    dag_utils.group("group", "driving_system", "constraints")
    for key in ["hand_l", "hand_r"]:
        spread(key)
        curl(key)
        fk_deform(key)
        orient(key)


def biped_foot():

    def roll_ik(key):
        foot_n = key.replace("leg", "foot")
        ctrl, jnts = data.body_ctrl["ik"][key][1], data.body_jnt["ik"][key]
        pivot_jnts = data.body_jnt["foot_pivot"][key]
        pivot_group = cmds.listRelatives(pivot_jnts[0], p=True, f=True)[0]
        foot_jnt, ball_jnt = jnts[2], jnts[3]
        roll_ball_jnt, roll_foot_jnt = pivot_jnts[4], pivot_jnts[5]
        foot_ikh = cmds.listRelatives(ctrl, type="ikHandle", fullPath=True)[0]
        ball_ikh = cmds.ikHandle(sj=foot_jnt, ee=ball_jnt,
                                 sol="ikSCsolver", n=f"{foot_n}_Roll_IKH")[0]
        cmds.parentConstraint(ctrl, pivot_group)
        dag_utils.parent(ball_ikh, roll_ball_jnt)
        dag_utils.parent(foot_ikh, roll_foot_jnt)
        cmds.orientConstraint(roll_foot_jnt, foot_jnt)

    def bank(key):
        foot_n = key.replace("leg", "foot")
        ctrl, jnts = data.body_ctrl["ik"][key][1], data.body_jnt["foot_pivot"][key]
        bank_inner_jnt, bank_outer_jnt = jnts[:2]

        md = cmds.createNode("multiplyDivide", n=f"{foot_n}_bank_MD")
        cmds.setAttr(f"{md}.input2X", -1)
        cmds.setAttr(f"{md}.input2Y", -1)
        cond = cmds.createNode("condition", n=f"{foot_n}_bank_cond")
        cmds.setAttr(f"{cond}.operation", 5)  # Less or Equal
        cmds.connectAttr(f"{ctrl}.Bank", f"{cond}.firstTerm")
        cmds.setAttr(f"{cond}.secondTerm", 0)

        cmds.connectAttr(f"{ctrl}.Bank", f"{cond}.colorIfTrueR")
        cmds.setAttr(f"{cond}.colorIfFalseR", 0)
        cmds.connectAttr(f"{cond}.outColorR", f"{md}.input1X")
        cmds.connectAttr(f"{md}.outputX", f"{bank_inner_jnt}.rotateX")

        cmds.setAttr(f"{cond}.colorIfTrueG", 0)
        cmds.connectAttr(f"{ctrl}.Bank", f"{cond}.colorIfFalseG")
        cmds.connectAttr(f"{cond}.outColorG", f"{md}.input1Y")
        cmds.connectAttr(f"{md}.outputY", f"{bank_outer_jnt}.rotateX")

    def roll(key):
        foot_n = key.replace("leg", "foot")
        ctrl, jnts = data.body_ctrl["ik"][key][1], data.body_jnt["foot_pivot"][key]
        ik_ball_jnt = data.body_jnt["ik"][key][3]
        heel_jnt, toe_jnt, ball_jnt = jnts[2:5]
        md = cmds.createNode("multiplyDivide", n=f"{foot_n}_roll_MD")
        cmds.setAttr(f"{md}.input2X", -1.0)
        cmds.setAttr(f"{md}.input2Y", -1.0)
        cmds.setAttr(f"{md}.input2Z", -1.0)
        heel_cond = cmds.createNode("condition", n=f"{foot_n}_heel_cond")
        cmds.setAttr(f"{heel_cond}.operation", 4)  # Less Than
        cmds.connectAttr(f"{ctrl}.Roll", f"{heel_cond}.firstTerm")
        cmds.setAttr(f"{heel_cond}.secondTerm", 0)
        cmds.setAttr(f"{heel_cond}.colorIfFalseR", 0)
        cmds.connectAttr(f"{ctrl}.Roll", f"{heel_cond}.colorIfTrueR")
        cmds.connectAttr(f"{heel_cond}.outColorR", f"{md}.input1X")
        cmds.connectAttr(f"{md}.outputX", f"{heel_jnt}.rotateZ")
        toe_cond = cmds.createNode("condition", n=f"{foot_n}_toe_cond")
        cmds.setAttr(f"{toe_cond}.operation", 3)  # Greater or Equal
        cmds.connectAttr(f"{ctrl}.Roll", f"{toe_cond}.firstTerm")
        cmds.setAttr(f"{toe_cond}.secondTerm", 30)
        cmds.setAttr(f"{toe_cond}.colorIfFalseR", 0)
        toe_pma = cmds.createNode("plusMinusAverage", n=f"{foot_n}_toe_PMA")
        cmds.setAttr(f"{toe_pma}.operation", 2)  # Subtract
        cmds.setAttr(f"{toe_pma}.input1D[1]", 30)
        cmds.connectAttr(f"{ctrl}.Roll", f"{toe_pma}.input1D[0]")
        cmds.connectAttr(f"{toe_pma}.output1D", f"{toe_cond}.colorIfTrueR")
        cmds.connectAttr(f"{toe_cond}.outColorR", f"{md}.input1Y")
        cmds.connectAttr(f"{md}.outputY", f"{toe_jnt}.rotateZ")
        ball_cond = cmds.createNode("condition", n=f"{foot_n}_ball_cond")
        cmds.setAttr(f"{ball_cond}.operation", 3)  # Greater or Equal
        cmds.connectAttr(f"{ctrl}.Roll", f"{ball_cond}.firstTerm")
        cmds.setAttr(f"{ball_cond}.secondTerm", 30)
        cmds.connectAttr(f"{ctrl}.Roll", f"{ball_cond}.colorIfFalseR")
        ball_pma = cmds.createNode("plusMinusAverage", n=f"{foot_n}_ball_PMA")
        cmds.setAttr(f"{ball_pma}.operation", 2)  # Subtract
        cmds.setAttr(f"{ball_pma}.input1D[0]", 90)
        cmds.connectAttr(f"{ctrl}.Roll", f"{ball_pma}.input1D[1]")
        cmds.connectAttr(f"{ball_pma}.output1D", f"{ball_cond}.colorIfTrueR")
        ball_clamp = cmds.createNode("clamp", n=f"{foot_n}_ball_clamp")
        cmds.setAttr(f"{ball_clamp}.minR", 0)
        cmds.setAttr(f"{ball_clamp}.maxR", 30)
        cmds.connectAttr(f"{ball_cond}.outColorR", f"{ball_clamp}.inputR")
        cmds.connectAttr(f"{ball_clamp}.outputR", f"{md}.input1Z")
        cmds.connectAttr(f"{md}.outputZ", f"{ball_jnt}.rotateZ")
        loc = cmds.spaceLocator(n=f"{foot_n}_ballAimUpRef_LOC")[0]
        cmds.matchTransform(loc, ball_jnt)
        cmds.parent(loc, ball_jnt)
        side = 1 if key[-1] == "l" else -1
        cmds.aimConstraint(toe_jnt, ik_ball_jnt,
                           aimVector=(1 * side, 0, 0), upVector=(0, 1, 0),
                           worldUpType="objectrotation", worldUpObject=loc,
                           worldUpVector=(0, 1, 0))

    for key in ["leg_l", "leg_r"]:
        roll_ik(key)
        bank(key)
        roll(key)
