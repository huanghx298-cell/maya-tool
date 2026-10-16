
import colorsys
import math
from collections import defaultdict

import maya.api.OpenMaya as om
import maya.cmds as cmds


class Mesh:

    @staticmethod
    def get_edges(components):
        result = cmds.polyListComponentConversion(components, toEdge=True)
        return cmds.ls(result, flatten=True)

    @staticmethod
    def get_faces(components):
        result = cmds.polyListComponentConversion(components, toFace=True)
        return cmds.ls(result, flatten=True)

    @staticmethod
    def get_vertex_group_centers(vertex_groups):
        # redesigning...................................
        is_grouped = isinstance(vertex_groups[0], list)
        if not is_grouped:
            vertex_groups = [vertex_groups]
        mesh = vertex_groups[0][0].split(".vtx[")[0]
        fn_mesh = om.MFnMesh(om.MSelectionList().add(mesh).getDagPath(0))
        points = fn_mesh.getPoints(om.MSpace.kWorld)
        centers = []
        for group in vertex_groups:
            x = y = z = 0.0
            for vtx in group:
                v_id = int(vtx.split("[")[-1].split("]")[0])
                p = points[v_id]
                x += p.x
                y += p.y
                z += p.z
            count = len(group)
            centers.append((x / count, y / count, z / count))
        return centers if is_grouped else centers[0]


class Math:

    @staticmethod
    def midpoint(point_a, point_b):
        x = (point_a[0] + point_b[0]) * 0.5
        y = (point_a[1] + point_b[1]) * 0.5
        z = (point_a[2] + point_b[2]) * 0.5
        return [x, y, z]

    @staticmethod
    def distance_squared(point_a, point_b):
        dx = point_a[0] - point_b[0]
        dy = point_a[1] - point_b[1]
        dz = point_a[2] - point_b[2]
        return dx * dx + dy * dy + dz * dz

    @staticmethod
    def distance(point_a, point_b):
        distance_squared = Math.distance_squared(point_a, point_b)
        return math.sqrt(distance_squared)

    @staticmethod
    def group_by_direction(origin, points):
        clusters = []
        cos_45 = math.cos(math.radians(45))
        while points:
            # Create initial reference direction
            point_a = points[0]
            ax = point_a[0] - origin[0]
            ay = point_a[1] - origin[1]
            az = point_a[2] - origin[2]
            alen = math.sqrt(ax*ax + ay*ay + az*az)
            ax, ay, az = ax / alen, ay / alen, az / alen
            points = points[1:]
            # Update the reference direction using the first point within 90°
            result = []
            start_idx = None
            for i, point_b in enumerate(points):
                bx = point_b[0] - origin[0]
                by = point_b[1] - origin[1]
                bz = point_b[2] - origin[2]
                blen = math.sqrt(bx*bx + by*by + bz*bz)
                bx, by, bz = bx / blen, by / blen, bz / blen
                if ax * bx + ay * by + az * bz > 1e-6:
                    avg_x, avg_y, avg_z = ax + bx, ay + by, az + bz
                    avg_len = math.sqrt(avg_x*avg_x+avg_y*avg_y+avg_z*avg_z)
                    avg_x, avg_y, avg_z = avg_x/avg_len, avg_y/avg_len, avg_z/avg_len
                    dot_b = ax * bx + ay * by + az * bz
                    result.append((point_a, 1.0))
                    result.append((point_b, dot_b))
                    start_idx = i + 1
                    break
            if start_idx is None:
                result.append((point_a, 1.0))
                clusters.append(result)
                continue
            # Collect points within 45° of the reference direction
            remaining_points = points[:start_idx - 1]
            for point_b in points[start_idx:]:
                bx = point_b[0] - origin[0]
                by = point_b[1] - origin[1]
                bz = point_b[2] - origin[2]
                blen = math.sqrt(bx*bx + by*by + bz*bz)
                bx, by, bz = bx / blen, by / blen, bz / blen
                cluster_dot = avg_x * bx + avg_y * by + avg_z * bz
                if cluster_dot >= cos_45:
                    dot_b = ax * bx + ay * by + az * bz
                    result.append((point_b, dot_b))
                else:
                    remaining_points.append(point_b)
            points = remaining_points
            clusters.append(result)
        return clusters


