"""Agricultural Crop Lifecycle Dataset Generator for PRAMAN.
Generates genuine, high-fidelity synthetic agricultural images with distinct visual
signatures for four lifecycle stages:
- SOWING: Plowed furrows, tilled soil, seed lines, loam/clay textures.
- CROP_GROWTH: Lush vegetative canopies, green leaf structures, crop rows.
- HARVEST: Ripe golden grains, mature wheat/paddy heads, cotton bolls on dry stalks.
- STORAGE: Stacked jute grain sacks, woven burlap textures, warehouse storage tarps.
"""

import os
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def generate_sowing_image(width=256, height=256, seed=None):
    """Generates an image of plowed soil, furrows, and seed trenches."""
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    # Base soil color (loam/clay brown)
    base_r = random.randint(90, 130)
    base_g = random.randint(60, 90)
    base_b = random.randint(35, 60)

    # Generate noisy soil background
    noise = np.random.normal(0, 15, (height, width, 3))
    soil = np.clip(np.array([base_r, base_g, base_b]) + noise, 0, 255).astype(np.uint8)
    img = Image.fromarray(soil)
    draw = ImageDraw.Draw(img)

    # Draw plow furrows (linear ridges with shadow and highlight)
    furrow_spacing = random.randint(18, 30)
    angle_offset = random.randint(-10, 10)

    for y in range(0, height + 40, furrow_spacing):
        # Shadow trough
        trough_color = (max(0, base_r - 40), max(0, base_g - 35), max(0, base_b - 25))
        ridge_color = (min(255, base_r + 30), min(255, base_g + 25), min(255, base_b + 15))

        draw.line([(-20, y + angle_offset), (width + 20, y - angle_offset)], fill=trough_color, width=4)
        draw.line([(-20, y + 5 + angle_offset), (width + 20, y + 5 - angle_offset)], fill=ridge_color, width=3)

        # Occasional seed granules or tiny clods
        for x in range(10, width, random.randint(15, 35)):
            if random.random() > 0.4:
                seed_color = (random.randint(180, 220), random.randint(160, 190), random.randint(100, 130))
                draw.ellipse([x, y + 2, x + 3, y + 5], fill=seed_color)

    # Slight surface texture blur
    return img.filter(ImageFilter.GaussianBlur(radius=0.5))


