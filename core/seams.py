"""Seam and transition operations (Q-Morph Sec 3.7)."""

from __future__ import annotations

import math
from typing import Optional, Set

import bmesh

from .edge_recovery import recover_edge
from .mesh_graph import MeshGraph

TRANSITION_RATIO = 2.5


def count_adjacent_quads(graph: MeshGraph, vert: bmesh.types.BMVert) -> int:
    return sum(1 for f in vert.link_faces if f in graph.quad_faces)


def needs_seam(
    graph: MeshGraph,
    vert: bmesh.types.BMVert,
    epsilon: float,
) -> bool:
    """Equation 5: seam when angle small or few adjacent quads."""
    front_edges = graph.adjacent_front_edges(vert)
    if len(front_edges) < 2:
        return False

    # Approximate angle between adjacent front edges at vert.
    dirs = []
    for fe in front_edges:
        other = MeshGraph.other_vert(fe, vert)
        dirs.append((other.co - vert.co).normalized())
    if len(dirs) < 2:
        return False
    dot = max(-1.0, min(1.0, dirs[0].dot(dirs[1])))
    alpha = math.acos(dot)
    nq = count_adjacent_quads(graph, vert)
    if alpha < epsilon / 2.0:
        return True
    if alpha < epsilon and nq < 5:
        return True
    return False


def needs_transition_seam(
    graph: MeshGraph,
    vert: bmesh.types.BMVert,
) -> bool:
    """Large length difference between adjacent front edges."""
    front_edges = graph.adjacent_front_edges(vert)
    if len(front_edges) < 2:
        return False
    lengths = [graph.edge_length(e) for e in front_edges]
    if not lengths:
        return False
    ratio = max(lengths) / max(min(lengths), 1e-8)
    return ratio > TRANSITION_RATIO


def perform_seam(
    graph: MeshGraph,
    vert: bmesh.types.BMVert,
    front_edges: Set[bmesh.types.BMEdge],
) -> bool:
    """Merge front neighbors across small angle (Fig 11)."""
    front = graph.adjacent_front_edges(vert)
    if len(front) < 2:
        return False

    # Find neighbors on front.
    neighbors = []
    for fe in front:
        neighbors.append(MeshGraph.other_vert(fe, vert))
    if len(neighbors) < 2:
        return False

    nk_m1, nk_p1 = neighbors[0], neighbors[1]

    if not recover_edge(graph, nk_m1, nk_p1, front_edges):
        return False

    # Merge nk_m1 and nk_p1 at midpoint.
    mid = (nk_m1.co + nk_p1.co) * 0.5
    try:
        bmesh.ops.pointmerge(
            graph.bm,
            verts=[nk_m1, nk_p1],
            merge_co=mid,
        )
        graph.refresh()
        return True
    except Exception:
        return False


def perform_transition_seam(
    graph: MeshGraph,
    vert: bmesh.types.BMVert,
) -> bool:
    """Split longer adjacent front edge at midpoint (Fig 12)."""
    front = graph.adjacent_front_edges(vert)
    if len(front) < 2:
        return False
    longest = max(front, key=graph.edge_length)
    new_v = graph.split_edge_at_point(longest, 0.5)
    graph.refresh()
    return new_v is not None
