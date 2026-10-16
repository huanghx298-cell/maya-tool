

import maya.cmds as cmds
import maya.api.OpenMaya as om

import data.rig_data as data
import rig.rig_schema as rig_schema

import rig.rig_skeleton as rig_skeleton
import rig.rig_ctrl as rig_ctrl

import utils.mesh_utils as mesh_utils
import utils.dag_utils as dag_utils
import utils.transform_utils as transform_utils


def build_ik(jnts):

    def create_curve():
        points = []
        for jnt in jnts:
            points.append(cmds.xform(jnt, q=True, ws=True, t=True))
        curve = cmds.curve(ep=points, d=3, n=f"{jnt_n}_spline_IK_CRV")
        curve = dag_utils.parent(curve, grp)
        return curve

    def create_ctrl():
        grp = dag_utils.group("IKSystem", f"{jnt_n}_spline_IK_ctrl_GRP")
        ctrls = []
        for i, u in enumerate([0, 0.5, 1]):
            ctrl = rig_ctrl.cube(n=f"{jnt_n}_IK{i:02d}_CTRL", s=3)
            matrix = transform_utils.curve_matrix(curve, u)
            cmds.xform(ctrl, ws=True, m=matrix)
            cmds.scale(0.11, 1, 1, ctrl, r=True, os=True)
            cmds.makeIdentity(ctrl, a=True, r=True, s=True)
            ctrl = dag_utils.parent(ctrl, grp)
            transform_utils.to_opm(ctrl)
            ctrls.append(ctrl)
        return ctrls

    def create_driver_joint():
        driver_jnts = []
        for i, u in enumerate([0, 0.5, 1]):
            matrix = transform_utils.curve_matrix(curve, u)
            jnt = cmds.createNode(
                "joint", n=f"{jnt_n}_driver{i:02d}_JNT", p=grp)
            cmds.xform(jnt, ws=True, m=matrix)
            transform_utils.to_opm(jnt)
            driver_jnts.append(jnt)
        return driver_jnts

    def create_follow_joint():
        selection = om.MSelectionList().add(curve)
        curve_fn = om.MFnNurbsCurve(selection.getDagPath(0))
        param = []
        for jnt in jnts:
            pos = om.MPoint(cmds.xform(jnt, q=True, ws=True, t=True))
            u = curve_fn.closestPoint(pos, space=om.MSpace.kWorld)[1]
            param.append(u)
        follow_jnts = []
        for i, (jnt, u) in enumerate(zip(jnts, param)):
            follow_jnt = cmds.createNode(
                "joint", n=f"{jnt_n}_follow{i:02d}_JNT")
            follow_jnt = dag_utils.parent(follow_jnt, grp)
            mp = cmds.createNode("motionPath", n=f"{jnt_n}_spline{i:02d}_MP")
            cmds.connectAttr(f"{curve}.worldSpace[0]",
                             f"{mp}.geometryPath")
            cmds.connectAttr(f"{mp}.allCoordinates",
                             f"{follow_jnt}.translate")
            cmds.setAttr(f"{mp}.uValue", u)
            cmds.matchTransform(follow_jnt, jnt, pos=False, rot=True)
            follow_jnts.append(follow_jnt)
        return follow_jnts

    def create_follow_locator():
        driver_locs = []
        for i, (current, target) in enumerate(
                zip(follow_jnts[1:-1], follow_jnts[2:]), start=1):
            loc = cmds.spaceLocator(n=f"{jnt_n}_follow{i:02d}_LOC")[0]
            cmds.matchTransform(loc, current)
            loc = dag_utils.parent(loc, grp)
            cmds.aimConstraint(target, current, aimVector=(1, 0, 0),
                               upVector=(0, 1, 0), worldUpType="objectrotation",
                               worldUpObject=loc, worldUpVector=(0, 1, 0))
            driver_locs.append(loc)
        return driver_locs

    # ctrl -> driver jnt -> curve -> follow jnt -> jnt
    jnt_n = jnts[0].rsplit("|", 1)[-1].removesuffix("_JNT")
    grp = dag_utils.group("group", "driving_system", jnt_n)
    curve = create_curve()
    ctrls = create_ctrl()
    driver_jnts = create_driver_joint()
    follow_jnts = create_follow_joint()
    follow_locs = create_follow_locator()

    def ctrl_joint_connections():
        for ctrl, driver_jnt in zip(ctrls, driver_jnts):
            cmds.parentConstraint(ctrl, driver_jnt)
        cmds.skinCluster(driver_jnts, curve, tsb=True, mi=1,
                         nw=1, n=f"{jnt_n}_curve_skinCluster")[0]
        for jnt, follow_jnt in zip(jnts, follow_jnts):
            cmds.parentConstraint(follow_jnt, jnt)
        for ctrl, jnt in zip((ctrls[0], ctrls[-1]),
                             (follow_jnts[0], follow_jnts[-1])):
            cmds.orientConstraint(ctrl, jnt, mo=True)

    def joint_rotation_distribution():
        locs_u, ctrls_u = [], []
        space = om.MSpace.kWorld
        cv_fn = om.MFnNurbsCurve(om.MSelectionList().add(curve).getDagPath(0))
        for loc in follow_locs:
            pos = om.MPoint(cmds.xform(loc, q=True, ws=True, t=True))
            locs_u.append(cv_fn.closestPoint(pos, space=space)[1])
        for ctrl in ctrls:
            pos = om.MPoint(cmds.xform(ctrl, q=True, ws=True, t=True))
            ctrls_u.append(cv_fn.closestPoint(pos, space=space)[1])
        constraints = []
        for i in range(len(ctrls) - 1):
            left_ctrl, right_ctrl = ctrls[i], ctrls[i + 1]
            left_u, right_u = ctrls_u[i], ctrls_u[i + 1]
            for target, target_u in zip(follow_locs, locs_u):
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

    def mid_ctrl_follow():
        start, mid, end = ctrls
        start_n = start.rsplit("|", 1)[-1].removesuffix("_CTRL")
        mid_n = mid.rsplit("|", 1)[-1].removesuffix("_CTRL")
        end_n = end.rsplit("|", 1)[-1].removesuffix("_CTRL")
        ctrls_grp = cmds.listRelatives(mid, p=True, f=True)[0]
        mid_grp = dag_utils.group(ctrls_grp, f"{mid_n}_offset_GRP")
        start_grp = dag_utils.group(start, f"{start_n}_follow_GRP")
        end_grp = dag_utils.group(end, f"{end_n}_follow_GRP")
        cmds.matchTransform(mid_grp, mid)
        cmds.matchTransform(start_grp, mid_grp)
        cmds.matchTransform(end_grp, mid_grp)
        transform_utils.to_opm(mid_grp)
        transform_utils.to_opm(start_grp)
        transform_utils.to_opm(end_grp)
        con = cmds.parentConstraint(start_grp, end_grp, mid_grp)[0]
        mid = dag_utils.parent(mid, mid_grp)
        transform_utils.to_opm(mid)
        ctrls[1] = mid
        w0 = cmds.listAttr(con, string="*W0")[0]
        w1 = cmds.listAttr(con, string="*W1")[0]
        cmds.setAttr(f"{con}.{w0}", 0.5)
        cmds.setAttr(f"{con}.{w1}", 0.5)

    ctrl_joint_connections()
    joint_rotation_distribution()
    mid_ctrl_follow()
