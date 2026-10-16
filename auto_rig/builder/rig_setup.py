

import maya.cmds as cmds
import maya.api.OpenMaya as om

import data.rig_data as data
import rig.rig_schema as rig_schema

import rig.rig_skeleton as rig_skeleton
import rig.rig_ctrl as rig_ctrl
import rig.rig_spline as rig_spline

import utils.mesh_utils as mesh_utils
import utils.dag_utils as dag_utils
import utils.transform_utils as transform_utils


def biped():

    def setup_joint():
        jnt_n = data.body_jnt["root"].split('|')[-1]
        grp = dag_utils.group("deform_joints", f"{jnt_n}_deform_jnt_GRP")
        jnt = dag_utils.parent(data.body_jnt["root"], grp)
        all_jnt = dag_utils.descendant(jnt, "joint")
        all_jnt.sort(key=lambda x: x.count("|"))
        data.body_jnt["root"] = jnt
        data.body_jnt["all_joint"] = all_jnt

    def classify_joint():
        arm_l, arm_r, leg_l, leg_r, spine = [], [], [], [], []
        for jnt in data.body_jnt["all_joint"]:
            name = jnt.rsplit("|", 1)[-1]
            if name.removesuffix("_l").removesuffix("_r") in rig_schema.UE5_BODY["arm"]:
                (arm_l if name.endswith("_l") else arm_r).append(jnt)
            elif name.removesuffix("_l").removesuffix("_r") in rig_schema.UE5_BODY["leg"]:
                (leg_l if name.endswith("_l") else leg_r).append(jnt)
            elif any(name.startswith(p) for p in rig_schema.UE5_BODY["spine"]):
                spine.append(jnt)
        data.body_jnt["deform"] = {}
        data.body_jnt["deform"]["arm_l"], data.body_jnt["deform"]["arm_r"] = arm_l, arm_r
        data.body_jnt["deform"]["leg_l"], data.body_jnt["deform"]["leg_r"] = leg_l, leg_r
        data.body_jnt["deform"]["spine"] = spine
        hand_l, hand_r = {}, {}
        for key, names in rig_schema.UE5_BODY["hand"].items():
            hand_l[key], hand_r[key] = [], []
            for jnt in data.body_jnt["all_joint"]:
                name = jnt.rsplit("|", 1)[-1]
                base_name = name.removesuffix("_l").removesuffix("_r")
                if base_name in names:
                    (hand_l if name.endswith("_l")
                     else hand_r)[key].append(jnt)
        data.body_jnt["deform"]["hand_l"] = hand_l
        data.body_jnt["deform"]["hand_r"] = hand_r
        joint_map = {jnt.rsplit("|", 1)[-1]: jnt
                     for jnt in data.body_jnt["all_joint"]}
        twist = {}
        for key, names in rig_schema.UE5_BODY["twist"].items():
            for side in ("l", "r"):
                twist[f"{key}_{side}"] = [joint_map[f"{name}_{side}"]
                                          for name in names]
        data.body_jnt["deform"]["twist"] = twist

    def duplicate_joint():
        data.body_jnt["fk"] = {}
        data.body_jnt["ik"] = {}
        for key in ["arm_l", "arm_r", "leg_l", "leg_r", "spine"]:
            chain = data.body_jnt["deform"][key]
            data.body_jnt["fk"][key] = rig_skeleton.duplicate(chain, "fk")
            data.body_jnt["ik"][key] = rig_skeleton.duplicate(chain, "ik")

    data.body_jnt["root"] = cmds.ls("root", type="joint", long=True)[0]
    dag_utils.group("group", "skeleton", "deform_joints")
    dag_utils.group("group", "skeleton", "fk_joints")
    dag_utils.group("group", "skeleton", "ik_joints")
    setup_joint()
    classify_joint()
    duplicate_joint()

    def setup_root_ctrl():
        jnt_n = data.body_jnt["root"].split("|")[-1]
        grp = dag_utils.group("MainSystem", f"fk_{jnt_n}_ctrl_GRP")
        ctrl = rig_ctrl.circle(n=f"{jnt_n}_ctrl", s=40.0)
        mesh_utils.normal(ctrl, x=90)
        ctrl = dag_utils.parent(ctrl, grp)
        cmds.matchTransform(ctrl, data.body_jnt["root"])
        transform_utils.to_opm(ctrl)
        data.body_ctrl["root_ctrl"] = ctrl

    def setup_fk_ctrl():

        def fk(jnts, s):
            jnt_n = jnts[0].split("|")[-1]
            parent = dag_utils.group("FKSystem", f"fk_{jnt_n}_ctrl_GRP")
            fk_ctrls = []
            for jnt in jnts:
                jnt_n = jnt.split("|")[-1]
                ctrl = rig_ctrl.circle(n=f"{jnt_n}_fk_CTRL", s=s)
                mesh_utils.normal(ctrl, z=-90)
                ctrl = dag_utils.parent(ctrl, parent)
                cmds.matchTransform(ctrl, jnt)
                transform_utils.to_opm(ctrl)
                parent = ctrl
                fk_ctrls.append(ctrl)
            return fk_ctrls

        data.body_ctrl["fk"] = {}
        jnt = data.body_jnt["deform"]
        for key in ["arm_l", "arm_r", "leg_l", "leg_r", "spine"]:
            s = 20.0 if key == "spine" else 11.0
            data.body_ctrl["fk"][key] = fk(jnt[key], s=s)

    def setup_limb_ik_ctrl():

        def ik(jnts):
            s_jnt_n = jnts[0].split("|")[-1]
            m_jnt_n = jnts[1].split("|")[-1]
            e_jnt_n = jnts[2].split("|")[-1]
            grp = dag_utils.group("IKSystem", f"ik_{s_jnt_n}_ctrl_GRP")
            pole_ctrl = rig_ctrl.pole_vector(
                n=f"{m_jnt_n}_pole_CTRL", s=5)
            ik_ctrl = rig_ctrl.cube(n=f"{e_jnt_n}_ik_CTRL", s=5)
            cmds.matchTransform(pole_ctrl, jnts[1])
            cmds.matchTransform(ik_ctrl, jnts[2])
            dag_utils.parent(pole_ctrl, grp)
            dag_utils.parent(ik_ctrl, grp)
            offset = 40.0 if m_jnt_n.startswith("calf") else -40.0
            offset *= 1 if m_jnt_n.endswith("_r") else -1
            cmds.move(0, offset, 0, pole_ctrl,
                      relative=True, objectSpace=True)
            if not key.startswith("leg"):
                cmds.makeIdentity(ik_ctrl, rotate=True)
            cmds.makeIdentity(pole_ctrl, rotate=True)
            transform_utils.to_opm(ik_ctrl)
            transform_utils.to_opm(pole_ctrl)
            return [pole_ctrl, ik_ctrl]

        data.body_ctrl["ik"] = {}
        jnt = data.body_jnt["deform"]
        for key in ["arm_l", "arm_r"]:
            data.body_ctrl["ik"][key] = ik(jnt[key][1:4])
        for key in ["leg_l", "leg_r"]:
            data.body_ctrl["ik"][key] = ik(jnt[key][0:3])

    def setup_spine_ik_ctrl():

        def curve():
            grp = dag_utils.group("group", "driving_system", "spine")
            jnts = data.body_jnt["ik"]["spine"]
            points = []
            for jnt in jnts:
                points.append(cmds.xform(jnt, q=True, ws=True, t=True))
            cv = cmds.curve(ep=points, d=3, n="spine_IK_EP_CRV")
            cv = dag_utils.parent(cv, grp)
            return cv

        def ik():
            grp = dag_utils.group("IKSystem", "ik_spine_ctrl_GRP")
            cv = data.body_ctrl["ik"]["spine_curve"]
            ctrls = []
            for name, u in zip(["spine_01", "spine_02", "spine_03"], [0, 0.5, 1]):
                ctrl = rig_ctrl.cube(n=f"{name}_ik_CTRL", s=18)
                matrix = transform_utils.curve_matrix(cv, u)
                cmds.xform(ctrl, ws=True, m=matrix)
                cmds.scale(0.11, 1, 1, ctrl, r=True, os=True)
                cmds.makeIdentity(ctrl, a=True, r=True, s=True)
                ctrl = dag_utils.parent(ctrl, grp)
                ctrls.append(ctrl)
            return ctrls

        data.body_ctrl["ik"]["spine_curve"] = curve()
        data.body_ctrl["ik"]["spine"] = ik()

        def follow_joint():
            cv = data.body_ctrl["ik"]["spine_curve"]
            jnts = data.body_jnt["ik"]["spine"]
            selection = om.MSelectionList().add(cv)
            curve_fn = om.MFnNurbsCurve(selection.getDagPath(0))
            param = []
            for jnt in jnts:
                pos = om.MPoint(cmds.xform(jnt, q=True, ws=True, t=True))
                u = curve_fn.closestPoint(pos, space=om.MSpace.kWorld)[1]
                param.append(u)
            grp = dag_utils.group("group", "driving_system", "spine")
            cv_jnts = []
            for jnt, u in zip(jnts, param):
                jnt_n = jnt.split("|")[-1].removesuffix("_ik_JNT")
                cv_jnt = cmds.createNode("joint", n=f"{jnt_n}_follow_JNT")
                cv_jnt = dag_utils.parent(cv_jnt, grp)
                mp = cmds.createNode("motionPath", n=f"{jnt_n}_spine_MP")
                cmds.connectAttr(f"{cv}.worldSpace[0]", f"{mp}.geometryPath")
                cmds.connectAttr(f"{mp}.allCoordinates", f"{cv_jnt}.translate")
                cmds.setAttr(f"{mp}.uValue", u)
                cmds.matchTransform(cv_jnt, jnt, pos=False, rot=True)
                cv_jnts.append(cv_jnt)
            return cv_jnts

        def driver_locator():
            grp = dag_utils.group("group", "driving_system", "spine")
            jnts = data.body_jnt["ik"]["spine_follow"]
            driver_locs = []
            for current, target in zip(jnts[1:-1], jnts[2:]):
                jnt_n = current.split("|")[-1].removesuffix("_follow_JNT")
                loc = cmds.spaceLocator(n=f"{jnt_n}_spine_driver_LOC")[0]
                cmds.matchTransform(loc, current)
                loc = dag_utils.parent(loc, grp)
                cmds.aimConstraint(target, current, aimVector=(1, 0, 0),
                                   upVector=(0, 1, 0), worldUpType="objectrotation",
                                   worldUpObject=loc, worldUpVector=(0, 1, 0))
                driver_locs.append(loc)
            return driver_locs

        def driver_joint():
            grp = dag_utils.group("group", "driving_system", "spine")
            cv = data.body_ctrl["ik"]["spine_curve"]
            jnts_n = ["spine_01", "spine_02", "spine_03"]
            param = [0, 0.5, 1]
            driver_jnts = []
            for jnt_n, u in zip(jnts_n, param):
                matrix = transform_utils.curve_matrix(cv, u)
                jnt = cmds.createNode(
                    "joint", n=f"{jnt_n}_driver_JNT", p=grp)
                cmds.xform(jnt, ws=True, m=matrix)
                transform_utils.to_opm(jnt)
                driver_jnts.append(jnt)
            return driver_jnts

        # ctrl -> driver jnt -> curve -> follow jnt -> ik jnt
        data.body_jnt["ik"]["spine_follow"] = follow_joint()
        data.body_jnt["ik"]["spine_driver"] = driver_joint()
        data.body_ctrl["ik"]["spine_driver_loc"] = driver_locator()

    def setup_ikfk_ctrl():

        def ikfk(jnt):
            grp = dag_utils.group("group", "controls", "IKFKSystem")
            jnt_n = jnt.split("|")[-1]
            ctrl = rig_ctrl.cross(n=f"{jnt_n}_ikfk_CTRL", s=2.5)
            ctrl = dag_utils.parent(ctrl, grp)
            cmds.matchTransform(ctrl, jnt, position=True)
            offset_x = 25.0 if jnt_n.startswith(
                "spine") else 15.0 if jnt_n.endswith("_l") else -15.0
            cmds.move(offset_x, 0, 0, ctrl, r=True, os=True)
            for attr in ("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"):
                cmds.setAttr(f"{ctrl}.{attr}", l=True, k=False, cb=False)
            cmds.addAttr(ctrl, longName="IKFKBlend", attributeType="double",
                         minValue=0, maxValue=10, defaultValue=0,
                         keyable=True)
            return ctrl

        data.body_ctrl["ikfk"] = {}
        for key in ["arm_l", "arm_r", "leg_l", "leg_r", "spine"]:
            i = 2 if key == "spine" else 1 if key.startswith("arm") else 0
            jnt = data.body_jnt["deform"][key][i]
            data.body_ctrl["ikfk"][key] = ikfk(jnt)

    dag_utils.group("group", "controls", "MainSystem")
    dag_utils.group("group", "controls", "FKSystem")
    dag_utils.group("group", "controls", "IKSystem")
    dag_utils.group("group", "driving_system", "spine")
    dag_utils.group("group", "controls", "IKFKSystem")
    setup_root_ctrl()
    setup_fk_ctrl()
    setup_limb_ik_ctrl()
    setup_spine_ik_ctrl()
    setup_ikfk_ctrl()

    def update_clavicle_ctrl():

        def clavicle(key, s):
            jnt_n = data.body_jnt["fk"][key][0].split("|")[-1]
            grp = dag_utils.group("FKSystem", f"fk_{jnt_n}_ctrl_GRP")
            ctrl = rig_ctrl.clavicle(n=f"{jnt_n}_fk_CTRL", s=s)
            if key.endswith("_l"):
                mesh_utils.normal(ctrl, z=90)
            else:
                mesh_utils.normal(ctrl, y=180, z=90)
            ctrl = dag_utils.parent(ctrl, grp)
            cmds.matchTransform(ctrl, data.body_jnt["fk"][key][0])
            transform_utils.to_opm(ctrl)
            dag_utils.parent(data.body_ctrl["fk"][key][1], ctrl)
            ctrls = dag_utils.descendant(ctrl, "transform")
            ctrls.sort(key=lambda x: x.count("|"))
            old_ctrl = data.body_ctrl["fk"][key][0]
            cmds.delete(old_ctrl)
            return ctrls

        for key in ["arm_l", "arm_r"]:
            data.body_ctrl["fk"][key] = clavicle(key, s=11.0)

    def hand_ctrl():

        def hand(key):
            grp = dag_utils.group("controls", "FKSystem", f"{key}_ctrl_GRP")
            jnt = data.body_jnt["deform"][f"arm_{key[-1]}"][-1]
            cmds.matchTransform(grp, jnt)
            transform_utils.to_opm(grp)
            ctrl = rig_ctrl.half_circle(n=f"{key}_CTRL", s=10)
            offset_y = 90 if key.endswith("_l") else -90
            mesh_utils.normal(ctrl, y=offset_y)
            ctrl = dag_utils.parent(ctrl, grp)
            cmds.matchTransform(ctrl, jnt)
            offset_x = 12 if key.endswith("_l") else -12
            cmds.move(offset_x, 0, 0, ctrl, r=True, os=True)
            transform_utils.to_opm(ctrl)
            finger_ctrls = {"hand": ctrl}
            for finger, finger_jnts in data.body_jnt["deform"][key].items():
                parent = grp
                finger_ctrls[finger] = []
                for jnt in finger_jnts:
                    jnt_n = jnt.split("|")[-1]
                    ctrl = rig_ctrl.circle(n=f"{jnt_n}_CTRL", s=2)
                    mesh_utils.normal(ctrl, z=90)
                    ctrl = dag_utils.parent(ctrl, parent)
                    cmds.matchTransform(ctrl, jnt)
                    transform_utils.to_opm(ctrl)
                    finger_ctrls[finger].append(ctrl)
                    parent = ctrl
            return finger_ctrls

        for key in ["hand_l", "hand_r"]:
            data.body_ctrl["fk"][key] = hand(key)

    dag_utils.group("group", "controls", "FKSystem")
    update_clavicle_ctrl()
    hand_ctrl()

    def foot_bankRoll(key):
        side = 1 if key[-1] == "l" else -1
        ctrls, jnts = data.body_ctrl["ik"][key], data.body_jnt["deform"][key]
        ik_ctrl, foot_jnt, ball_jnt = ctrls[1], jnts[2], jnts[3]
        foot_n = foot_jnt.split("|")[-1]
        grp = dag_utils.group("foot_bankRoll_system", f"{foot_n}_bankRoll_GRP")
        cmds.matchTransform(grp, foot_jnt)
        transform_utils.to_opm(grp)
        cmds.joint(n=f"{key}_bankInnerPivot_JNT")
        cmds.joint(n=f"{key}_bankOuterPivot_JNT")
        cmds.joint(n=f"{key}_heelPivot_JNT")
        cmds.joint(n=f"{key}_toePivot_JNT")
        cmds.joint(n=f"{key}_ballPivot_JNT")
        cmds.joint(n=f"{key}_footPivot_JNT")
        bank_inner_loc = cmds.spaceLocator(n=f"{key}_bankInnerPivot_LOC")[0]
        bank_outer_loc = cmds.spaceLocator(n=f"{key}_bankOuterPivot_LOC")[0]
        roll_heel_loc = cmds.spaceLocator(n=f"{key}_heelPivot_LOC")[0]
        roll_toe_loc = cmds.spaceLocator(n=f"{key}_toePivot_LOC")[0]
        roll_ball_loc = cmds.spaceLocator(n=f"{key}_ballPivot_LOC")[0]
        roll_foot_loc = cmds.spaceLocator(n=f"{key}_footPivot_LOC")[0]
        pivot_jnts = cmds.listRelatives(grp, ad=True, type="joint", f=True)
        pivot_jnts.sort(key=lambda x: x.count("|"))
        pivot_locs = [
            bank_inner_loc, bank_outer_loc,
            roll_heel_loc, roll_toe_loc, roll_ball_loc, roll_foot_loc
        ]
        cmds.matchTransform(bank_inner_loc, foot_jnt)
        transform_utils.to_opm(bank_inner_loc)
        cmds.matchTransform(bank_inner_loc, ball_jnt, rot=True, px=True)
        cmds.move(0, 0, 4.5 * side, bank_inner_loc, r=True, os=True)
        cmds.matchTransform(bank_outer_loc, foot_jnt)
        transform_utils.to_opm(bank_outer_loc)
        cmds.matchTransform(bank_outer_loc, ball_jnt, rot=True, px=True)
        cmds.move(0, 0, -6.0 * side, bank_outer_loc, r=True, os=True)
        cmds.matchTransform(roll_heel_loc, foot_jnt)
        transform_utils.to_opm(roll_heel_loc)
        cmds.matchTransform(roll_heel_loc, ball_jnt, rot=True, px=True)
        cmds.move(-5.0 * side, 0, 0, roll_heel_loc, r=True, os=True)
        cmds.matchTransform(roll_toe_loc, ball_jnt)
        cmds.move(7.5 * side, 0, 0, roll_toe_loc, r=True, os=True)
        cmds.matchTransform(roll_ball_loc, ball_jnt)
        cmds.matchTransform(roll_foot_loc, foot_jnt)
        for jnt, loc in zip(pivot_jnts, pivot_locs):
            cmds.matchTransform(jnt, loc)
            transform_utils.to_opm(jnt)
        cmds.delete(pivot_locs)
        cmds.addAttr(ik_ctrl, ln="Roll", at="double", dv=0, k=True)
        cmds.addAttr(ik_ctrl, ln="Bank", at="double", dv=0, k=True)
        return pivot_jnts

    dag_utils.group("group", "driving_system", "foot_bankRoll_system")
    data.body_jnt["foot_pivot"] = {}
    for key in ["leg_l", "leg_r"]:
        data.body_jnt["foot_pivot"][key] = foot_bankRoll(key)

    def limb_twist_joints(key, suffix):
        base_jnt, twist_01_jnt = data.body_jnt["deform"][f"twist"][key][:2]
        n = base_jnt.rsplit("|", 1)[-1]
        grp = dag_utils.group("twist_system", f"{n}_twist_{suffix}_GRP")
        twist = cmds.createNode("joint", n=f"{n}_twist_{suffix}_JNT")
        follow_01 = cmds.createNode("joint", n=f"{n}_follow_01_{suffix}_JNT")
        follow_02 = cmds.createNode("joint", n=f"{n}_follow_02_{suffix}_JNT")
        twist = dag_utils.parent(twist, grp)
        follow_01 = dag_utils.parent(follow_01, grp)
        follow_02 = dag_utils.parent(follow_02, follow_01)
        cmds.matchTransform(twist, base_jnt)
        cmds.matchTransform(follow_01, base_jnt)
        cmds.matchTransform(follow_02, twist_01_jnt)
        transform_utils.to_opm(twist)
        loc = cmds.spaceLocator(n=f"{n}_twist_{suffix}_LOC")[0]
        cmds.matchTransform(loc, base_jnt)
        cmds.move(0, 10, 0, loc, r=True, os=True)
        return [twist, follow_01, follow_02, loc]
    dag_utils.group("group", "driving_system", "twist_system")
    twist_driver = data.body_jnt["twist_driver"] = {}
    for key in ("arm_l", "arm_r"):
        twist_driver[key] = {}
        for suffix in ("fk", "ik"):
            break
            twist_driver[key][suffix] = limb_twist_joint(key, suffix)

    def limb_twist_joint(key):
        base_jnt, twist_01_jnt = data.body_jnt["deform"]["twist"][key][:2]
        n = base_jnt.rsplit("|", 1)[-1]
        grp = dag_utils.group("twist_system", f"{n}_twist_GRP")
        twist = cmds.createNode("joint", n=f"{n}_twist_JNT")
        follow_01 = cmds.createNode("joint", n=f"{n}_follow_01_JNT")
        follow_02 = cmds.createNode("joint", n=f"{n}_follow_02_JNT")
        twist_delta = cmds.createNode("joint", n=f"{n}_twist_delta_JNT")
        twist = dag_utils.parent(twist, grp)
        follow_01 = dag_utils.parent(follow_01, grp)
        follow_02 = dag_utils.parent(follow_02, follow_01)
        twist_delta = dag_utils.parent(twist_delta, grp)
        cmds.matchTransform(twist, base_jnt)
        cmds.matchTransform(follow_01, base_jnt)
        cmds.matchTransform(follow_02, twist_01_jnt)
        cmds.matchTransform(twist_delta, base_jnt)
        transform_utils.to_opm(twist)
        loc = cmds.spaceLocator(n=f"{n}_twist_LOC")[0]
        loc = dag_utils.parent(loc, grp)
        cmds.matchTransform(loc, base_jnt)
        cmds.move(0, 10, 0, loc, r=True, os=True)
        return [twist, follow_01, follow_02, loc, twist_delta]
    dag_utils.group("group", "driving_system", "twist_system")
    data.body_jnt["twist_driver"] = {}
    for key in ("arm_l", "arm_r"):
        data.body_jnt["twist_driver"][key] = limb_twist_joint(key)


