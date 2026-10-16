

import maya.cmds as cmds


def groupss(*names):
    parent, path = None, ""
    for name in names:
        if cmds.objExists(name):
            child = name
        else:
            if parent is None:
                child = cmds.group(empty=True, name=name)
            else:
                child = cmds.group(empty=True, name=name, parent=parent)
        parent = child
        path += f"{name}|"
    path = path[:-1]
    child = cmds.ls(path, long=True)[0]
    return child


def group(*names):
    parent, path = None, ""
    for name in names:
        if cmds.objExists(name):
            child = name
        else:
            child = cmds.group(empty=True, name=name)
            if parent:
                child = cmds.parent(child, parent)[0]
        parent = child
        path += f"{name}|"
    path = path[:-1]
    child = cmds.ls(path, long=True)[0]
    return child


def parent(child, parent):
    parent = cmds.ls(parent, long=True)[0]
    child = cmds.parent(child, parent)[0]
    child = f"{parent}|{child}"
    return child


def descendant(node, type=None):
    descendant = cmds.listRelatives(node, ad=True, type=type, f=True)
    return [node] + descendant
