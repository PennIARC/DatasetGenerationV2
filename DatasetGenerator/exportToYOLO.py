import cv2
import os
import shutil
import controlPanel as cp

# --- CONFIG ---
TARGET_SIZE = 640

# --- PATHS ---
INPUT_IMG_DIR = os.path.join(cp.OUTPUT_PATH, cp.IMAGES_DIR)
INPUT_LBL_DIR = os.path.join(cp.OUTPUT_PATH, cp.LABELS_DIR)

OUTPUT_BASE = "finalDataset"
OUTPUT_IMG_DIR = os.path.join(OUTPUT_BASE, "images")
OUTPUT_LBL_DIR = os.path.join(OUTPUT_BASE, "labels")


def process_dataset():
    # 1. Setup Directories
    if os.path.exists(OUTPUT_BASE):
        shutil.rmtree(OUTPUT_BASE)
    os.makedirs(OUTPUT_IMG_DIR)
    os.makedirs(OUTPUT_LBL_DIR)

    files = [f for f in os.listdir(INPUT_IMG_DIR) if f.endswith(('.jpg', '.png'))]
    total_files = len(files)

    print(f"Processing {total_files} images -> {TARGET_SIZE}x{TARGET_SIZE} (Stretched)...")

    for i, filename in enumerate(files):
        # --- PATHS ---
        src_img_path = os.path.join(INPUT_IMG_DIR, filename)
        name_no_ext = os.path.splitext(filename)[0]
        src_lbl_path = os.path.join(INPUT_LBL_DIR, name_no_ext + ".txt")

        dst_img_path = os.path.join(OUTPUT_IMG_DIR, filename)
        dst_lbl_path = os.path.join(OUTPUT_LBL_DIR, name_no_ext + ".txt")

        # --- 1. PROCESS IMAGE (STRETCH) ---
        img = cv2.imread(src_img_path)

        # Resize directly to target size (ignoring aspect ratio)
        img_resized = cv2.resize(img, (TARGET_SIZE, TARGET_SIZE), interpolation=cv2.INTER_LINEAR)

        cv2.imwrite(dst_img_path, img_resized)

        # --- 2. PROCESS LABELS ---
        # Because we are stretching the image and YOLO labels are normalized (0.0 to 1.0),
        # the label values DO NOT CHANGE. A point at 50% width is still at 50% width.
        # We simply copy the file.

        if os.path.exists(src_lbl_path):
            shutil.copy(src_lbl_path, dst_lbl_path)

        if i % 100 == 0:
            print(f"Processed {i}/{total_files}")

    print("Export Complete.")
    print(f"Dataset saved to: {os.path.abspath(OUTPUT_BASE)}")


if __name__ == "__main__":
    process_dataset()