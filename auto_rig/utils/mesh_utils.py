

import maya.cmds as cmds
import maya.api.OpenMaya as om

from collections import defaultdict


def get_vertex(component):
    result = cmds.polyListComponentConversion(component, toVertex=True)
    return cmds.ls(result, flatten=True)


def order_vertex(edges):
    graph = defaultdict(list)
    for edge in edges:
        a, b = get_vertex(edge)
        graph[a].append(b)
        graph[b].append(a)
    up_axis = cmds.upAxis(q=True, axis=True)
    up_i = {"x": 0, "y": 1, "z": 2}[up_axis]
    verts = get_vertex(edges)
    starts = [v for v in verts if len(graph[v]) == 1] or cmds.error(
        "Edge selection must be an open chain.")
    start = max(starts, key=lambda v: cmds.pointPosition(v, w=True)[up_i])
    ordered = []
    current = start
    previous = None
    while current is not None:
        ordered.append(current)
        next_vertex = None
        for v in graph[current]:
            if v != previous:
                next_vertex = v
                break
        previous = current
        current = next_vertex
    return ordered


def vertex_position(mesh):
    selection = om.MSelectionList()
    selection.add(mesh)
    dag_path = selection.getDagPath(0)
    fn_mesh = om.MFnMesh(dag_path)
    space = om.MSpace.kWorld
    positions = fn_mesh.getPoints(space)
    return positions


def vertex_center(vertex_groups):
    # Kept at this level to avoid repeated Maya API calls
    # from lower-level abstraction.
    is_grouped = isinstance(vertex_groups[0], list)
    if not is_grouped:
        vertex_groups = [vertex_groups]
    mesh = vertex_groups[0][0].split(".vtx[")[0]
    fn_mesh = om.MFnMesh(om.MSelectionList().add(mesh).getDagPath(0))
    points = fn_mesh.getPoints(om.MSpace.kWorld)
    centers = []
    for group in vertex_groups:
        pos = []
        for vtx in group:
            v_id = int(vtx.split("[")[-1].split("]")[0])
            pos.append(points[v_id])
        center = (
            (min(p.x for p in pos) + max(p.x for p in pos)) / 2,
            (min(p.y for p in pos) + max(p.y for p in pos)) / 2,
            (min(p.z for p in pos) + max(p.z for p in pos)) / 2,
        )
        centers.append(center)
    return centers if is_grouped else centers[0]


def normal(obj, x=None, y=None, z=None):
    rotate = (
        0 if x is None else x,
        0 if y is None else y,
        0 if z is None else z,
    )
    cmds.rotate(*rotate, obj, relative=True, objectSpace=True)
    cmds.makeIdentity(obj, apply=True, rotate=True)


def edge_group(edges):
    edge_ids = {int(e.split("[")[-1].split("]")[0]) for e in edges}
    mesh = edges[0].split(".e[")[0]
    it = om.MItMeshEdge(om.MSelectionList().add(mesh).getDagPath(0))
    vertex_to_edges = defaultdict(list)
    edge_to_vertices = {}
    while not it.isDone():
        edge_id = it.index()
        if edge_id in edge_ids:
            v0 = it.vertexId(0)
            v1 = it.vertexId(1)
            edge_to_vertices[edge_id] = (v0, v1)
            vertex_to_edges[v0].append(edge_id)
            vertex_to_edges[v1].append(edge_id)
        it.next()
    visited_edges = set()
    groups = []
    for edge_id in edge_ids:
        if edge_id in visited_edges:
            continue
        stack = [edge_id]
        edge_group = []
        while stack:
            current = stack.pop()
            if current in visited_edges:
                continue
            visited_edges.add(current)
            edge_group.append(f"{mesh}.e[{current}]")
            for vtx in edge_to_vertices[current]:
                for neighbor in vertex_to_edges[vtx]:
                    if neighbor not in visited_edges:
                        stack.append(neighbor)
        groups.append(edge_group)
    return groups