class Transform:

    @staticmethod
    def from_opm(node):
        local_m = cmds.xform(node, q=True, m=True, os=True)
        old_m = cmds.getAttr(node + ".offsetParentMatrix")
        new_m = [0] * 16
        for row in range(4):
            for col in range(4):
                new_m[row*4 + col] = sum(local_m[row*4 + k] * old_m[k*4 + col]
                                         for k in range(4))
        tm = om.MTransformationMatrix(om.MMatrix(new_m))
        translation = tm.translation(om.MSpace.kTransform)
        rotate_order = cmds.getAttr(node + ".rotateOrder")
        rotation = tm.rotation().asEulerRotation()
        rotation.reorderIt(rotate_order)
        scale = tm.scale(om.MSpace.kTransform)
        identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
        cmds.setAttr(node + ".offsetParentMatrix", *identity, type="matrix")
        cmds.setAttr(node + ".translate",
                     translation.x,
                     translation.y,
                     translation.z)
        cmds.setAttr(node + ".rotate",
                     math.degrees(rotation.x),
                     math.degrees(rotation.y),
                     math.degrees(rotation.z))
        cmds.setAttr(node + ".scale", *scale)

    @staticmethod
    def bake_joint_orient_to_rotate(joint):
        rx, ry, rz = cmds.getAttr(joint + ".rotate")[0]
        jox, joy, joz = cmds.getAttr(joint + ".jointOrient")[0]
        rotate_order = cmds.getAttr(joint + ".rotateOrder")
        rot_q = om.MEulerRotation(
            math.radians(rx),
            math.radians(ry),
            math.radians(rz),
            rotate_order
        ).asQuaternion()
        jo_q = om.MEulerRotation(
            math.radians(jox),
            math.radians(joy),
            math.radians(joz),
            rotate_order
        ).asQuaternion()
        new_rot = rot_q * jo_q
        new_euler = new_rot.asEulerRotation()
        new_euler.reorderIt(rotate_order)
        cmds.setAttr(joint + ".jointOrient", 0, 0, 0)
        cmds.setAttr(
            joint + ".rotate",
            math.degrees(new_euler.x),
            math.degrees(new_euler.y),
            math.degrees(new_euler.z)
        )


class MaterialUtils:

    @staticmethod
    def create_band_materials(count):
        sgs = []
        for i in range(count):
            mat = cmds.createNode("lambert")
            h = float(i) / count
            r, g, b = colorsys.hsv_to_rgb(h, 1.0, 1.0)
            cmds.setAttr(f"{mat}.color", r, g, b, type="double3")
            sg = cmds.sets(r=True, nss=True, em=True, n=f"{mat}SG")
            cmds.connectAttr(f"{mat}.outColor", f"{sg}.surfaceShader", f=True)
            sgs.append(sg)
        return sgs


class SkinWeight:

    @staticmethod
    def jnt_hier_dist(mesh, vtxs_id_grps, jnts_grps):
        mesh_fn = om.MFnMesh(om.MSelectionList().add(mesh).getDagPath(0))
        vtxs_p = mesh_fn.getPoints(om.MSpace.kWorld)
        vtx_plane_distances = {}
        vtx_jnts_weight = {}
        for vtxs_id, jnts in zip(vtxs_id_grps, jnts_grps):
            planes = {}
            for i in range(len(jnts) - 1):
                dag = om.MSelectionList().add(jnts[i]).getDagPath(0)
                jnt_p = om.MFnTransform(dag).translation(om.MSpace.kWorld)
                next_dag = om.MSelectionList().add(jnts[i + 1]).getDagPath(0)
                next_p = om.MFnTransform(
                    next_dag).translation(om.MSpace.kWorld)
                direction = next_p - jnt_p
                length = direction.length()
                planes[i] = {
                    "start_jnt": jnts[i],
                    "end_jnt": jnts[i + 1],
                    "start_p": jnt_p,
                    "end_p": next_p,
                    "mid_p": (jnt_p + next_p) * 0.5,
                    "n": direction.normal(),
                    "length": length,
                }
            for vtx_id in vtxs_id:
                vtx_p = vtxs_p[vtx_id]
                nearest_plane_id = None
                nearest_distance = float("inf")
                nearest_signed_distance = None
                for plane_id, plane in planes.items():
                    signed_dist = om.MVector(
                        vtx_p - plane["mid_p"]) * plane["n"]
                    distance = abs(signed_dist)
                    if distance < nearest_distance:
                        nearest_distance = distance
                        nearest_signed_distance = signed_dist
                        nearest_plane_id = plane_id
                plane = planes[nearest_plane_id]
                proj = om.MVector(vtx_p - plane["start_p"]) * plane["n"]
                proj = max(0.0, min(plane["length"], proj))
                raw_ratio = proj / plane["length"]
                fade_start = 0.7
                ratio = 0.0 if raw_ratio <= fade_start else (
                    raw_ratio - fade_start) / (1.0 - fade_start)
                vtx_plane_distances[vtx_id] = {
                    "plane_id": nearest_plane_id,
                    "signed_distance": nearest_signed_distance,
                    "weight_a": 1.0 - ratio,
                    "weight_b": ratio,
                }
                vtx_jnts_weight[vtx_id] = {
                    plane["start_jnt"]: 1.0 - ratio,
                    plane["end_jnt"]: ratio,
                }
        return vtx_jnts_weight
