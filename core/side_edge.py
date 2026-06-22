"""Side edge definition: existing edge, swap, or split (Q-Morph Sec 3.2.1)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

import bmesh
from mathutils import Vector

from .mesh_graph import MeshGraph

DEFAULT_SIDE_EPS = math.pi / 6.0  # 30 degrees


@dataclass
class SideEdgeResult:
    edge: Optional[bmesh.types.BMEdge]
    vert: bmesh.types.BMVert
    created: bool = False


def _bisector(
    graph: MeshGraph,
    vert: bmesh.types.BMVert,
    front_edges: List[bmesh.types.BMEdge],
    exclude: Optional[bmesh.types.BMEdge] = None,
) -> Vector:
    dirs: List[Vector] = []
    for fe in front_edges:
        if fe == exclude:
            continue
        other = MeshGraph.other_vert(fe, vert)
        d = (other.co - vert.co).normalized()
        dirs.append(d)
    if not dirs:
        return Vector((0.0, 1.0, 0.0))
    if len(dirs) == 1:
        return dirs[0]
    avg = dirs[0] + dirs[1]
    if avg.length_squared < 1e-12:
        avg = dirs[0].cross(Vector((0.0, 0.0, 1.0)))
    return avg.normalized()


def _angle_between(a: Vector, b: Vector) -> float:
    dot = max(-1.0, min(1.0, a.normalized().dot(b.normalized())))
    return math.acos(dot)


def find_existing_side_edge(
    graph: MeshGraph,
    vert: bmesh.types.BMVert,
    front_edge: bmesh.types.BMEdge,
    front_edges: Set[bmesh.types.BMEdge],
    epsilon: float = DEFAULT_SIDE_EPS,
) -> SideEdgeResult:
    """Select or create side edge at front corner vert."""
    adjacent_front = [e for e in graph.adjacent_front_edges(vert) if e != front_edge]
    ideal = _bisector(graph, vert, adjacent_front + [front_edge], exclude=front_edge)

    best_edge = None
    best_angle = math.pi

    for edge in vert.link_edges:
        if edge == front_edge:
            continue
        other = MeshGraph.other_vert(edge, vert)
        if other in front_edge.verts:
            continue
        direction = (other.co - vert.co).normalized()
        angle = _angle_between(ideal, direction)
        if angle < best_angle:
            best_angle = angle
            best_edge = edge

    if best_edge and best_angle < epsilon:
        return SideEdgeResult(edge=best_edge, vert=vert, created=False)

    # Try swap on opposite edge of adjacent triangle.
    swap_result = _try_swap_side(graph, vert, front_edge, ideal, front_edges, epsilon)
    if swap_result.edge:
        return swap_result

    # Split fallback.
    split_result = _try_split_side(graph, vert, front_edge, ideal, front_edges, epsilon)
    return split_result


def _try_swap_side(
    graph: MeshGraph,
    vert: bmesh.types.BMVert,
    front_edge: bmesh.types.BMEdge,
    ideal: Vector,
    front_edges: Set[bmesh.types.BMEdge],
    epsilon: float,
) -> SideEdgeResult:
    for f in vert.link_faces:
        if f not in graph.tri_faces:
            continue
        for e in f.edges:
            if vert in e.verts:
                continue
            if e in front_edges:
                continue
            opp_mid = (e.verts[0].co + e.verts[1].co) * 0.5
            vm = (opp_mid - vert.co).normalized()
            beta = _angle_between(ideal, vm)
            if beta < epsilon:
                if graph.swap_edge(e):
                    graph.refresh()
                    new_edge = graph.get_edge(vert, e.verts[0]) or graph.get_edge(vert, e.verts[1])
                    if new_edge:
                        return SideEdgeResult(edge=new_edge, vert=vert, created=True)
    return SideEdgeResult(edge=None, vert=vert)


def _try_split_side(
    graph: MeshGraph,
    vert: bmesh.types.BMVert,
    front_edge: bmesh.types.BMEdge,
    ideal: Vector,
    front_edges: Set[bmesh.types.BMEdge],
    epsilon: float,
) -> SideEdgeResult:
    for f in vert.link_faces:
        if f not in graph.tri_faces:
            continue
        for e in f.edges:
            if vert in e.verts:
                continue
            if e in front_edges:
                continue
            new_v = graph.split_edge_at_point(e, 0.5)
            if new_v:
                graph.refresh()
                new_edge = graph.get_edge(vert, new_v)
                return SideEdgeResult(edge=new_edge, vert=vert, created=True)
    return SideEdgeResult(edge=None, vert=vert)


def side_vertices_for_front(
    graph: MeshGraph,
    front_edge: bmesh.types.BMEdge,
    front_edges: Set[bmesh.types.BMEdge],
    epsilon: float = DEFAULT_SIDE_EPS,
) -> Tuple[Optional[bmesh.types.BMVert], Optional[bmesh.types.BMVert]]:
    """Define side edge endpoints at both ends of front edge."""
    v0, v1 = front_edge.verts
    left = find_existing_side_edge(graph, v0, front_edge, front_edges, epsilon)
    right = find_existing_side_edge(graph, v1, front_edge, front_edges, epsilon)

    top_v0 = MeshGraph.other_vert(left.edge, v0) if left.edge else None
    top_v1 = MeshGraph.other_vert(right.edge, v1) if right.edge else None
    return top_v0, top_v1
