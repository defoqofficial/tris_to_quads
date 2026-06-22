"""Top edge recovery via edge swapping (Q-Morph Algorithms 1–2, Sec 3.2.2–3.2.3)."""

from __future__ import annotations

from typing import List, Optional, Set

import bmesh
from mathutils import Vector

from .mesh_graph import MeshGraph

MAX_RECOVERY_STEPS = 128


def _project_to_tangent(vec: Vector, normal: Vector) -> Vector:
    n = normal.normalized()
    return vec - n * vec.dot(n)


def _tangent_dot(a: Vector, b: Vector, normal: Vector) -> float:
    ta = _project_to_tangent(a, normal)
    tb = _project_to_tangent(b, normal)
    if ta.length_squared < 1e-12 or tb.length_squared < 1e-12:
        return 0.0
    return ta.normalized().dot(tb.normalized())


def _edge_intersects_segment_3d(
    graph: MeshGraph,
    edge: bmesh.types.BMEdge,
    p0: Vector,
    p1: Vector,
) -> bool:
    """Check if edge intersects segment p0-p1 in tangent plane at midpoint."""
    a, b = edge.verts[0].co, edge.verts[1].co
    mid = (p0 + p1) * 0.5
    normal = graph.tangent_normal_at_co(mid)
    seg = p1 - p0
    ea = a - p0
    eb = b - p0
    # 2D cross-like test in tangent plane
    def cross2(u: Vector, v: Vector) -> float:
        tu = _project_to_tangent(u, normal)
        tv = _project_to_tangent(v, normal)
        return tu.x * tv.y - tu.y * tv.x

    d1 = cross2(seg, ea)
    d2 = cross2(seg, eb)
    d3 = cross2(eb - ea, p0 - a)
    d4 = cross2(eb - ea, p1 - a)
    return (d1 * d2 < 0) and (d3 * d4 < 0)


def build_intersection_list(
    graph: MeshGraph,
    nc: bmesh.types.BMVert,
    nd: bmesh.types.BMVert,
    front_edges: Set[bmesh.types.BMEdge],
) -> Optional[List[bmesh.types.BMEdge]]:
    """Algorithm 2: build Lambda(S) list of edges the recovered edge must cross."""
    if graph.edge_exists(nc, nd):
        return []

    lam: List[bmesh.types.BMEdge] = []
    vs = nd.co - nc.co
    normal = graph.tangent_normal(nc)

    # Find starting triangle at nc.
    start_face = None
    for f in nc.link_faces:
        if f in graph.tri_faces:
            start_face = f
            break
    if start_face is None:
        return None

    # Walk from nc toward nd.
    cur_face = start_face
    visited: Set[bmesh.types.BMFace] = set()
    steps = 0

    while steps < MAX_RECOVERY_STEPS:
        steps += 1
        if nd in cur_face.verts:
            return lam
        if cur_face in visited:
            break
        visited.add(cur_face)

        # Opposite edge on current tri (from nc perspective or walk direction).
        walk_from = nc if nc in cur_face.verts else None
        if walk_from is None:
            for v in cur_face.verts:
                if _tangent_dot(v.co - nc.co, vs, normal) > 0:
                    walk_from = v
                    break
        if walk_from is None:
            return None

        ei = None
        for e in cur_face.edges:
            if walk_from not in e.verts:
                ei = e
                break
        if ei is None:
            return None
        if ei in front_edges:
            return None
        if ei not in lam:
            lam.append(ei)

        # Move to adjacent triangle across ei.
        next_face = None
        for f in ei.link_faces:
            if f != cur_face and f in graph.tri_faces:
                next_face = f
                break
        if next_face is None:
            break
        cur_face = next_face

    return lam


def recover_edge(
    graph: MeshGraph,
    nc: bmesh.types.BMVert,
    nd: bmesh.types.BMVert,
    front_edges: Set[bmesh.types.BMEdge],
) -> bool:
    """Algorithm 1: recover direct edge nc-nd via edge swaps."""
    if graph.edge_exists(nc, nd):
        return True

    lam = build_intersection_list(graph, nc, nd, front_edges)
    if lam is None:
        return False

    steps = 0
    while not graph.edge_exists(nc, nd) and steps < MAX_RECOVERY_STEPS:
        steps += 1
        if not lam:
            lam = build_intersection_list(graph, nc, nd, front_edges)
            if not lam:
                break

        ei = lam[0]
        if not ei.is_valid or len(ei.link_faces) != 2:
            lam.pop(0)
            continue
        if not graph.swap_edge(ei):
            lam.pop(0)
            continue

        if graph.edge_exists(nc, nd):
            return True

        # Rebuild lambda after swap.
        lam = build_intersection_list(graph, nc, nd, front_edges)
        if lam is None:
            break

    return graph.edge_exists(nc, nd)
