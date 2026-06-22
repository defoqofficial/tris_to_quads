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
    success = tris == 0
    print(f"  Status: {'PASS' if success else 'FAIL'}")
    bm.free()
    return success


def test_planar_grid():
    """Test conversion of a simple planar triangular grid."""
    return _run_on_bmesh("Planar grid 5x5", lambda bm: _make_grid_tri_mesh(bm, 5))


def test_open_boundary():
    """Grid with one row of faces removed (open boundary)."""

    def build(bm):
        _make_grid_tri_mesh(bm, 4)
        to_remove = [f for f in bm.faces if all(v.co.y > 2.5 for v in f.verts)]
        if to_remove:
            import bmesh
            bmesh.ops.delete(bm, geom=to_remove, context="FACES")

    return _run_on_bmesh("Open boundary", build)


def test_two_tri_pair():
    """Test minimal two-triangle pair case (vertex ordering edge case)."""
    import bmesh
    
    def build(bm):
        # Create a simple two-triangle configuration
        v0 = bm.verts.new((0, 0, 0))
        v1 = bm.verts.new((1, 0, 0))
        v2 = bm.verts.new((0.5, 1, 0))
        v3 = bm.verts.new((0.5, -1, 0))
        
        bm.faces.new((v0, v1, v2))
        bm.faces.new((v0, v3, v1))
    
    return _run_on_bmesh("Two-triangle pair", build)


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

    bm.faces.ensure_lookup_table()
    tri_count = sum(1 for f in bm.faces if len(f.verts) == 3)
    print(f"\n=== Cylinder ===")
    print(f"  Input triangles: {tri_count}")
    
    graph = MeshGraph(bm)
    engine = QMorphEngine(graph, QMorphSettings())
    result = engine.run()
    quads = graph.count_quads()
    tris = graph.count_remaining_tris()
    print(f"  Quads: {quads}, Tris left: {tris}")
    print(f"  {result.message}")
    success = tris <= 1  # Cylinder may have 1 tri due to odd boundary
    print(f"  Status: {'PASS' if success else 'FAIL'}")
    bm.free()
    return success


def run_all():
    """Run all tests and report results."""
    results = {}
    
    results['planar_grid'] = test_planar_grid()
    results['open_boundary'] = test_open_boundary()
    results['two_tri_pair'] = test_two_tri_pair()
    
    try:
        results['cylinder'] = test_cylinder()
    except Exception as exc:
        print(f"\nCylinder test failed: {exc}")
        results['cylinder'] = False
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {test_name}: {status}")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    print(f"\nTotal: {passed}/{total} tests passed")
    print("=" * 50)
    
    return all(results.values())


if __name__ == "__main__":
    success = run_all()
    import sys
    sys.exit(0 if success else 1)
