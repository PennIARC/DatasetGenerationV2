import pygame
import os

# --- CONFIG ---
BOX_COLOR = (0, 255, 0)  # Green for Final Dataset
TEXT_COLOR = (255, 255, 255)
UI_BG_COLOR = (0, 0, 0, 180)

# --- PATHS ---
# This assumes the script is run from the DatasetGenerator folder
# or that finalDataset was created relative to this script
BASE_DIR = "DatasetGenerator/finalDataset"
IMG_DIR = os.path.join(BASE_DIR, "images")
LBL_DIR = os.path.join(BASE_DIR, "labels")


def parse_yolo_label(file_path, img_w, img_h):
    """
    Reads a YOLO txt file and returns a list of pygame Rects.
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

        # Parse (class x y w h)
        x_center = float(parts[1])
        y_center = float(parts[2])
        w = float(parts[3])
        h = float(parts[4])

        # Convert to Pixel Coordinates relative to the specific image size
        pixel_w = w * img_w
        pixel_h = h * img_h
        pixel_x = (x_center * img_w) - (pixel_w / 2)
        pixel_y = (y_center * img_h) - (pixel_h / 2)

        rects.append(pygame.Rect(pixel_x, pixel_y, pixel_w, pixel_h))

    return rects


def main():
    pygame.init()

    # Get File List
    if not os.path.exists(IMG_DIR):
        print(f"Error: Directory {IMG_DIR} not found.")
        print("Did you run 'exportToYolo.py' yet?")
        return

    files = sorted([f for f in os.listdir(IMG_DIR) if f.endswith(('.jpg', '.png'))])

    if not files:
        print("No images found in finalDataset/images.")
        return

    # Load first image to determine window size (Should be 640x640)
    first_img = pygame.image.load(os.path.join(IMG_DIR, files[0]))
    win_w, win_h = first_img.get_size()

    # Setup Screen (Windowed, not fullscreen, fitting the letterboxed image)
    screen = pygame.display.set_mode((win_w, win_h))
    pygame.display.set_caption(f"YOLO Dataset Viewer ({win_w}x{win_h})")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 18, bold=True)

    index = 0
    current_image = None
    current_rects = []
    dirty = True

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

        # --- Data Loading ---
        if dirty:
            filename = files[index]
            img_path = os.path.join(IMG_DIR, filename)
            lbl_filename = os.path.splitext(filename)[0] + ".txt"
            lbl_path = os.path.join(LBL_DIR, lbl_filename)

            # Load Image
            current_image = pygame.image.load(img_path).convert()

            # Parse Labels
            # We pass the image dimensions because coordinates are normalized to THIS specific image
            current_rects = parse_yolo_label(lbl_path, win_w, win_h)

            dirty = False

        # --- Rendering ---
        screen.blit(current_image, (0, 0))

        # Draw Boxes
        for rect in current_rects:
            pygame.draw.rect(screen, BOX_COLOR, rect, 2)
            # Add semi-transparent fill
            s = pygame.Surface((rect.width, rect.height))
            s.set_alpha(60)
            s.fill(BOX_COLOR)
            screen.blit(s, (rect.x, rect.y))

        # UI Overlay
        ui_text_lines = [
            f"File: {files[index]}",
            f"Index: {index + 1}/{len(files)}",
            f"Mines: {len(current_rects)}",
            f"Res: {win_w}x{win_h}"
        ]

        # UI Background
        ui_height = len(ui_text_lines) * 22 + 10
        ui_surface = pygame.Surface((250, ui_height))
        ui_surface.set_alpha(180)
        ui_surface.fill((0, 0, 0))
        screen.blit(ui_surface, (5, 5))

        # UI Text
        for i, line in enumerate(ui_text_lines):
            text_surf = font.render(line, True, TEXT_COLOR)
            screen.blit(text_surf, (15, 10 + i * 22))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    main()