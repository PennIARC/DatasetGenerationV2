import math
import random


def normalize_yolo(rect, screen_w, screen_h):
    """
    Convert Pygame Rect to YOLO format (class x_center y_center width height)
    Normalized 0.0 to 1.0
    """
    dw = 1. / screen_w
    dh = 1. / screen_h

    x_center = rect.centerx * dw
    y_center = rect.centery * dh
    w = rect.width * dw
    h = rect.height * dh

    return [x_center, y_center, w, h]


def random_col_range(base_rgb, variance=30):
    """Returns a color shifted slightly from base."""
    r, g, b = base_rgb
    r = max(0, min(255, r + random.randint(-variance, variance)))
    g = max(0, min(255, g + random.randint(-variance, variance)))
    b = max(0, min(255, b + random.randint(-variance, variance)))
    return (r, g, b)


def clamp(val, min_val, max_val):
    return max(min_val, min(max_val, val))