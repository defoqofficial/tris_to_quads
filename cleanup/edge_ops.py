"""Local quad connectivity operations (STAR Fig 15)."""

from __future__ import annotations

import logging
from typing import Optional

import bmesh

from ..core.mesh_graph import MeshGraph

logger = logging.getLogger(__name__)


def edge_rotate(graph: MeshGraph, edge: bmesh.types.BMEdge) -> bool:
    """2-2 edge swap between two quads (edge rotate)."""
    if len(edge.link_faces) != 2:
        return False
    if any(len(f.verts) != 4 for f in edge.link_faces):
        return False
    try:
        bmesh.ops.rotate_edges(graph.bm, edges=[edge], ccw=False)
        graph.refresh()
        logger.debug(f"Edge rotate successful for edge {edge.index}")
        return True
    except Exception as e:
        logger.debug(f"Edge rotate failed: {e}")
        return False


def remove_doublet(graph: MeshGraph, vert: bmesh.types.BMVert) -> bool:
    """Remove valence-2 interior vertex (doublet removal)."""
    if graph.is_boundary_vert(vert):
        return False
    if graph.valence(vert) != 2:
        return False
    try:
        bmesh.ops.dissolve_verts(graph.bm, verts=[vert], use_face_split=False)
        graph.refresh()
        logger.debug(f"Doublet removed: vertex {vert.index}")
        return True
    except Exception as e:
        logger.debug(f"Doublet removal failed: {e}")
        return False


def try_improve_edge_flow(graph: MeshGraph) -> int:
    """Attempt edge rotates that improve valence regularity."""
    improved = 0
    graph.refresh()
    for edge in list(graph.bm.edges):
        if len(edge.link_faces) != 2:
            continue
        if any(len(f.verts) != 4 for f in edge.link_faces):
            continue
        v0, v1 = edge.verts
        before = sum(
            1 for v in (v0, v1) if not graph.is_regular(v)
        )
        if edge_rotate(graph, edge):
            after = sum(
                1 for v in (v0, v1) if not graph.is_regular(v)
            )
            if after < before:
                improved += 1
            elif after > before:
                edge_rotate(graph, edge)  # revert
    
    if improved > 0:
        logger.debug(f"Edge flow: {improved} edges improved")
    return improved


def remove_all_doublets(graph: MeshGraph) -> int:
    """Remove all valence-2 interior vertices."""
    removed = 0
    changed = True
    while changed:
        changed = False
        graph.refresh()
        for v in list(graph.bm.verts):
            if remove_doublet(graph, v):
                removed += 1
                changed = True
    
    if removed > 0:
        logger.info(f"Removed {removed} doublets")
    return removed
