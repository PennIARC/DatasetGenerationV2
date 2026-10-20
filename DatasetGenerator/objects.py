import pygame
import random
import os
import cv2
import numpy as np
from calcs import random_col_range, normalize_yolo
import controlPanel as cp


class Mine:
    def __init__(self, sprite_folder, scale_range):
        sprites = [f for f in os.listdir(sprite_folder) if f.endswith('.png')]
        if not sprites:
            raise FileNotFoundError(f"No sprites found in {sprite_folder}")

        choice = random.choice(sprites)
        self.original_image = pygame.image.load(os.path.join(sprite_folder, choice)).convert_alpha()

        # Scale
        scale = random.uniform(scale_range[0], scale_range[1])
        w = int(self.original_image.get_width() * scale)
        h = int(self.original_image.get_height() * scale)
        self.image = pygame.transform.scale(self.original_image, (w, h))

        # Rotation
        self.angle = random.uniform(0, 360)
        self.image = pygame.transform.rotate(self.image, self.angle)

        self.mask = pygame.mask.from_surface(self.image)
        self.rect = self.image.get_rect()
        self._add_surface_dirt()

    def _add_surface_dirt(self):
        w, h = self.image.get_size()
        num_specs = random.randint(5, 20)
        for _ in range(num_specs):
            dx = random.randint(0, w - 1)
            dy = random.randint(0, h - 1)
            if self.image.get_at((dx, dy))[3] > 0:
                color = random_col_range((80, 60, 40), 30)
                radius = random.randint(1, 3)
                pygame.draw.circle(self.image, color, (dx, dy), radius)

    def set_position(self, max_w, max_h):
        self.rect.x = random.randint(0, max_w - self.rect.width)
        self.rect.y = random.randint(0, max_h - self.rect.height)

    def draw(self, surface):
        surface.blit(self.image, self.rect)

    def get_yolo_bbox(self, screen_w, screen_h):
        mask_rects = self.mask.get_bounding_rects()
        if not mask_rects: return None
        union_rect = mask_rects[0]
        for r in mask_rects[1:]:
            union_rect.union_ip(r)
        screen_rect = union_rect.move(self.rect.x, self.rect.y)
        return [0] + normalize_yolo(screen_rect, screen_w, screen_h)


