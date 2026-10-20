import pygame
import moderngl
import os
import random
import time
import array
from objects import Mine, EnvironmentDebris
import controlPanel as cp

# --- SETUP DIRECTORIES ---
os.makedirs(os.path.join(cp.OUTPUT_PATH, cp.IMAGES_DIR), exist_ok=True)
os.makedirs(os.path.join(cp.OUTPUT_PATH, cp.LABELS_DIR), exist_ok=True)

# --- PYGAME & OPENGL SETUP ---
pygame.init()

# Attributes for ModernGL 3.3 Core on MacOS
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_FORWARD_COMPATIBLE_FLAG, 1)
pygame.display.gl_set_attribute(pygame.GL_DOUBLEBUFFER, 1)

# Hidden window for context creation
pygame.display.set_mode((cp.SCREEN_WIDTH, cp.SCREEN_HEIGHT), pygame.OPENGL | pygame.DOUBLEBUF | pygame.HIDDEN)

# Pygame Surface (The "Canvas")
game_surface = pygame.Surface((cp.SCREEN_WIDTH, cp.SCREEN_HEIGHT)).convert()

# ModernGL Context
ctx = moderngl.create_context()
ctx.enable(moderngl.BLEND)

# Texture to hold the Pygame surface
# We use 3 components (RGB)
texture = ctx.texture((cp.SCREEN_WIDTH, cp.SCREEN_HEIGHT), 3)
texture.filter = (moderngl.LINEAR, moderngl.LINEAR)

# Screen Quad
quad_buffer = ctx.buffer(data=array.array('f', [
    -1.0, 1.0, 0.0, 0.0,
    -1.0, -1.0, 0.0, 1.0,
    1.0, 1.0, 1.0, 0.0,
    1.0, -1.0, 1.0, 1.0,
]))


def load_shader():
    try:
        with open('shaders/basic.vert') as f:
            vert = f.read()
        with open('shaders/post.frag') as f:
            frag = f.read()
        return ctx.program(vertex_shader=vert, fragment_shader=frag)
    except Exception as e:
        print(f"Shader Error: {e}")
        exit()


prog = load_shader()
vao = ctx.vertex_array(prog, [(quad_buffer, '2f 2f', 'in_vert', 'in_text')])

# Backgrounds
bg_path = 'assets/backgrounds'
os.makedirs(bg_path, exist_ok=True)
bg_files = [os.path.join(bg_path, f) for f in os.listdir(bg_path) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]


def generate_one_image(index):
    # 1. Draw Background
    if bg_files:
        bg_choice = random.choice(bg_files)
        try:
            bg_img = pygame.image.load(bg_choice).convert()

            # --- FIX: Robust Scaling for any Aspect Ratio ---
            img_w, img_h = bg_img.get_size()

            # Calculate minimal scale needed to cover the screen
            scale_w = cp.SCREEN_WIDTH / img_w
            scale_h = cp.SCREEN_HEIGHT / img_h
            min_scale = max(scale_w, scale_h)

            # Add random zoom (1.0 to 1.5x)
            final_scale = min_scale * random.uniform(1.0, 1.5)

            new_w = int(img_w * final_scale)
            new_h = int(img_h * final_scale)

            bg_img = pygame.transform.scale(bg_img, (new_w, new_h))

            # Center the crop or random offset? Random is better for data variety
            max_offset_x = new_w - cp.SCREEN_WIDTH
            max_offset_y = new_h - cp.SCREEN_HEIGHT

            off_x = random.randint(0, max(0, max_offset_x))
            off_y = random.randint(0, max(0, max_offset_y))

            game_surface.blit(bg_img, (-off_x, -off_y))
        except Exception as e:
            print(f"Background Load Error: {e}")
            game_surface.fill((50, 70, 50))
    else:
        game_surface.fill((34, 139, 34))  # Forest Green default

    # 2. Draw Debris (Undergrowth)
    debris = EnvironmentDebris(cp.SCREEN_WIDTH, cp.SCREEN_HEIGHT)
    debris.draw(game_surface)

    # 3. Draw Mines & Get Labels
    labels = []
    mines = []  # Keep track for collision detection

    # 10% chance to spawn 0 mines
    if random.random() < 0.10:
        num_mines = 0
    else:
        num_mines = random.randint(cp.MIN_MINES, cp.MAX_MINES)

    try:
        for _ in range(num_mines):
            m = Mine('assets/mines', (cp.MINE_SCALE_MIN, cp.MINE_SCALE_MAX))

            # Collision/Overlap Check
            placed = False
            attempts = 0
            while not placed and attempts < 50:
                m.set_position(cp.SCREEN_WIDTH, cp.SCREEN_HEIGHT)

                # Check collision with existing mines
                collision = False
                for existing_mine in mines:
                    if m.rect.colliderect(existing_mine.rect.inflate(10, 10)):
                        collision = True
                        break

                if not collision:
                    placed = True
                attempts += 1

            if placed:
                m.draw(game_surface)
                lbl = m.get_yolo_bbox(cp.SCREEN_WIDTH, cp.SCREEN_HEIGHT)
                if lbl:
                    labels.append(lbl)
                    mines.append(m)

    except FileNotFoundError:
        print("Error: No mine sprites found. Run generate_sprites.py first!")
        return

    # 4. Draw Overgrowth (Occlusion)
    debris_over = EnvironmentDebris(cp.SCREEN_WIDTH, cp.SCREEN_HEIGHT)
    debris_over.draw(game_surface)

    # 5. Post-Processing (ModernGL)
    # Upload Pygame surface data to GPU texture
    # FIX: alignment=1 to prevent corruption/striding issues
    texture.write(pygame.image.tobytes(game_surface, 'RGB'), alignment=1)
    texture.use(0)

    # Update Shader Uniforms
    if 'time' in prog: prog['time'].value = random.random() * 1000.0
    if 'noise_strength' in prog: prog['noise_strength'].value = random.uniform(0.05, 0.12)

    # Render to Framebuffer
    fbo = ctx.simple_framebuffer((cp.SCREEN_WIDTH, cp.SCREEN_HEIGHT))
    fbo.use()
    ctx.clear()
    vao.render(mode=moderngl.TRIANGLE_STRIP)

    # 6. Read back and Save
    # FIX: alignment=1 here as well
    data = fbo.read(components=3, alignment=1)
    img = pygame.image.frombytes(data, (cp.SCREEN_WIDTH, cp.SCREEN_HEIGHT), 'RGB')

    # Vertical Flip (OpenGL -> Pygame)
    img = pygame.transform.flip(img, False, True)

    img_name = f"train_{index:05d}.jpg"
    lbl_name = f"train_{index:05d}.txt"

    pygame.image.save(img, os.path.join(cp.OUTPUT_PATH, cp.IMAGES_DIR, img_name))

    with open(os.path.join(cp.OUTPUT_PATH, cp.LABELS_DIR, lbl_name), "w") as f:
        for l in labels:
            # Class X Y W H
            f.write(f"{int(l[0])} {l[1]:.6f} {l[2]:.6f} {l[3]:.6f} {l[4]:.6f}\n")


if __name__ == "__main__":
    start_time = time.time()
    print(f"Starting Generation of {cp.NUM_IMAGES_TO_GENERATE} images...")

    for i in range(cp.NUM_IMAGES_TO_GENERATE):
        generate_one_image(i)
        if i % 10 == 0:
            print(f"Generated {i} / {cp.NUM_IMAGES_TO_GENERATE}")

    print(f"Done in {time.time() - start_time:.2f}s")