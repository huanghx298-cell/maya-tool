

import maya.cmds as cmds
import maya.api.OpenMaya as om
import math


def to_opm(node):
    if cmds.nodeType(node) == "joint":
        bake_joint_orient(node)
    local_m = cmds.xform(node, q=True, m=True, os=True)
    old_m = cmds.getAttr(node + ".offsetParentMatrix")
    new_m = [0] * 16
    for row in range(4):
        for col in range(4):
            new_m[row*4 + col] = sum(local_m[row*4 + k] * old_m[k*4 + col]
                                     for k in range(4))
    cmds.setAttr(node + ".offsetParentMatrix", *new_m, type="matrix")
    cmds.setAttr(node + ".translate", 0, 0, 0)
    cmds.setAttr(node + ".rotate", 0, 0, 0)
    cmds.setAttr(node + ".scale", 1, 1, 1)


def bake_joint_orient(joint):
    rx, ry, rz = cmds.getAttr(joint + ".rotate")[0]
    jox, joy, joz = cmds.getAttr(joint + ".jointOrient")[0]
    rotate_order = cmds.getAttr(joint + ".rotateOrder")
    rx, ry, rz = math.radians(rx), math.radians(ry), math.radians(rz)
    jox, joy, joz = math.radians(jox), math.radians(joy), math.radians(joz)
    rot_q = om.MEulerRotation(rx, ry, rz, rotate_order).asQuaternion()
    jo_q = om.MEulerRotation(jox, joy, joz, rotate_order).asQuaternion()
    new_rot = rot_q * jo_q
    new_euler = new_rot.asEulerRotation()
    new_euler.reorderIt(rotate_order)
    cmds.setAttr(joint + ".jointOrient", 0, 0, 0)
    cmds.setAttr(joint + ".rotate", math.degrees(new_euler.x),
                 math.degrees(new_euler.y), math.degrees(new_euler.z))


def curve_matrix(cv, u, *, axis="x", up_axis="-z"):
    UP_VECTORS = {
        "x":  om.MVector(1, 0, 0), "-x": om.MVector(-1, 0, 0),
        "y":  om.MVector(0, 1, 0), "-y": om.MVector(0, -1, 0),
        "z":  om.MVector(0, 0, 1), "-z": om.MVector(0, 0, -1),
    }
    P = om.MVector(cmds.pointOnCurve(cv, pr=u, top=True, p=True))
    T = om.MVector(cmds.pointOnCurve(cv, pr=u, top=True, nt=True))
    N = om.MVector(UP_VECTORS[up_axis])
    B = (T ^ N).normal()
    N = (B ^ T).normal()
    X, Y, Z = {"x": (T, N, B), "y": (B, T, N), "z": (N, B, T)}[axis]
    matrix = om.MMatrix([
        X.x, X.y, X.z, 0,
        Y.x, Y.y, Y.z, 0,
        Z.x, Z.y, Z.z, 0,
        P.x, P.y, P.z, 1])
    return matrix


def orients(source, target, aim_axis="x"):
    p0 = om.MVector(cmds.xform(source, q=True, ws=True, t=True))
    p1 = om.MVector(cmds.xform(target, q=True, ws=True, t=True))
    old_matrix = om.MMatrix(cmds.xform(source, q=True, ws=True, matrix=True))
    old_y = om.MVector(old_matrix[4], old_matrix[5], old_matrix[6]).normal()
    x = (p1 - p0).normal()
    x = x if aim_axis == "x" else -x
    y = (old_y - x * (old_y * x)).normalize()
    z = (x ^ y).normal()
    y = (z ^ x).normal()
    matrix = om.MMatrix([
        x.x, x.y, x.z, 0,
        y.x, y.y, y.z, 0,
        z.x, z.y, z.z, 0,
        p0.x, p0.y, p0.z, 1,
    ])
    cmds.xform(source, ws=True, matrix=matrix)


def orient(source, target, aim_axis="x", up_axis="y"):
    p0 = om.MVector(cmds.xform(source, q=True, ws=True, t=True))
    p1 = om.MVector(cmds.xform(target, q=True, ws=True, t=True))
    old_m = om.MMatrix(cmds.xform(source, q=True, ws=True, matrix=True))
    aim_name = aim_axis.removeprefix("-")
    up_name = up_axis.removeprefix("-")
    axis_index = {"x": 0, "y": 4, "z": 8}
    i = axis_index[up_axis.removeprefix("-")]
    up = om.MVector(old_m[i], old_m[i + 1], old_m[i + 2]).normal()
    up = -up if up_axis.startswith("-") else up
    aim = (p1 - p0).normal()
    aim = -aim if aim_axis.startswith("-") else aim
    up = (up - aim * (up * aim)).normal()
    axes = {aim_name: -aim if aim_axis.startswith("-") else aim,
            up_name: -up if up_axis.startswith("-") else up, }
    missing_axis = ({"x", "y", "z"} - set(axes)).pop()
    cross_axes = {"x": ("y", "z"), "y": ("z", "x"), "z": ("x", "y"), }
    a, b = cross_axes[missing_axis]
    axes[missing_axis] = (axes[a] ^ axes[b]).normal()
    x, y, z = axes["x"], axes["y"], axes["z"]
    matrix = om.MMatrix([
        x.x, x.y, x.z, 0,
        y.x, y.y, y.z, 0,
        z.x, z.y, z.z, 0,
        p0.x, p0.y, p0.z, 1,
    ])
    cmds.xform(source, ws=True, matrix=matrix)
