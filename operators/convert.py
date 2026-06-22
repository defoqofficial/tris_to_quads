"""Modal operator for Q-Morph quad conversion."""

from __future__ import annotations

import logging

import bmesh
import bpy
from bpy.types import Operator

from ..cleanup.edge_ops import remove_all_doublets
from ..cleanup.valence import cleanup_valence
from ..core.mesh_graph import MeshGraph
from ..core.qmorph import QMorphEngine, QMorphSettings
from ..core.smoothing import smooth_global

logger = logging.getLogger(__name__)


def _prepare_bmesh(obj, selected_only: bool) -> tuple[bmesh.types.BMesh, str | None]:
    """Prepare bmesh for conversion with robust selection handling."""
    me = obj.data
    bm = bmesh.from_edit_mesh(me)

    # Determine working set of faces
    if selected_only:
        faces = [f for f in bm.faces if f.select]
        if not faces:
            logger.info("No faces selected; converting entire mesh")
            selected_only = False

    if not selected_only:
        faces = list(bm.faces)
        # Mark all faces as selected for triangulation
        for f in bm.faces:
            f.select = True

    # Triangulate all non-triangle faces in working set (ngons and quads).
    non_tris = [f for f in faces if len(f.verts) != 3]
    if non_tris:
        logger.info(f"Triangulating {len(non_tris)} non-triangle faces")
        try:
            bmesh.ops.triangulate(bm, faces=non_tris)
        except Exception as e:
            logger.error(f"Triangulation failed: {e}")
            return bm, f"Triangulation failed: {e}"

    # Ensure lookup table is up-to-date after triangulation
    bm.faces.ensure_lookup_table()
    
    # Re-evaluate working set after triangulation
    # If we're converting the whole mesh, get all current triangles
    # Otherwise, get triangles from the originally-selected faces (they may have been subdivided)
    if not selected_only:
        tris = [f for f in bm.faces if len(f.verts) == 3]
    else:
        # For selected-only mode, only count tris from originally selected faces or their children
        # This is a conservative approach: count all triangles that exist and are marked selected
        tris = [f for f in bm.faces if f.select and len(f.verts) == 3]
    
    if not tris:
        msg = "No triangles to convert."
        logger.warning(msg)
        return bm, msg

    logger.info(f"Prepared mesh with {len(tris)} triangles for conversion")
    return bm, None


class MESH_OT_qmorph_convert_to_quads(Operator):
    bl_idname = "mesh.qmorph_convert_to_quads"
    bl_label = "Q-Morph Tris to Quads"
    bl_description = "Convert triangle mesh to optimized quads using Q-Morph"
    bl_options = {"REGISTER", "UNDO"}

    _timer = None
    _engine = None
    _graph = None
    _bm = None
    _obj = None

    @classmethod
    def poll(cls, context):
        obj = context.edit_object
        return obj is not None and obj.type == "MESH" and obj.mode == "EDIT"

    def invoke(self, context, event):
        return self.execute(context)

    def execute(self, context):
        props = context.scene.qmorph_props
        self._obj = context.edit_object

        self._bm, err = _prepare_bmesh(self._obj, selected_only=True)
        if err:
            self.report({"WARNING"}, err)
            logger.warning(f"Preparation failed: {err}")
            return {"CANCELLED"}

        self._graph = MeshGraph(self._bm)
        settings = QMorphSettings(
            angle_threshold=props.angle_threshold,
            side_edge_eps=props.side_edge_eps,
            enable_seams=props.enable_seams,
            preserve_boundary=props.preserve_boundary,
        )
        self._engine = QMorphEngine(self._graph, settings)

        wm = context.window_manager
        if self._timer:
            wm.event_timer_remove(self._timer)
        self._timer = wm.event_timer_add(0.05, window=context.window)
        wm.modal_handler_add(self)
        context.workspace.status_text_set("Q-Morph running… [ESC] cancel")
        logger.info("Q-Morph conversion started")
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type in {"RIGHTMOUSE", "ESC"}:
            self._engine.cancel()
            self._finish(context, cancelled=True)
            return {"CANCELLED"}

        if event.type == "TIMER":
            still_running = self._engine.run_batch()
            p = self._engine.progress
            context.workspace.status_text_set(
                f"Q-Morph | Front: {p.front_remaining} | "
                f"Quads: {p.quads_formed} | Tris left: {p.tris_remaining} | [ESC] cancel"
            )
            if not still_running:
                self._finish(context, cancelled=False)
                return {"FINISHED"}

        return {"PASS_THROUGH"}

    def _finish(self, context, cancelled: bool):
        wm = context.window_manager
        if self._timer:
            wm.event_timer_remove(self._timer)
            self._timer = None
        context.workspace.status_text_set(None)

        if cancelled:
            self.report({"INFO"}, "Q-Morph cancelled.")
            logger.info("Q-Morph cancelled by user")
            return

        props = context.scene.qmorph_props

        # STAR cleanup
        if props.cleanup_passes > 0:
            logger.info(f"Running {props.cleanup_passes} cleanup passes")
            cleanup_valence(self._graph, props.cleanup_passes)
            remove_all_doublets(self._graph)

        # Final smoothing
        if props.smooth_iterations > 0:
            logger.info(f"Running {props.smooth_iterations} smoothing iterations")
            smooth_global(
                self._graph,
                props.smooth_iterations,
                props.preserve_boundary,
            )

        bmesh.update_edit_mesh(self._obj.data)
        tris_left = self._graph.count_remaining_tris()
        quads = self._graph.count_quads()
        msg = f"Q-Morph complete: {quads} quads"
        if tris_left:
            msg += f", {tris_left} triangle(s) remaining"
        self.report({"INFO"}, msg)
        logger.info(msg)


def menu_func(self, context):
    self.layout.operator(MESH_OT_qmorph_convert_to_quads.bl_idname)
