"""
Blender test script for Q-Morph addon.

Run inside Blender (Scripting workspace or Text Editor):
    import sys
    sys.path.insert(0, r"C:\\Users\\grask\\Projects")
    import q_morph_quads.tests.blender_test_meshes as t
    t.run_all()
"""

from __future__ import annotations


def _make_grid_tri_mesh(bm, size=4):
    import bmesh

    verts = []
    for y in range(size):
        for x in range(size):
            verts.append(bm.verts.new((x, y, 0)))

    bm.verts.ensure_lookup_table()

    def idx(x, y):
        return verts[y * size + x]

    for y in range(size - 1):
        for x in range(size - 1):
            v00 = idx(x, y)
            v10 = idx(x + 1, y)
            v01 = idx(x, y + 1)
            v11 = idx(x + 1, y + 1)
            bm.faces.new((v00, v10, v11))
            bm.faces.new((v00, v11, v01))


def _run_on_bmesh(name, build_fn):
    import bmesh

    from q_morph_quads.cleanup.edge_ops import remove_all_doublets
    from q_morph_quads.cleanup.valence import cleanup_valence, irregular_vertices
    from q_morph_quads.core.mesh_graph import MeshGraph
    from q_morph_quads.core.qmorph import QMorphEngine, QMorphSettings
    from q_morph_quads.core.smoothing import smooth_global

    bm = bmesh.new()
    build_fn(bm)
    bm.faces.ensure_lookup_table()
    tri_count = sum(1 for f in bm.faces if len(f.verts) == 3)
    print(f"\n=== {name} ===")
    print(f"  Input triangles: {tri_count}")

    graph = MeshGraph(bm)
    engine = QMorphEngine(graph, QMorphSettings())
    result = engine.run()
    cleanup_valence(graph, 3)
    remove_all_doublets(graph)
    smooth_global(graph, 2, True)

    quads = graph.count_quads()
    tris = graph.count_remaining_tris()
    irregular = len(irregular_vertices(graph))
    print(f"  Quads formed: {quads}")
    print(f"  Tris remaining: {tris}")
    print(f"  Irregular verts: {irregular}")
    print(f"  Message: {result.message}")
    bm.free()
    return tris == 0


def test_planar_grid():
    _run_on_bmesh("Planar grid", lambda bm: _make_grid_tri_mesh(bm, 5))


def test_open_boundary():
    """Grid with one row of faces removed (open boundary)."""

    def build(bm):
        _make_grid_tri_mesh(bm, 4)
        to_remove = [f for f in bm.faces if all(v.co.y > 2.5 for v in f.verts)]
        if to_remove:
            bmesh.ops.delete(bm, geom=to_remove, context="FACES")

    import bmesh

    _run_on_bmesh("Open boundary", build)


def test_cylinder():
    import bmesh
    import bpy

    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=1, depth=2)
    obj = bpy.context.active_object
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bpy.data.objects.remove(obj, do_unlink=True)

    from q_morph_quads.core.mesh_graph import MeshGraph
    from q_morph_quads.core.qmorph import QMorphEngine, QMorphSettings

    graph = MeshGraph(bm)
    engine = QMorphEngine(graph, QMorphSettings())
    result = engine.run()
    print(f"\n=== Cylinder ===")
    print(f"  Quads: {graph.count_quads()}, Tris left: {graph.count_remaining_tris()}")
    print(f"  {result.message}")
    bm.free()


def run_all():
    test_planar_grid()
    test_open_boundary()
    try:
        test_cylinder()
    except Exception as exc:
        print(f"Cylinder test skipped or failed: {exc}")
    print("\nDone.")


if __name__ == "__main__":
    run_all()
