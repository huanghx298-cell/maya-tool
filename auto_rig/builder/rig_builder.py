

import time

import maya.cmds as cmds

import data.rig_data as data

import utils.mesh_utils as mesh_utils

import builder.rig_setup as rig_setup
import builder.rig_build as rig_build
import builder.rig_finalize as rig_finalize


def debug():

    rig_setup.create_curve()


def body_auto():

    start_time = time.perf_counter()

    rig_setup.biped()
    rig_build.biped_limb()
    rig_build.biped_spine()
    rig_build.biped_blend()
    rig_build.biped_hand()
    rig_build.biped_foot()
    rig_finalize.biped_space()
    rig_finalize.biped_twist()

    # RigPipeline.build_head()

    elapsed = time.perf_counter() - start_time

    print("\n" + "=" * 60)
    print("AUTO RIG LITE UE5 BUILD SUCCESS")
    print(f"BUILD TIME: {elapsed:.2f} seconds")
    print("=" * 60 + "\n")


def eye_autosss():

    meshes = cmds.ls(type="mesh", long=True)

    centers = []
    for mesh in meshes:
        vertices = cmds.ls(mesh + ".vtx[*]", flatten=True)
        centers.append(mesh_utils.vertex_center(vertices))
    count = len(centers)

    center = (
        sum(c[0] for c in centers) / count,
        sum(c[1] for c in centers) / count,
        sum(c[2] for c in centers) / count,
    )

    joint = cmds.createNode("joint")
    cmds.xform(joint, worldSpace=True, translation=center)

    return center


def eye_auto():

    def eye_preview():

        def find_x_extremes():
            left = right = None
            min_x, max_x = float("inf"), float("-inf")
            for vertex in vertices:
                vertex_id = vertex_ids[vertex]
                x = positions[vertex_id].x
                if x < min_x:
                    min_x = x
                    left = vertex
                if x > max_x:
                    max_x = x
                    right = vertex
            return left, right

        def split_upper_lower():
            min_pos = positions[vertex_ids[min_vertex]]
            max_pos = positions[vertex_ids[max_vertex]]
            upper = []
            lower = []
            for vertex in vertices:
                if vertex == min_vertex or vertex == max_vertex:
                    continue
                pos = positions[vertex_ids[vertex]]
                t = (pos.x - min_pos.x) / (max_pos.x - min_pos.x)
                line_y = min_pos.y + t * (max_pos.y - min_pos.y)
                if pos.y > line_y:
                    upper.append(vertex)
                else:
                    lower.append(vertex)
            upper.sort(key=lambda v: positions[vertex_ids[v]].x)
            lower.sort(key=lambda v: positions[vertex_ids[v]].x, reverse=True)
            return upper, lower

        min_vertex, max_vertex = find_x_extremes()
        upper, lower = split_upper_lower()
        upper = [min_vertex] + upper + [max_vertex]
        data.face["inner_eye"]["min"] = min_vertex
        data.face["inner_eye"]["max"] = max_vertex
        data.face["inner_eye"]["loop"] = upper + lower
        data.face["inner_eye"]["upper"] = upper

    def eye_adjust():

        def curve(p0, p1, v0, t):
            return p0 + t * v0 + t * t * (p1 - p0 - v0)

        def p1_tangent(p0, p1, v0):
            return 2 * (p1 - p0) - v0

        def abc():
            upper = data.face["inner_eye"]["upper"]
            data.face["inner_eye"]["tangents"] = []
            for i in range(len(upper) - 1):
                p0 = positions[vertex_ids[upper[i]]]
                p1 = positions[vertex_ids[upper[i + 1]]]
                if i == 0:
                    v0 = p1 - p0
                data.face["inner_eye"]["tangents"].append(v0)
                v0 = p1_tangent(p0, p1, v0)

    vertices = mesh_utils.get_vertex(data.face.get("inner_eye"))
    mesh = vertices[0].split(".vtx[")[0]
    positions = mesh_utils.vertex_position(mesh)
    vertex_ids = {vertex: int(vertex.split(
        ".vtx[")[-1].split("]")[0])for vertex in vertices}


def reload_scene():
    scene = cmds.file(query=True, sceneName=True)
    cmds.file(scene, open=True, force=True)


def get_selection():
    return cmds.ls(selection=True, long=True) or []
