"""Irregular vertex reduction (STAR Sec 2.1, 4.3.4)."""

from __future__ import annotations

from typing import List, Tuple

import bmesh

from ..core.mesh_graph import MeshGraph
from .edge_ops import edge_rotate, try_improve_edge_flow


def irregular_vertices(graph: MeshGraph) -> List[bmesh.types.BMVert]:
    return [v for v in graph.bm.verts if not graph.is_regular(v)]


def valence_deviation_score(graph: MeshGraph) -> int:
    return sum(
        abs(graph.valence(v) - graph.target_valence(v))
        for v in graph.bm.verts
    )


def try_pentagon_triangle_swap(graph: MeshGraph, vert: bmesh.types.BMVert) -> bool:
    """
    Local move for valence-5 interior vertex adjacent to a triangle.
    Attempt edge rotate on a surrounding quad edge to reduce irregularity.
    """
    if graph.valence(vert) != 5:
        return False
    for edge in vert.link_edges:
        if len(edge.link_faces) == 2 and all(len(f.verts) == 4 for f in edge.link_faces):
            before = valence_deviation_score(graph)
            if edge_rotate(graph, edge):
                after = valence_deviation_score(graph)
                if after < before:
                    return True
                edge_rotate(graph, edge)
    return False


def try_valence3_pair_move(graph: MeshGraph, vert: bmesh.types.BMVert) -> bool:
    """Improve valence-3 interior nodes via edge rotate."""
    if graph.valence(vert) != 3 or graph.is_boundary_vert(vert):
        return False
    for edge in vert.link_edges:
        if len(edge.link_faces) == 2 and all(len(f.verts) == 4 for f in edge.link_faces):
            before = valence_deviation_score(graph)
            if edge_rotate(graph, edge):
                after = valence_deviation_score(graph)
                if after < before:
                    return True
                edge_rotate(graph, edge)
    return False


def cleanup_valence(graph: MeshGraph, passes: int = 3) -> Tuple[int, int]:
    """
    Run STAR-inspired valence cleanup passes.
    Returns (irregular_before, irregular_after).
    """
    before = len(irregular_vertices(graph))
    for _ in range(passes):
        graph.refresh()
        for v in list(graph.bm.verts):
            if not graph.is_regular(v):
                try_pentagon_triangle_swap(graph, v)
                try_valence3_pair_move(graph, v)
        try_improve_edge_flow(graph)
    after = len(irregular_vertices(graph))
    return before, after
