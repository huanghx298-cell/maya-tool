

import maya.cmds as cmds

import utils.dag_utils as dag_utils
import utils.transform_utils as transform_utils


def duplicate(jnts, suffix):
    root_n = jnts[0].split("|")[-1]
    grp = dag_utils.group(
        "skeleton", f"{suffix}_joints", f"{suffix}_jnt_{root_n}_GRP")
    suffix_jnts = []
    parent = grp
    for jnt in jnts:
        jnt_n = jnt.split("|")[-1]
        suffix_jnt = cmds.createNode("joint", n=f"{jnt_n}_{suffix}_JNT")
        suffix_jnt = dag_utils.parent(suffix_jnt, parent)
        cmds.matchTransform(suffix_jnt, jnt)
        transform_utils.from_joint_orient(suffix_jnt)
        transform_utils.to_opm(suffix_jnt)
        suffix_jnts.append(suffix_jnt)
        parent = suffix_jnt
    return suffix_jnts
