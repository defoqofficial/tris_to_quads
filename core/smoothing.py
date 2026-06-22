"""Local and global smoothing (Q-Morph Sec 3.4, STAR Sec 4.2)."""

from __future__ import annotations

from typing import Iterable, Optional, Set

import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from .mesh_graph import MeshGraph

TRANSITION_RATIO = 2.5


def _laplacian_target(vert: bmesh.types.BMVert) -> Vector:
    if not vert.link_edges:
        return vert.co.copy()
    acc = Vector((0.0, 0.0, 0.0))
    for edge in vert.link_edges:
        other = edge.other_vert(vert)
        acc += other.co
    return acc / len(vert.link_edges)


def _project_tangent(delta: Vector, normal: Vector) -> Vector:
    n = normal.normalized()
    return delta - n * delta.dot(n)


def _is_inverted(face: bmesh.types.BMFace) -> bool:
    return face.normal.length_squared < 1e-12 or face.calc_area() < 1e-10


def smooth_vert_local(
    graph: MeshGraph,
    vert: bmesh.types.BMVert,
    front_verts: Set[bmesh.types.BMVert],
    bvh: Optional[BVHTree] = None,
    preserve_boundary: bool = True,
) -> None:
    """Smooth single vertex with inversion guard."""
    if preserve_boundary and graph.is_boundary_vert(vert):
        return

    old_co = vert.co.copy()
    normal = graph.tangent_normal(vert)
    target = _laplacian_target(vert)

    if vert in front_verts and len(vert.link_faces) >= 2:
        # Blacker-style: blend toward isoparametric midpoint for front row nodes.
        quad_neighbors = [v for f in vert.link_faces if f in graph.quad_faces for v in f.verts if v != vert]
        if quad_neighbors:
            qacc = Vector((0.0, 0.0, 0.0))
            for qv in quad_neighbors:
                qacc += qv.co
            target = target.lerp(qacc / len(quad_neighbors), 0.5)

    tr = graph.boundary_edge_ratio()
    if tr > TRANSITION_RATIO:
        # Use average of all connected edge lengths for transition sizing.
        lengths = [graph.edge_length(e) for e in vert.link_edges]
        if lengths:
            avg_len = sum(lengths) / len(lengths)
            direction = (target - vert.co)
            if direction.length > avg_len:
                direction = direction.normalized() * avg_len
            target = vert.co + direction

    delta = _project_tangent(target - vert.co, normal)
    new_co = vert.co + delta * 0.5

    if bvh is not None:
        new_co = graph.project_to_surface(new_co, bvh)

    vert.co = new_co
    graph.bm.normal_update()

    # Inversion guard: revert if neighbors inverted.
    for f in vert.link_faces:
        if _is_inverted(f):
            vert.co = old_co
            graph.bm.normal_update()
            return


def smooth_local_around_quad(
    graph: MeshGraph,
    quad_verts: Iterable[bmesh.types.BMVert],
    front_verts: Set[bmesh.types.BMVert],
    bvh: Optional[BVHTree] = None,
    preserve_boundary: bool = True,
) -> None:
    """Smooth quad corners and their edge neighbors."""
    to_smooth: Set[bmesh.types.BMVert] = set(quad_verts)
    for v in quad_verts:
        for edge in v.link_edges:
            to_smooth.add(edge.other_vert(v))
    for v in to_smooth:
        smooth_vert_local(graph, v, front_verts, bvh, preserve_boundary)


def smooth_global(
    graph: MeshGraph,
    iterations: int = 5,
    preserve_boundary: bool = True,
) -> None:
    """Constrained tangent-space Laplacian smoothing (STAR Sec 4.2)."""
    if iterations <= 0:
        return
    bvh = graph.build_bvh()
    front_verts: Set[bmesh.types.BMVert] = set()
    for _ in range(iterations):
        graph.bm.verts.ensure_lookup_table()
        moves = []
        for v in graph.bm.verts:
            if preserve_boundary and graph.is_boundary_vert(v):
                continue
            normal = graph.tangent_normal(v)
            target = _laplacian_target(v)
            delta = _project_tangent(target - v.co, normal)
            new_co = graph.project_to_surface(v.co + delta * 0.35, bvh)
            moves.append((v, new_co))
        for v, co in moves:
            v.co = co
        graph.bm.normal_update()
