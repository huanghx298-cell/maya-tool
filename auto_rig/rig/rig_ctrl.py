

import maya.cmds as cmds

from rig.rig_schema import CTRL


def circle(n, s):
    idx = CTRL["color"]["cyan"]
    points = [(x * s, y * s, z * s) for x, y, z in CTRL["circle"]]
    points += points[:3]
    knots = list(range(-2, len(points)))
    ctrl = cmds.curve(d=3, p=points, knot=knots, per=True, name=n)
    shape = cmds.listRelatives(ctrl, s=True, f=True)[0]
    cmds.setAttr(shape + ".overrideEnabled", 1)
    cmds.setAttr(shape + ".overrideColor", idx)
    return ctrl


def half_circle(n, s):
    idx = CTRL["color"]["yellow"]
    points = [(x * s, y * s, z * s) for x, y, z in CTRL["half_circle"]]
    ctrl = cmds.curve(d=3, p=points, name=n)
    shape = cmds.listRelatives(ctrl, s=True, f=True)[0]
    cmds.setAttr(shape + ".overrideEnabled", 1)
    cmds.setAttr(shape + ".overrideColor", idx)
    return ctrl


def cube(n, s):
    idx = CTRL["color"]["red"]
    points = [(x * s, y * s, z * s) for x, y, z in CTRL["cube"]]
    ctrl = cmds.curve(d=1, p=points, name=n)
    shape = cmds.listRelatives(ctrl, s=True, f=True)[0]
    cmds.setAttr(shape + ".overrideEnabled", 1)
    cmds.setAttr(shape + ".overrideColor", idx)
    return ctrl


def pole_vector(n, s):
    idx = CTRL["color"]["red"]
    points = [(x * s, y * s, z * s) for x, y, z in CTRL["pole_vector"]]
    ctrl = cmds.curve(d=1, p=points, name=n)
    shape = cmds.listRelatives(ctrl, s=True, f=True)[0]
    cmds.setAttr(shape + ".overrideEnabled", 1)
    cmds.setAttr(shape + ".overrideColor", idx)
    return ctrl


def cross(n, s):
    idx = CTRL["color"]["blue"]
    points = [(x * s, y * s, z * s) for x, y, z in CTRL["ikfk_switch"]]
    ctrl = cmds.curve(d=1, p=points, name=n)
    shape = cmds.listRelatives(ctrl, s=True, f=True)[0]
    cmds.setAttr(shape + ".overrideEnabled", 1)
    cmds.setAttr(shape + ".overrideColor", idx)
    return ctrl


def clavicle(n, s):
    idx = CTRL["color"]["yellow"]
    arc_points = [(x * s, y * s, z * s) for x, y, z in CTRL["clavicle"][0]]
    line_points = [(x * s, y * s, z * s) for x, y, z in CTRL["clavicle"][1]]
    ctrl = cmds.curve(d=3, p=arc_points, name=n)
    line = cmds.curve(d=1, p=line_points)
    line_shape = cmds.listRelatives(line, s=True, f=True)[0]
    cmds.parent(line_shape, ctrl, s=True, r=True)
    cmds.delete(line)
    mirror = cmds.duplicate(ctrl)[0]
    cmds.rotate(0, 0, 180, mirror, r=True, os=True)
    cmds.makeIdentity(mirror, apply=True)
    mirror_shapes = cmds.listRelatives(mirror, s=True, f=True)
    cmds.parent(mirror_shapes, ctrl, s=True, r=True)
    cmds.delete(mirror)
    shapes = cmds.listRelatives(ctrl, s=True, f=True)
    for shape in shapes:
        cmds.setAttr(shape + ".overrideEnabled", 1)
        cmds.setAttr(shape + ".overrideColor", idx)
    return ctrl
