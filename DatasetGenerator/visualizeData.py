import pygame
import os
import controlPanel as cp

# --- CONFIG ---
BOX_COLOR = (255, 50, 50)  # Red
TEXT_COLOR = (255, 255, 255)
UI_BG_COLOR = (0, 0, 0, 180)  # Semi-transparent black

# --- PATHS ---
IMG_DIR = os.path.join(cp.OUTPUT_PATH, cp.IMAGES_DIR)
LBL_DIR = os.path.join(cp.OUTPUT_PATH, cp.LABELS_DIR)


def parse_yolo_label(file_path, img_w, img_h):
    """
    Reads a YOLO txt file and returns a list of pygame Rects.
    YOLO format: class x_center y_center width height (normalized 0-1)
    """
    rects = []
    if not os.path.exists(file_path):
        return rects

    with open(file_path, 'r') as f:
        lines = f.readlines()

    for line in lines:
        parts = line.strip().split()
        if len(parts) < 5:
            continue

        # Parse (we ignore class_id [0] since we only have one class for now)
        x_center = float(parts[1])
        y_center = float(parts[2])
        w = float(parts[3])
        h = float(parts[4])

        # Convert to Pixel Coordinates
        pixel_w = w * img_w
        pixel_h = h * img_h
        pixel_x = (x_center * img_w) - (pixel_w / 2)
        pixel_y = (y_center * img_h) - (pixel_h / 2)

        rects.append(pygame.Rect(pixel_x, pixel_y, pixel_w, pixel_h))

    return rects


def main():
    pygame.init()

    # Setup Screen
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.display.set_caption("IARC Dataset Visualizer")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 24, bold=True)

    # Get File List
    if not os.path.exists(IMG_DIR):
        print(f"Error: Directory {IMG_DIR} not found. Run main.py first.")
        return

    # Sort files to ensure 00000, 00001 order
    files = sorted([f for f in os.listdir(IMG_DIR) if f.endswith(('.jpg', '.png'))])

    if not files:
        print("No images found.")
        return

    index = 0
    current_image = None
    current_rects = []

    # Load Initial
    dirty = True  # Flag to reload image only when changed

    running = True
    while running:
        # --- Event Handling ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_RIGHT:
                    index = (index + 1) % len(files)
                    dirty = True
                elif event.key == pygame.K_LEFT:
                    index = (index - 1) % len(files)
                    dirty = True

        # --- Data Loading (Only if Changed) ---
        if dirty:
            filename = files[index]
            img_path = os.path.join(IMG_DIR, filename)

            # Load Label (Assumes same name but .txt)
            lbl_filename = os.path.splitext(filename)[0] + ".txt"
            lbl_path = os.path.join(LBL_DIR, lbl_filename)

            # Load Image
            current_image = pygame.image.load(img_path).convert()

            # Parse Labels
            current_rects = parse_yolo_label(lbl_path, cp.SCREEN_WIDTH, cp.SCREEN_HEIGHT)

            dirty = False

        # --- Rendering ---

        # 1. Draw Image
        screen.blit(current_image, (0, 0))

        # 2. Draw Bounding Boxes
        for rect in current_rects:
            # Draw Thick Box
            pygame.draw.rect(screen, BOX_COLOR, rect, 3)
            # Draw semi-transparent fill (optional, for visibility check)
            s = pygame.Surface((rect.width, rect.height))
            s.set_alpha(50)
            s.fill(BOX_COLOR)
            screen.blit(s, (rect.x, rect.y))

        # 3. Draw UI Overlay
        ui_text_lines = [
            f"File: {files[index]} ({index + 1}/{len(files)})",
            f"Mines Detected: {len(current_rects)}",
            "Controls: Left/Right Arrows to scroll, ESC to quit"
        ]

        # Draw UI Background Box
        ui_height = len(ui_text_lines) * 30 + 10
        ui_surface = pygame.Surface((600, ui_height))
        ui_surface.set_alpha(180)
        ui_surface.fill((0, 0, 0))
        screen.blit(ui_surface, (10, 10))

        # Render Text
        for i, line in enumerate(ui_text_lines):
            text_surf = font.render(line, True, TEXT_COLOR)
            screen.blit(text_surf, (20, 20 + i * 30))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    main()