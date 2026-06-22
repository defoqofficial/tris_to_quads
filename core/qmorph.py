"""Main Q-Morph advancing-front engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Set, Tuple

import bmesh

from .edge_recovery import recover_edge
from .front import FrontManager
from .mesh_graph import MeshGraph
from .seams import (
    needs_seam,
    needs_transition_seam,
    perform_seam,
    perform_transition_seam,
)
from .side_edge import DEFAULT_SIDE_EPS, side_vertices_for_front
from .smoothing import smooth_local_around_quad


@dataclass
class QMorphSettings:
    angle_threshold: float = 2.356194490192345  # 3*pi/4
    side_edge_eps: float = DEFAULT_SIDE_EPS
    enable_seams: bool = True
    preserve_boundary: bool = True
    batch_size: int = 50


@dataclass
class QMorphProgress:
    front_remaining: int = 0
    quads_formed: int = 0
    tris_remaining: int = 0
    steps: int = 0
    done: bool = False
    message: str = ""


@dataclass
class QMorphResult:
    success: bool
    quads_formed: int = 0
    tris_remaining: int = 0
    steps: int = 0
    message: str = ""


class QMorphEngine:
    """Advancing-front Q-Morph quad conversion."""

    def __init__(self, graph: MeshGraph, settings: Optional[QMorphSettings] = None):
        self.graph = graph
        self.settings = settings or QMorphSettings()
        self.front = FrontManager(graph, self.settings.angle_threshold)
        self.progress = QMorphProgress()
        self._cancelled = False
        self._initialized = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self, max_steps: Optional[int] = None) -> QMorphResult:
        self.graph.refresh()
        self.front.initialize()
        self._initialized = True
        steps = 0
        max_steps = max_steps or len(self.graph.tri_faces) * 4

        while not self._cancelled and steps < max_steps:
            edge = self.front.pop_next()
            if edge is None:
                break

            if not self._process_front_edge(edge):
                # Fallback: try simple pair merge on this edge if two tris.
                self._try_simple_merge(edge)

            steps += 1
            self.progress.steps = steps
            self.progress.quads_formed = self.graph.count_quads()
            self.progress.tris_remaining = self.graph.count_remaining_tris()
            self.progress.front_remaining = len(self.graph.get_front_edges())
            self.front.rebuild()

        # Pair remaining adjacent triangle pairs greedily by front order.
        self._merge_remaining_pairs()

        self.progress.done = True
        tris_left = self.graph.count_remaining_tris()
        return QMorphResult(
            success=tris_left == 0,
            quads_formed=self.graph.count_quads(),
            tris_remaining=tris_left,
            steps=steps,
            message=self._build_message(tris_left),
        )

    def run_batch(self, batch_size: Optional[int] = None) -> bool:
        """Process one batch; return False when complete."""
        batch_size = batch_size or self.settings.batch_size
        if self.progress.done:
            return False
        if not self._initialized:
            self.graph.refresh()
            self.front.initialize()
            self._initialized = True

        for _ in range(batch_size):
            if self._cancelled:
                self.progress.done = True
                return False
            edge = self.front.pop_next()
            if edge is None:
                self._merge_remaining_pairs()
                self.progress.done = True
                self.progress.tris_remaining = self.graph.count_remaining_tris()
                return False
            if not self._process_front_edge(edge):
                self._try_simple_merge(edge)
            self.progress.steps += 1
            self.front.rebuild()

        self.progress.quads_formed = self.graph.count_quads()
        self.progress.tris_remaining = self.graph.count_remaining_tris()
        self.progress.front_remaining = len(self.graph.get_front_edges())
        return True

    def _build_message(self, tris_left: int) -> str:
        if tris_left == 0:
            return "Conversion complete."
        if tris_left == 1:
            return "Complete with 1 remaining triangle (odd boundary loop)."
        return f"Complete with {tris_left} remaining triangles."

    def _front_edge_set(self) -> Set[bmesh.types.BMEdge]:
        return set(self.graph.get_front_edges())

    def _process_front_edge(self, front_edge: bmesh.types.BMEdge) -> bool:
        v0, v1 = front_edge.verts
        front_edges = self._front_edge_set()

        if self.settings.enable_seams:
            for v in (v0, v1):
                if needs_seam(self.graph, v, self.settings.side_edge_eps):
                    if perform_seam(self.graph, v, front_edges):
                        return False
                if needs_transition_seam(self.graph, v):
                    perform_transition_seam(self.graph, v)
                    return False

        # Simple 2-triangle merge when front edge borders two tris only.
        if self._try_simple_merge(front_edge):
            return True

        top_v0, top_v1 = side_vertices_for_front(
            self.graph, front_edge, front_edges, self.settings.side_edge_eps
        )
        if top_v0 is None or top_v1 is None:
            return False

        if not recover_edge(self.graph, top_v0, top_v1, front_edges):
            return False

        corners = (v0, top_v0, v1, top_v1)
        tris = self.graph.collect_tris_in_quad_region(corners, front_edge)
        quad = self.graph.form_quad(corners, tris)
        if quad is None:
            return False

        smooth_local_around_quad(
            self.graph,
            corners,
            {v0, v1},
            preserve_boundary=self.settings.preserve_boundary,
        )
        return True

    def _try_simple_merge(self, edge: bmesh.types.BMEdge) -> bool:
        if len(edge.link_faces) != 2:
            return False
        f0, f1 = edge.link_faces
        if f0 not in self.graph.tri_faces or f1 not in self.graph.tri_faces:
            return False
        quad = self.graph.merge_pair_to_quad(edge)
        return quad is not None

    def _merge_remaining_pairs(self) -> None:
        """Greedy merge of remaining adjacent triangle pairs."""
        changed = True
        while changed:
            changed = False
            self.graph.refresh()
            for edge in list(self.graph.bm.edges):
                if len(edge.link_faces) != 2:
                    continue
                if self._try_simple_merge(edge):
                    changed = True
