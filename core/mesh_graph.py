"""bmesh-backed mesh graph for Q-Morph quad conversion."""

from __future__ import annotations

import logging
import math
from enum import IntEnum
from typing import Iterable, List, Optional, Set, Tuple

import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

logger = logging.getLogger(__name__)


class FaceKind(IntEnum):
    TRI = 0
    QUAD = 1


class MeshGraph:
    """Wraps bmesh and tracks triangle vs quad face membership."""

    def __init__(self, bm: bmesh.types.BMesh):
        self.bm = bm
        self.quad_faces: Set[bmesh.types.BMFace] = set()
        self.tri_faces: Set[bmesh.types.BMFace] = set()
        self._rebuild_face_sets()

    def _rebuild_face_sets(self) -> None:
        self.bm.faces.ensure_lookup_table()
        self.quad_faces = {f for f in self.bm.faces if len(f.verts) == 4}
        self.tri_faces = {f for f in self.bm.faces if len(f.verts) == 3}

    def refresh(self) -> None:
        self.bm.verts.ensure_lookup_table()
        self.bm.edges.ensure_lookup_table()
        self.bm.faces.ensure_lookup_table()
        self._rebuild_face_sets()

    def face_kind(self, face: bmesh.types.BMFace) -> FaceKind:
        """Classify face kind with stricter checking to avoid ngons."""
        if face in self.quad_faces:
            return FaceKind.QUAD
        if face in self.tri_faces:
            return FaceKind.TRI
        # Log unexpected face type for diagnostics
        logger.debug(f"Unexpected face with {len(face.verts)} vertices")
        return FaceKind.TRI  # Default fallback, but logged

    def is_boundary_edge(self, edge: bmesh.types.BMEdge) -> bool:
        return edge.is_boundary or len(edge.link_faces) == 1

    def is_front_edge(self, edge: bmesh.types.BMEdge) -> bool:
        """Edge between one quad and one triangle, or mesh boundary with a tri."""
        kinds = {self.face_kind(f) for f in edge.link_faces}
        if FaceKind.QUAD in kinds and FaceKind.TRI in kinds:
            return True
        if len(edge.link_faces) == 1 and FaceKind.TRI in kinds:
            return True
        return False

    def get_front_edges(self) -> List[bmesh.types.BMEdge]:
        return [e for e in self.bm.edges if self.is_front_edge(e)]

    def get_boundary_edges(self) -> List[bmesh.types.BMEdge]:
        return [e for e in self.bm.edges if self.is_boundary_edge(e)]

    def adjacent_front_edges(self, vert: bmesh.types.BMVert) -> List[bmesh.types.BMEdge]:
        return [e for e in vert.link_edges if self.is_front_edge(e)]

    def edge_length(self, edge: bmesh.types.BMEdge) -> float:
        return edge.calc_length()

    def vert_co(self, vert: bmesh.types.BMVert) -> Vector:
        return vert.co.copy()

    def tangent_normal(self, vert: bmesh.types.BMVert) -> Vector:
        n = Vector((0.0, 0.0, 0.0))
        for f in vert.link_faces:
            n += f.normal
        if n.length_squared < 1e-12:
            return Vector((0.0, 0.0, 1.0))
        return n.normalized()

    def tangent_normal_at_co(self, co: Vector) -> Vector:
        """Average normal of the nearest vertex to co."""
        best = None
        best_dist = 1e18
        self.bm.verts.ensure_lookup_table()
        for v in self.bm.verts:
            d = (v.co - co).length_squared
            if d < best_dist:
                best_dist = d
                best = v
        if best is None:
            return Vector((0.0, 0.0, 1.0))
        return self.tangent_normal(best)

    @staticmethod
    def other_vert(edge: bmesh.types.BMEdge, vert: bmesh.types.BMVert) -> bmesh.types.BMVert:
        return edge.verts[0] if edge.verts[1] == vert else edge.verts[1]

    def face_normal(self, face: bmesh.types.BMFace) -> Vector:
        return face.normal.copy()

    def angle_at_vert_in_face(
        self, vert: bmesh.types.BMVert, face: bmesh.types.BMFace
    ) -> float:
        verts = list(face.verts)
        idx = verts.index(vert)
        v_prev = verts[(idx - 1) % len(verts)]
        v_next = verts[(idx + 1) % len(verts)]
        a = (v_prev.co - vert.co).normalized()
        b = (v_next.co - vert.co).normalized()
        dot = max(-1.0, min(1.0, a.dot(b)))
        return math.acos(dot)

    def front_angle_at_vert(self, vert: bmesh.types.BMVert) -> float:
        """Approximate front angle by summing tri angles at vert (Q-Morph Sec 3.1)."""
        total = 0.0
        for f in vert.link_faces:
            if f in self.tri_faces:
                total += self.angle_at_vert_in_face(vert, f)
        return total

    def swap_edge(self, edge: bmesh.types.BMEdge) -> bool:
        """Flip diagonal between two adjacent triangles."""
        if len(edge.link_faces) != 2:
            return False
        if any(len(f.verts) != 3 for f in edge.link_faces):
            return False
        try:
            bmesh.ops.rotate_edges(self.bm, edges=[edge], ccw=False)
            self.refresh()
            return True
        except Exception:
            return False

    def split_edge_at_point(
        self, edge: bmesh.types.BMEdge, factor: float = 0.5
    ) -> Optional[bmesh.types.BMVert]:
        """Split edge and return the new vertex."""
        v0, v1 = edge.verts
        co = v0.co.lerp(v1.co, factor)
        try:
            result = bmesh.ops.subdivide_edges(
                self.bm, edges=[edge], cuts=1, geom_intersect=False
            )
            self.refresh()
            new_verts = [g for g in result.get("geom", []) if isinstance(g, bmesh.types.BMVert)]
            if not new_verts:
                return None
            new_vert = new_verts[0]
            new_vert.co = co
            return new_vert
        except Exception:
            return None

    def edge_exists(self, v0: bmesh.types.BMVert, v1: bmesh.types.BMVert) -> bool:
        return v0 in v1.link_verts

    def get_edge(self, v0: bmesh.types.BMVert, v1: bmesh.types.BMVert) -> Optional[bmesh.types.BMEdge]:
        for e in v0.link_edges:
            if v1 in e.verts:
                return e
        return None

    def opposite_vert_in_tri(
        self, edge: bmesh.types.BMEdge, face: bmesh.types.BMFace
    ) -> Optional[bmesh.types.BMVert]:
        for v in face.verts:
            if v not in edge.verts:
                return v
        return None

    def tris_between(
        self,
        v0: bmesh.types.BMVert,
        v1: bmesh.types.BMVert,
        max_steps: int = 256,
    ) -> Optional[List[bmesh.types.BMFace]]:
        """Walk triangle fan from v0 toward v1; return tri path if found."""
        if v0 == v1:
            return []
        visited: Set[bmesh.types.BMFace] = set()
        queue: List[Tuple[bmesh.types.BMVert, List[bmesh.types.BMFace]]] = [(v0, [])]
        while queue:
            cur, path = queue.pop(0)
            if len(path) > max_steps:
                continue
            for f in cur.link_faces:
                if f not in self.tri_faces or f in visited:
                    continue
                visited.add(f)
                for v in f.verts:
                    if v == cur:
                        continue
                    if v == v1:
                        return path + [f]
                    queue.append((v, path + [f]))
        return None

    def collect_tris_in_quad_region(
        self,
        corners: Tuple[bmesh.types.BMVert, ...],
        front_edge: bmesh.types.BMEdge,
    ) -> Set[bmesh.types.BMFace]:
        """Collect triangle faces inside the quad bounded by corners."""
        corner_set = set(corners)
        
        # Explicitly pick seed faces from the tri-side only
        seed_faces: Set[bmesh.types.BMFace] = set()
        for face in front_edge.link_faces:
            if face in self.tri_faces:
                seed_faces.add(face)
        
        if not seed_faces:
            logger.debug("collect_tris_in_quad_region: no tri-side seed faces found")
            return set()

        collected: Set[bmesh.types.BMFace] = set()
        stack = list(seed_faces)
        while stack:
            f = stack.pop()
            if f in collected or f not in self.tri_faces:
                continue
            if any(v in corner_set for v in f.verts):
                collected.add(f)
                for e in f.edges:
                    for nf in e.link_faces:
                        if nf in self.tri_faces and nf not in collected:
                            stack.append(nf)
        return collected

    def _order_quad_verts(
        self, verts: List[bmesh.types.BMVert], shared_edge: bmesh.types.BMEdge
    ) -> Optional[Tuple[bmesh.types.BMVert, ...]]:
        """Order 4 verts consistently around quad center in planar winding order."""
        v0, v1 = shared_edge.verts
        tips = [v for v in verts if v not in shared_edge.verts]
        if len(tips) != 2:
            logger.debug(f"_order_quad_verts: expected 2 tips, got {len(tips)}")
            return None
        
        # Compute quad center and tangent plane
        center = (v0.co + v1.co + tips[0].co + tips[1].co) * 0.25
        normal = self.tangent_normal_at_co(center)
        
        # Project all 4 verts to tangent plane and sort by angle around center
        def project_to_plane(pt: Vector) -> Vector:
            v = pt - center
            n = normal.normalized()
            return v - n * v.dot(n)
        
        # Create a local 2D coordinate system on the plane
        proj_v0 = project_to_plane(v0.co)
        proj_v1 = project_to_plane(v1.co)
        proj_t0 = project_to_plane(tips[0].co)
        proj_t1 = project_to_plane(tips[1].co)
        
        # Use first edge direction as reference for angle calculation
        ref_dir = proj_v0.normalized() if proj_v0.length_squared > 1e-12 else Vector((1.0, 0.0, 0.0))
        
        # Calculate angles around center for all vertices
        def angle_from_center(proj: Vector) -> float:
            if proj.length_squared < 1e-12:
                return 0.0
            # Project to a 2D angle using atan2 with a perpendicular vector
            perp = normal.cross(ref_dir).normalized()
            x = proj.dot(ref_dir)
            y = proj.dot(perp)
            return math.atan2(y, x)
        
        angles = [
            (angle_from_center(proj_v0), v0),
            (angle_from_center(proj_v1), v1),
            (angle_from_center(proj_t0), tips[0]),
            (angle_from_center(proj_t1), tips[1]),
        ]
        
        # Sort by angle to get consistent winding order
        angles.sort(key=lambda x: x[0])
        ordered = tuple(v for _, v in angles)
        
        logger.debug(f"_order_quad_verts: ordered {[id(v) for v in ordered]}")
        return ordered

    def form_quad(
        self,
        verts: Tuple[bmesh.types.BMVert, bmesh.types.BMVert, bmesh.types.BMVert, bmesh.types.BMVert],
        tris_to_remove: Iterable[bmesh.types.BMFace],
    ) -> Optional[bmesh.types.BMFace]:
        """Delete interior tris and create a quad face with robust error handling."""
        tris = [f for f in tris_to_remove if f.is_valid]
        
        # Delete interior triangles
        if tris:
            try:
                bmesh.ops.delete(self.bm, geom=tris, context="FACES")
            except Exception as e:
                logger.warning(f"form_quad: failed to delete interior tris: {e}")
                return None
        
        self.refresh()
        
        # Attempt to create the quad face
        try:
            # Try direct face creation first
            face = self.bm.faces.new(list(verts))
            self.quad_faces.add(face)
            self.refresh()
            logger.debug(f"form_quad: successfully created quad with verts {[id(v) for v in verts]}")
            return face
        except ValueError as e:
            logger.warning(f"form_quad: direct face creation failed with {e}, retrying with edge healing")
            # If direct creation fails, try ensuring edges exist and recreate
            try:
                self.refresh()
                # Ensure all edges between consecutive vertices exist
                for i in range(4):
                    v_curr = verts[i]
                    v_next = verts[(i + 1) % 4]
                    if not self.edge_exists(v_curr, v_next):
                        try:
                            self.bm.edges.new((v_curr, v_next))
                        except Exception as edge_e:
                            logger.debug(f"form_quad: could not create edge {i}-{(i+1)%4}: {edge_e}")
                            return None
                self.refresh()
                # Try again with edges in place
                face = self.bm.faces.new(list(verts))
                self.quad_faces.add(face)
                self.refresh()
                logger.debug(f"form_quad: quad created after edge healing")
                return face
            except Exception as retry_e:
                logger.error(f"form_quad: quad creation failed after retry: {retry_e} with verts {[str(v.index) for v in verts]}")
                return None
        except Exception as e:
            logger.error(f"form_quad: unexpected error creating quad: {e}")
            return None

    def merge_pair_to_quad(
        self, edge: bmesh.types.BMEdge
    ) -> Optional[bmesh.types.BMFace]:
        """Merge two adjacent triangles sharing edge into one quad (simple case)."""
        if len(edge.link_faces) != 2:
            return None
        f0, f1 = edge.link_faces
        if f0 not in self.tri_faces or f1 not in self.tri_faces:
            return None
        vset = []
        for f in (f0, f1):
            for v in f.verts:
                if v not in vset:
                    vset.append(v)
        if len(vset) != 4:
            logger.debug(f"merge_pair_to_quad: expected 4 unique verts, got {len(vset)}")
            return None
        ordered = self._order_quad_verts(vset, edge)
        if ordered is None:
            return None
        return self.form_quad(ordered, (f0, f1))

    def valence(self, vert: bmesh.types.BMVert) -> int:
        return len(vert.link_edges)

    def is_boundary_vert(self, vert: bmesh.types.BMVert) -> bool:
        return any(e.is_boundary for e in vert.link_edges)

    def target_valence(self, vert: bmesh.types.BMVert) -> int:
        return 3 if self.is_boundary_vert(vert) else 4

    def is_regular(self, vert: bmesh.types.BMVert) -> bool:
        return self.valence(vert) == self.target_valence(vert)

    def boundary_edge_ratio(self) -> float:
        lengths = [self.edge_length(e) for e in self.get_boundary_edges()]
        if not lengths:
            return 1.0
        return max(lengths) / max(min(lengths), 1e-8)

    def build_bvh(self) -> BVHTree:
        self.bm.faces.ensure_lookup_table()
        return BVHTree.FromBMesh(self.bm)

    def project_to_surface(self, co: Vector, bvh: BVHTree) -> Vector:
        loc, _normal, _idx, _dist = bvh.find_nearest(co)
        return loc if loc is not None else co

    def count_remaining_tris(self) -> int:
        return len(self.tri_faces)

    def count_quads(self) -> int:
        return len(self.quad_faces)
