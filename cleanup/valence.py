"""Irregular vertex reduction (STAR Sec 2.1, 4.3.4)."""

from __future__ import annotations

import logging
from typing import List, Tuple

import bmesh

from ..core.mesh_graph import MeshGraph
from .edge_ops import edge_rotate, try_improve_edge_flow

logger = logging.getLogger(__name__)


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
                    logger.debug(f"Pentagon-triangle swap improved valence from {before} to {after}")
                    return True
                edge_rotate(graph, edge)  # revert
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
                    logger.debug(f"Valence-3 pair move improved valence from {before} to {after}")
                    return True
                edge_rotate(graph, edge)  # revert
    return False


def cleanup_valence(graph: MeshGraph, passes: int = 3) -> Tuple[int, int]:
    """
    Run STAR-inspired valence cleanup passes.
    Returns (irregular_before, irregular_after).
    """
    before = len(irregular_vertices(graph))
    logger.info(f"Valence cleanup starting with {before} irregular vertices")
    
    for pass_num in range(passes):
        graph.refresh()
        improved = 0
        for v in list(graph.bm.verts):
            if not graph.is_regular(v):
                if try_pentagon_triangle_swap(graph, v) or try_valence3_pair_move(graph, v):
                    improved += 1
        
        edge_flow_improved = try_improve_edge_flow(graph)
        logger.debug(f"Cleanup pass {pass_num + 1}: {improved} verts improved, {edge_flow_improved} edge flows improved")
    
    after = len(irregular_vertices(graph))
    logger.info(f"Valence cleanup complete: {before} -> {after} irregular vertices")
    return before, after
