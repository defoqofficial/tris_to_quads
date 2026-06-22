"""Front edge classification and priority queue management (Q-Morph Sec 3.1–3.2)."""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import bmesh

from .mesh_graph import MeshGraph

# Default: 135 degrees — node bit set when front angle is below this.
DEFAULT_ANGLE_THRESHOLD = 3.0 * math.pi / 4.0

# State priority: 11 > 01/10 > 00
STATE_PRIORITY = {
    (1, 1): 0,
    (0, 1): 1,
    (1, 0): 1,
    (0, 0): 2,
}


@dataclass(order=True)
class FrontEntry:
    """Priority queue entry for front edges."""

    sort_key: Tuple[int, int, float, int] = field(compare=True)
    edge: bmesh.types.BMEdge = field(compare=False)
    state: Tuple[int, int] = field(compare=False)
    level: int = field(compare=False)


class FrontManager:
    """Manages front edge classification, levels, and selection priority."""

    def __init__(
        self,
        graph: MeshGraph,
        angle_threshold: float = DEFAULT_ANGLE_THRESHOLD,
    ):
        self.graph = graph
        self.angle_threshold = angle_threshold
        self.levels: Dict[bmesh.types.BMEdge, int] = {}
        self._heap: List[FrontEntry] = []
        self._edge_set: Set[bmesh.types.BMEdge] = set()

    def clear(self) -> None:
        self.levels.clear()
        self._heap.clear()
        self._edge_set.clear()

    def initialize(self) -> None:
        """Build initial front from boundary edges (level 0)."""
        self.clear()
        for edge in self.graph.get_boundary_edges():
            if any(f in self.graph.tri_faces for f in edge.link_faces):
                self.levels[edge] = 0
                self._push_edge(edge)

    def rebuild(self) -> None:
        """Recompute front from current mesh state."""
        old_levels = dict(self.levels)
        self.clear()
        for edge in self.graph.get_front_edges():
            level = old_levels.get(edge, 0)
            # Bump level when edge newly appears after quad formation.
            if edge not in old_levels:
                neighbors = self._neighbor_levels(edge, old_levels)
                level = (max(neighbors) + 1) if neighbors else 0
            self.levels[edge] = level
            self._push_edge(edge)

    def _neighbor_levels(
        self, edge: bmesh.types.BMEdge, old_levels: Dict[bmesh.types.BMEdge, int]
    ) -> List[int]:
        levels = []
        for v in edge.verts:
            for fe in self.graph.adjacent_front_edges(v):
                if fe in old_levels:
                    levels.append(old_levels[fe])
        return levels

    def classify_state(self, edge: bmesh.types.BMEdge) -> Tuple[int, int]:
        """Return (left_bit, right_bit) state for front edge."""
        v0, v1 = edge.verts
        return (
            self._node_state_bit(v0, edge),
            self._node_state_bit(v1, edge),
        )

    def _node_state_bit(
        self, vert: bmesh.types.BMVert, edge: bmesh.types.BMEdge
    ) -> int:
        angle = self.graph.front_angle_at_vert(vert)
        return 1 if angle < self.angle_threshold else 0

    def _push_edge(self, edge: bmesh.types.BMEdge) -> None:
        if edge in self._edge_set:
            return
        state = self.classify_state(edge)
        level = self.levels.get(edge, 0)
        priority = STATE_PRIORITY[state]
        length = self.graph.edge_length(edge)
        entry = FrontEntry(
            sort_key=(priority, level, length, id(edge)),
            edge=edge,
            state=state,
            level=level,
        )
        heapq.heappush(self._heap, entry)
        self._edge_set.add(edge)

    def pop_next(self) -> Optional[bmesh.types.BMEdge]:
        """Pop highest-priority valid front edge."""
        while self._heap:
            entry = heapq.heappop(self._heap)
            edge = entry.edge
            if not edge.is_valid:
                continue
            if edge not in self._edge_set:
                continue
            if not self.graph.is_front_edge(edge):
                self._edge_set.discard(edge)
                continue
            self._edge_set.discard(edge)
            return edge
        return None

    def count(self) -> int:
        return len(self._edge_set) + len(self._heap)

    def remaining_estimate(self) -> int:
        return max(len(self._edge_set), len(self._heap))

    def front_loops(self) -> List[List[bmesh.types.BMEdge]]:
        """Return front edges grouped into continuous loops."""
        edges = list(self._edge_set)
        if not edges:
            edges = [e for e in self.graph.get_front_edges()]
        unused = set(edges)
        loops: List[List[bmesh.types.BMEdge]] = []

        while unused:
            start = next(iter(unused))
            loop = [start]
            unused.remove(start)
            cur = start
            while True:
                next_edge = None
                for v in cur.verts:
                    for e in self.graph.adjacent_front_edges(v):
                        if e in unused:
                            next_edge = e
                            break
                    if next_edge:
                        break
                if next_edge is None:
                    break
                loop.append(next_edge)
                unused.remove(next_edge)
                cur = next_edge
            loops.append(loop)
        return loops

    def loop_edge_count_if_connected(
        self,
        edge: bmesh.types.BMEdge,
        target: bmesh.types.BMVert,
    ) -> int:
        """Estimate loop size if edge were connected to target vert's front."""
        loops = self.front_loops()
        for loop in loops:
            edge_set = set(loop)
            if edge in edge_set:
                return len(loop)
        return 0
