bl_info = {
    "name": "Q-Morph Quad Meshing",
    "author": "Q-Morph Addon",
    "version": (1, 0, 0),
    "blender": (5, 1, 0),
    "location": "View3D > Sidebar > Q-Morph Quads",
    "description": "Convert triangle meshes to optimized quad meshes using Q-Morph",
    "category": "Mesh",
}

import bpy

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


def unregister():
    bpy.types.VIEW3D_MT_edit_mesh_clean.remove(menu_func)
    del bpy.types.Scene.qmorph_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
