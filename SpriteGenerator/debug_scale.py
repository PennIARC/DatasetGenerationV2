import trimesh
import pyrender
import numpy as np
from PIL import Image

# --- CONFIG ---
STL_PATH = 'mine.stl'


def debug_render():
    print(f"--- DEBUGGING {STL_PATH} ---")

    # 1. Load and Inspect Mesh
    try:
        mesh = trimesh.load(STL_PATH)
    except Exception as e:
        print(f"ERROR: Could not load STL. {e}")
        return

    print(f"Original Extents: {mesh.extents}")
    print(f"Original Bounds: {mesh.bounds}")
    print(f"Original Center of Mass: {mesh.center_mass}")

    # 2. Normalize Mesh
    # We center the mesh and scale it so the longest side is 1.0 unit.
    mesh.vertices -= mesh.center_mass
    max_extent = np.max(mesh.extents)
    if max_extent == 0:
        print("ERROR: Mesh has 0 size.")
        return

    scale_factor = 1.0 / max_extent
    mesh.apply_scale(scale_factor)

    print(f"Normalized Scale Factor Applied: {scale_factor}")
    print(f"New Extents: {mesh.extents}")

    # 3. Create Scene
    scene = pyrender.Scene(bg_color=[0, 0, 0, 0], ambient_light=[0.3, 0.3, 0.3])

    # Add Mesh
    pyrender_mesh = pyrender.Mesh.from_trimesh(mesh)
    scene.add(pyrender_mesh)

    # 4. Setup Camera (Orthographic)
    camera = pyrender.OrthographicCamera(xmag=0.6, ymag=0.6)
    camera_pose = np.array([
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 2.0],  # 2 units back
        [0.0, 0.0, 0.0, 1.0],
    ])
    scene.add(camera, pose=camera_pose)

    # 5. Add Light
    light = pyrender.DirectionalLight(color=[1.0, 1.0, 1.0], intensity=5.0)
    scene.add(light, pose=camera_pose)

    # 6. Render
    print("Attempting render...")
    r = pyrender.OffscreenRenderer(viewport_width=512, viewport_height=512)

    # FIX: Explicitly request RGBA flags
    color, depth = r.render(scene, flags=pyrender.RenderFlags.RGBA)

    # 7. Check Output
    print(f"Output shape: {color.shape}")
    non_zero_pixels = np.count_nonzero(color[:, :, 3])
    print(f"Non-transparent pixels: {non_zero_pixels}")

    if non_zero_pixels == 0:
        print("FAILURE: Image is empty.")
    else:
        print("SUCCESS: Image content detected.")
        img = Image.fromarray(color)
        img.save("debug_output.png")
        print("Saved 'debug_output.png'. Check this file!")


if __name__ == "__main__":
    debug_render()