def create_curve():

    def build_curve():
        edge_groups = mesh_utils.edge_group(sel)
        curves = []
        for i, edge in enumerate(edge_groups):
            points = [cmds.pointPosition(vtx, world=True)
                      for vtx in mesh_utils.order_vertex(edge)]
            curve = cmds.curve(d=3, ep=points, n=f"{mesh}_crv{i:02d}_CRV")
            curves.append(curve)
        return curves

    def build_joint():
        jnts, param = [], [0, 0.33, 0.66, 1]
        for curve in curves:
            curve_n = curve.rsplit("|", 1)[-1].removesuffix("_CRV")
            curve_jnts = []
            for i, u in enumerate(param):
                matrix = transform_utils.curve_matrix(curve, u)
                jnt = cmds.createNode("joint", n=f"{curve_n}_jnt{i:02d}_JNT")
                cmds.xform(jnt, ws=True, m=matrix)
                curve_jnts.append(jnt)
            jnts.append(curve_jnts)
            for jnt_0, jnt_1 in zip(curve_jnts[:-1], curve_jnts[1:]):
                transform_utils.orient(jnt_0, jnt_1, "x", "y")
                transform_utils.to_opm(jnt_0)
                dag_utils.parent(jnt_1, jnt_0)
            cmds.matchTransform(curve_jnts[-1], curve_jnts[-2], rot=True)
            transform_utils.to_opm(curve_jnts[-1])
        return jnts

    sel = cmds.ls(sl=True, fl=True)
    mesh = sel[0].split(".", 1)[0]
    curves = build_curve()
    jnts = build_joint()
    for chain in jnts:
        rig_spline.build_ik(chain)
    jnts = [jnt for chain in jnts for jnt in chain]
    skin = cmds.skinCluster(jnts, mesh, tsb=True, n=f"{mesh}_SKC")[0]
    jnt = cmds.ls("Root_M", type="joint")[0]
    cmds.skinCluster(skin, e=True, ai=jnt, lw=True, wt=0)