def generate_crop_growth_image(width=256, height=256, seed=None):
    """Generates an image of dense green crop foliage and canopy rows."""
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    # 50% grid/row crop field patterns, 50% organic foliage
    if random.random() > 0.5:
        # High contrast crop field (green foliage with stalks and soil rows)
        img = Image.new("RGB", (width, height), color=(34, 139, 34))  # Forest green
        draw = ImageDraw.Draw(img)
        step_x = max(10, width // 15)
        step_y = max(10, height // 12)
        for x in range(0, width, step_x):
            draw.line([(x, 0), (x, height)], fill=(139, 69, 19), width=2)
            for y in range(0, height, step_y):
                draw.polygon(
                    [(x, y), (x + step_x // 2, y + step_y // 2), (x, y + step_y)],
                    fill=(50, 205, 50),
                )
                draw.rectangle([x + 2, y + 2, x + 6, y + 6], fill=(40, 180, 40))
        return img.filter(ImageFilter.GaussianBlur(radius=0.4))

    # Base dark soil / under-canopy shadow
    base = np.zeros((height, width, 3), dtype=np.uint8)
    base[:, :, 0] = np.random.randint(30, 50, (height, width))
    base[:, :, 1] = np.random.randint(50, 80, (height, width))
    base[:, :, 2] = np.random.randint(20, 35, (height, width))
    img = Image.fromarray(base)
    draw = ImageDraw.Draw(img)

    # Draw crop rows and overlapping leaves
    row_spacing = random.randint(25, 40)
    for x_center in range(20, width + 20, row_spacing):
        # Draw vertical crop stalk band
        for y in range(5, height, random.randint(8, 16)):
            # Random leaf shape
            leaf_w = random.randint(16, 32)
            leaf_h = random.randint(10, 22)
            leaf_x = x_center + random.randint(-12, 12)
            leaf_y = y

            # Green chlorophyll hues
            g_val = random.randint(140, 220)
            r_val = random.randint(25, 75)
            b_val = random.randint(15, 60)
            leaf_color = (r_val, g_val, b_val)
            vein_color = (min(255, r_val + 30), min(255, g_val + 25), min(255, b_val + 20))

            # Leaf polygon (pointing left or right)
            direction = 1 if random.random() > 0.5 else -1
            draw.polygon([
                (leaf_x, leaf_y),
                (leaf_x + direction * (leaf_w // 2), leaf_y - leaf_h // 2),
                (leaf_x + direction * leaf_w, leaf_y),
                (leaf_x + direction * (leaf_w // 2), leaf_y + leaf_h // 2),
            ], fill=leaf_color)

            # Central leaf vein
            draw.line([
                (leaf_x, leaf_y),
                (leaf_x + direction * leaf_w, leaf_y)
            ], fill=vein_color, width=1)

    return img.filter(ImageFilter.GaussianBlur(radius=0.4))


def generate_harvest_image(width=256, height=256, seed=None):
    """Generates an image of ripe golden crops, mature wheat/paddy heads, or cotton bolls."""
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    mode = random.choice(["golden_grain", "cotton_field"])

    if mode == "golden_grain":
        # Base golden-amber field background
        base = np.zeros((height, width, 3), dtype=np.uint8)
        base[:, :, 0] = np.random.randint(170, 210, (height, width))  # High Red
        base[:, :, 1] = np.random.randint(140, 180, (height, width))  # Moderate Green (Yellowish)
        base[:, :, 2] = np.random.randint(30, 70, (height, width))    # Low Blue
        img = Image.fromarray(base)
        draw = ImageDraw.Draw(img)

        # Dense mature stalks and golden grain heads
        for x in range(5, width, random.randint(4, 9)):
            stalk_y = random.randint(height // 3, height)
            straw_color = (random.randint(190, 230), random.randint(160, 200), random.randint(50, 90))
            draw.line([(x, height), (x + random.randint(-8, 8), stalk_y)], fill=straw_color, width=2)

            # Grain ear / panicle
            head_len = random.randint(20, 45)
            for dy in range(0, head_len, 4):
                ear_color = (random.randint(210, 245), random.randint(180, 215), random.randint(70, 110))
                draw.ellipse([x - 4, stalk_y - dy, x + 4, stalk_y - dy + 5], fill=ear_color)
    else:
        # Cotton field with white bolls on dry stalks
        base = np.zeros((height, width, 3), dtype=np.uint8)
        base[:, :, 0] = np.random.randint(90, 120, (height, width))
        base[:, :, 1] = np.random.randint(75, 100, (height, width))
        base[:, :, 2] = np.random.randint(45, 70, (height, width))
        img = Image.fromarray(base)
        draw = ImageDraw.Draw(img)

        # Brown branches
        for _ in range(15):
            x1, y1 = random.randint(0, width), random.randint(height // 2, height)
            x2, y2 = x1 + random.randint(-40, 40), y1 - random.randint(40, 120)
            draw.line([(x1, y1), (x2, y2)], fill=(70, 45, 25), width=3)

        # Fluffy white cotton bolls
        for _ in range(random.randint(25, 45)):
            bx = random.randint(15, width - 15)
            by = random.randint(20, height - 30)
            radius = random.randint(8, 16)
            cotton_color = (random.randint(230, 250), random.randint(230, 250), random.randint(225, 245))
            draw.ellipse([bx - radius, by - radius, bx + radius, by + radius], fill=cotton_color)
            # Calyx / sepals
            draw.polygon([
                (bx - radius, by),
                (bx, by + radius + 4),
                (bx + radius, by)
            ], fill=(80, 50, 30))

    return img.filter(ImageFilter.GaussianBlur(radius=0.4))


def generate_storage_image(width=256, height=256, seed=None):
    """Generates an image of stacked burlap/jute grain sacks and warehouse storage."""
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    # Base warehouse background (neutral concrete gray)
    base = np.zeros((height, width, 3), dtype=np.uint8)
    base[:, :, 0] = np.random.randint(100, 130, (height, width))
    base[:, :, 1] = np.random.randint(105, 135, (height, width))
    base[:, :, 2] = np.random.randint(110, 140, (height, width))
    img = Image.fromarray(base)
    draw = ImageDraw.Draw(img)

    # Stacked jute bags in rows
    bag_h = random.randint(28, 42)
    bag_w = random.randint(60, 90)

    for row_y in range(height - 10, 40, -bag_h + 4):
        offset = random.randint(-15, 15)
        for col_x in range(-20, width + 40, bag_w - 6):
            x1 = col_x + offset
            y1 = row_y - bag_h
            x2 = x1 + bag_w
            y2 = row_y

            # Jute / burlap texture color (tan / brown-grey fabric)
            jute_r = random.randint(155, 185)
            jute_g = random.randint(130, 160)
            jute_b = random.randint(95, 125)
            bag_color = (jute_r, jute_g, jute_b)
            shadow_color = (max(0, jute_r - 40), max(0, jute_g - 40), max(0, jute_b - 35))

            # Rounded sack body
            draw.rounded_rectangle([x1, y1, x2, y2], radius=6, fill=bag_color, outline=shadow_color, width=2)

            # Stitching / tie ears at bag corners
            draw.ellipse([x1 - 2, y1 - 2, x1 + 6, y1 + 6], fill=shadow_color)
            draw.ellipse([x2 - 6, y1 - 2, x2 + 2, y1 + 6], fill=shadow_color)

            # Horizontal weave lines
            for wy in range(y1 + 6, y2 - 4, 6):
                draw.line([(x1 + 4, wy), (x2 - 4, wy)], fill=shadow_color, width=1)

    # Occasional blue or orange tarp on upper stack
    if random.random() > 0.5:
        tarp_color = random.choice([(30, 90, 180), (210, 100, 20)])
        tarp_y = random.randint(30, 80)
        draw.polygon([
            (0, tarp_y),
            (width, tarp_y + random.randint(-15, 15)),
            (width, tarp_y + 35),
            (0, tarp_y + 25)
        ], fill=tarp_color)

    return img.filter(ImageFilter.GaussianBlur(radius=0.5))


def build_crop_stage_dataset(base_dir="ai_engine/data/crop_stages", samples_per_class=60):
    """Builds complete agricultural dataset on disk."""
    classes = {
        "SOWING": generate_sowing_image,
        "CROP_GROWTH": generate_crop_growth_image,
        "HARVEST": generate_harvest_image,
        "STORAGE": generate_storage_image,
    }

    print(f"Creating agricultural dataset in {base_dir} with {samples_per_class} samples per class...")
    total_samples = 0

    for stage_name, generator_fn in classes.items():
        stage_dir = os.path.join(base_dir, stage_name)
        os.makedirs(stage_dir, exist_ok=True)

        for i in range(samples_per_class):
            seed = 1000 * (list(classes.keys()).index(stage_name) + 1) + i
            img = generator_fn(width=256, height=256, seed=seed)
            filename = f"{stage_name.lower()}_{i:03d}.jpg"
            filepath = os.path.join(stage_dir, filename)
            img.save(filepath, format="JPEG", quality=92)
            total_samples += 1

    print(f"Dataset successfully created: {total_samples} images across {len(classes)} classes.")
    return base_dir, total_samples


if __name__ == "__main__":
    build_crop_stage_dataset()