class EnvironmentDebris:
    def __init__(self, w, h, density_factor=1.0):
        self.w = w
        self.h = h
        self.elements = []

        # 1. Procedural Dirt (Base Layer)
        self._generate_dirt(density_factor)

        # 2. Rocks (Mid Layer - before grass)
        if os.path.exists(cp.ROCK_ASSET_DIR):
            self._generate_rocks(density_factor)

        # 3. Photo-realistic Grass (Top Debris Layer)
        if os.path.exists(cp.GRASS_ASSET_DIR):
            self._generate_grass_overlays(density_factor)

    def _process_image_otsu(self, filepath):
        """
        Helper to remove white backgrounds and shadows using Otsu's thresholding.
        Used for both grass and rocks.
        """
        img_bgr = cv2.imread(filepath)
        if img_bgr is None: return None

        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)

        # Otsu's Binarization
        _, mask = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        r, g, b = cv2.split(img_rgb)
        rgba = cv2.merge([r, g, b, mask])

        h, w = rgba.shape[:2]
        return pygame.image.frombuffer(rgba.tobytes(), (w, h), 'RGBA').convert_alpha()

    def _generate_rocks(self, density_factor):
        files = [f for f in os.listdir(cp.ROCK_ASSET_DIR) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
        if not files: return

        num_rocks = int(random.randint(cp.ROCKS_TO_SPAWN_MIN, cp.ROCKS_TO_SPAWN_MAX) * density_factor)

        for _ in range(num_rocks):
            filename = random.choice(files)
            rock_surf = self._process_image_otsu(os.path.join(cp.ROCK_ASSET_DIR, filename))
            if not rock_surf: continue

            # 1. Random Scale (Larger than grass)
            target_w = random.randint(cp.ROCK_OUTPUT_SIZE_MIN, cp.ROCK_OUTPUT_SIZE_MAX)
            orig_w, orig_h = rock_surf.get_size()
            aspect = orig_h / orig_w
            target_h = int(target_w * aspect)

            rock_img = pygame.transform.scale(rock_surf, (target_w, target_h))

            # 2. Random Rotation
            angle = random.uniform(0, 360)
            rock_img = pygame.transform.rotate(rock_img, angle)

            # 3. Random Position
            screen_x = random.randint(-target_w // 2, self.w)
            screen_y = random.randint(-target_h // 2, self.h)

            self.elements.append({
                'type': 'image',
                'surf': rock_img,
                'pos': (screen_x, screen_y)
            })

    def _generate_dirt(self, density_factor):
        num = int(random.randint(50, 200) * density_factor)
        for _ in range(num):
            size = random.randint(4, 12)
            x = random.randint(0, self.w)
            y = random.randint(0, self.h)
            col = random_col_range(cp.DIRT_COLOR_BASE, cp.DIRT_VARIANCE)
            self.elements.append({'type': 'rect', 'rect': (x, y, size, size), 'col': col})

    def _load_and_process_grass(self, filepath):
        """
        Loads image, applies Otsu's threshold to remove shadows/bg, returns Pygame Surface.
        """
        # Load in BGR (OpenCV default)
        img_bgr = cv2.imread(filepath)
        if img_bgr is None: return None

        # Convert to Grayscale
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        # Blur slightly to reduce noise for Otsu
        blur = cv2.GaussianBlur(gray, (5, 5), 0)

        # Otsu's Thresholding
        # cv2.THRESH_BINARY_INV because grass is dark (low val) and bg is white (high val)
        # We want grass to be White (255) in the mask to keep it opaque
        _, mask = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Convert BGR to RGB for Pygame
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        # Add Alpha Channel
        r, g, b = cv2.split(img_rgb)
        rgba = cv2.merge([r, g, b, mask])

        # Convert to Pygame Surface
        # Pygame image.frombuffer expects bytes
        h, w = rgba.shape[:2]
        surface = pygame.image.frombuffer(rgba.tobytes(), (w, h), 'RGBA').convert_alpha()
        return surface

    def _generate_grass_overlays(self, density_factor):
        files = [f for f in os.listdir(cp.GRASS_ASSET_DIR) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
        if not files: return

        # Pick random source images
        num_sources = cp.GRASS_IMAGES_TO_SAMPLE
        choices = random.sample(files, min(len(files), num_sources))

        for filename in choices:
            master_surf = self._load_and_process_grass(os.path.join(cp.GRASS_ASSET_DIR, filename))
            if not master_surf: continue

            mw, mh = master_surf.get_size()

            # Spawn crops
            count = int(random.randint(5, cp.GRASS_CLIPPINGS_PER_IMAGE) * density_factor)

            for _ in range(count):
                # 1. Random Crop
                cw = random.randint(cp.GRASS_CROP_SIZE_MIN, cp.GRASS_CROP_SIZE_MAX)
                ch = random.randint(cp.GRASS_CROP_SIZE_MIN, cp.GRASS_CROP_SIZE_MAX)

                # Ensure crop is within bounds
                if cw >= mw or ch >= mh: continue

                cx = random.randint(0, mw - cw)
                cy = random.randint(0, mh - ch)

                # Create Subsurface
                try:
                    crop = master_surf.subsurface((cx, cy, cw, ch))

                    # Optimization: Check if this crop is empty (transparent)
                    # We check the mask of the crop. If it's empty, skip it.
                    if pygame.mask.from_surface(crop).count() < 10:
                        continue

                    # 2. Scale Down
                    target_w = random.randint(cp.GRASS_OUTPUT_SIZE_MIN, cp.GRASS_OUTPUT_SIZE_MAX)
                    # Maintain aspect ratio
                    aspect = ch / cw
                    target_h = int(target_w * aspect)

                    final_img = pygame.transform.scale(crop, (target_w, target_h))

                    # 3. Position
                    screen_x = random.randint(0, self.w)
                    screen_y = random.randint(0, self.h)

                    self.elements.append({
                        'type': 'image',
                        'surf': final_img,
                        'pos': (screen_x, screen_y)
                    })

                except ValueError:
                    continue  # Crop out of bounds

    def draw(self, surface):
        for el in self.elements:
            if el['type'] == 'rect':
                pygame.draw.rect(surface, el['col'], el['rect'])
            elif el['type'] == 'line':
                pygame.draw.line(surface, el['col'], el['start'], el['end'], el['width'])
            elif el['type'] == 'image':
                surface.blit(el['surf'], el['pos'])