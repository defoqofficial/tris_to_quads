# Q-Morph Quad Meshing Blender Addon

Convert triangle meshes to optimized pure-quad meshes using the **Q-Morph** advancing-front algorithm (Owen et al.) with **STAR**-inspired post-processing.

## Requirements

- Blender 5.1 or newer
- No external Python dependencies

## Installation

1. Copy or symlink the `q_morph_quads` folder into your Blender extensions directory:
   - Windows: `%APPDATA%\Blender Foundation\Blender\5.1\extensions\user_default\`
2. Open Blender → **Edit → Preferences → Get Extensions**
3. Enable **Q-Morph Quad Meshing**

Alternatively, zip the folder and use **Install from Disk**.

## Usage

1. Select a mesh object and enter **Edit Mode**
2. Select triangular faces to convert (or leave unselected to convert the whole mesh)
3. Open the **Q-Morph Quads** sidebar tab (press `N` in the 3D Viewport)
4. Adjust settings if needed, then click **Convert Tris to Quads**

The operator also appears under **Mesh → Clean Up → Q-Morph Tris to Quads**.

Press **ESC** during conversion to cancel.

## Testing

Syntax validation (no Blender required):

```powershell
py tests\check_syntax.py
```

Inside Blender, run the mesh test suite from the Scripting workspace:

```python
import sys
sys.path.insert(0, r"C:\Users\grask\Projects")
import q_morph_quads.tests.blender_test_meshes as t
t.run_all()
```

Tests cover planar grid, open boundary, and cylinder meshes.

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| Angle Threshold | 135° | Front edge state classification |
| Side Edge Tolerance | 30° | Max angle for reusing existing edges as sides |
| Enable Seams | On | Seam and transition-seam operations |
| Cleanup Passes | 3 | STAR valence-reduction iterations |
| Smooth Iterations | 5 | Final tangent-space smoothing |
| Preserve Boundary | On | Lock boundary vertices while smoothing |

## Algorithm Overview

1. **Q-Morph advancing front** — grows quad rows inward from the mesh boundary using side-edge definition, 3D edge recovery, and local smoothing
2. **STAR cleanup** — edge rotate, doublet removal, irregular vertex reduction
3. **Tangent-space smoothing** — constrained Laplacian smoothing on the surface

## Known Limitations

1. **Odd boundary loops** — may leave one interior triangle (Q-Morph paper, Sec 3)
2. **Unstructured output** — produces valence-semi-regular meshes, not semi-regular patch layouts
3. **Input quality** — uniform, well-shaped triangle meshes yield the best loop alignment
4. **No remeshing** — connectivity conversion only; vertex count stays roughly the same

## References

- Owen et al., *Advancing Front Quadrilateral Meshing Using Triangle Transformations* (Q-Morph)
- Bommes et al., *State of the Art in Quad Meshing* (STAR)

## License

GPL-3.0-or-later
