import os
import trimesh
import pyrender
import numpy as np
from PIL import Image
from scipy.spatial.transform import Rotation as R

# --- CONFIG ---
STL_PATH = 'mine.stl'
OUTPUT_DIR = '../DatasetGenerator/assets/mines'
NUM_ANGLES = 50
IMAGE_SIZE = (512, 512)

os.makedirs(OUTPUT_DIR, exist_ok=True)


def generate_sprites():
    # 1. Load and Normalize Mesh
    mesh = trimesh.load(STL_PATH)
    mesh.vertices -= mesh.center_mass
    scale_factor = 1.0 / np.max(mesh.extents)
    mesh.apply_scale(scale_factor)

    # 2. Setup Scene
    scene = pyrender.Scene(bg_color=[0, 0, 0, 0])

    # Camera
    camera = pyrender.OrthographicCamera(xmag=0.6, ymag=0.6)
    camera_pose = np.array([
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 2.0],
        [0.0, 0.0, 0.0, 1.0],
    ])
    cam_node = scene.add(camera, pose=camera_pose)

    # Lighting (Attached to camera, moves with it effectively)
    light = pyrender.DirectionalLight(color=[1.0, 1.0, 1.0], intensity=3.0)
    scene.add(light, pose=camera_pose)

    renderer = pyrender.OffscreenRenderer(viewport_width=IMAGE_SIZE[0], viewport_height=IMAGE_SIZE[1])

    print(f"Generating {NUM_ANGLES} sprites into {OUTPUT_DIR}...")

    for i in range(NUM_ANGLES):
        # 3. Randomize Material
        base_color = np.array([0.1490, 0.3843, 0.2745])
        base_color += np.random.uniform(-0.1, 0.1) * 3
        for _ in range(3):
            base_color[_] += np.random.uniform(-0.05, 0.05)
        base_color = np.clip(base_color, 0, 1)
        base_color = np.append(base_color, 1.0)

        material = pyrender.MetallicRoughnessMaterial(
            baseColorFactor=base_color,
            metallicFactor=0.1,
            roughnessFactor=0.7
        )

        # 4. Random Rotation
        rot_angles = [
            np.random.uniform(-20, 20),  # X (Pitch)
            np.random.uniform(-20, 20),  # Y (Roll)
            np.random.uniform(0, 360)  # Z (Yaw - spinning on ground)
        ]
        rotation_matrix = R.from_euler('xyz', rot_angles, degrees=True).as_matrix()

        pose = np.eye(4)
        pose[:3, :3] = rotation_matrix

        # Create temp mesh with material
        temp_mesh = pyrender.Mesh.from_trimesh(mesh, material=material)
        mesh_node = scene.add(temp_mesh, pose=pose)

        # 5. Render
        color, _ = renderer.render(scene, flags=pyrender.RenderFlags.RGBA)

        # 6. Save if valid
        if np.any(color[:, :, 3] > 0):
            im = Image.fromarray(color)
            bbox = im.getbbox()
            if bbox:
                im = im.crop(bbox)
                im.save(os.path.join(OUTPUT_DIR, f"mine_{i:04d}.png"))
        else:
            print(f"Warning: Frame {i} was empty.")

        scene.remove_node(mesh_node)

    print("Done.")


if __name__ == "__main__":
    generate_sprites()