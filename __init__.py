bl_info = {
    "name": "Q-Morph Quad Meshing",
    "author": "Q-Morph Addon",
    "version": (1, 0, 1),
    "blender": (5, 1, 0),
    "location": "View3D > Sidebar > Q-Morph Quads",
    "description": "Convert triangle meshes to optimized quad meshes using Q-Morph",
    "category": "Mesh",
}

import bpy
import logging
import sys

# Configure logging for debugging
logger = logging.getLogger("q_morph_quads")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("[Q-Morph] %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

from .operators.convert import MESH_OT_qmorph_convert_to_quads, menu_func
from .ui.panel import QMorphProperties, VIEW3D_PT_qmorph_quads

classes = (
    QMorphProperties,
    VIEW3D_PT_qmorph_quads,
    MESH_OT_qmorph_convert_to_quads,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.qmorph_props = bpy.props.PointerProperty(type=QMorphProperties)
    bpy.types.VIEW3D_MT_edit_mesh_clean.append(menu_func)
    logger.info(f"Q-Morph Quad Meshing v{bl_info['version']} registered")


def unregister():
    bpy.types.VIEW3D_MT_edit_mesh_clean.remove(menu_func)
    del bpy.types.Scene.qmorph_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    logger.info("Q-Morph Quad Meshing unregistered")


if __name__ == "__main__":
    register()
