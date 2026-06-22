"""Scene properties and sidebar panel."""

import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty, PointerProperty
from bpy.types import Panel, PropertyGroup


class QMorphProperties(PropertyGroup):
    angle_threshold: FloatProperty(
        name="Angle Threshold",
        description="Front classification angle (radians); default 135°",
        default=2.356194490192345,
        min=0.785398,
        max=3.141593,
        subtype="ANGLE",
    )
    side_edge_eps: FloatProperty(
        name="Side Edge Tolerance",
        description="Maximum angle for selecting existing side edges",
        default=0.523599,
        min=0.1,
        max=1.570796,
        subtype="ANGLE",
    )
    enable_seams: BoolProperty(
        name="Enable Seams",
        description="Apply seam and transition-seam operations",
        default=True,
    )
    cleanup_passes: IntProperty(
        name="Cleanup Passes",
        description="STAR valence reduction iterations",
        default=3,
        min=0,
        max=20,
    )
    smooth_iterations: IntProperty(
        name="Smooth Iterations",
        description="Final tangent-space smoothing passes",
        default=5,
        min=0,
        max=50,
    )
    preserve_boundary: BoolProperty(
        name="Preserve Boundary",
        description="Lock boundary vertices during smoothing",
        default=True,
    )


class VIEW3D_PT_qmorph_quads(Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Q-Morph Quads"
    bl_label = "Q-Morph Quad Meshing"

    def draw(self, context):
        layout = self.layout
        props = context.scene.qmorph_props

        box = layout.box()
        box.label(text="Q-Morph Settings", icon="MODIFIER")
        box.prop(props, "angle_threshold")
        box.prop(props, "side_edge_eps")
        box.prop(props, "enable_seams")

        box = layout.box()
        box.label(text="Post-Process (STAR)", icon="TOOL_SETTINGS")
        box.prop(props, "cleanup_passes")
        box.prop(props, "smooth_iterations")
        box.prop(props, "preserve_boundary")

        layout.separator()
        layout.operator("mesh.qmorph_convert_to_quads", text="Convert Tris to Quads", icon="PLAY")
