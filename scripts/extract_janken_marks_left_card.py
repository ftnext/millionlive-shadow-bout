# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "Pillow",
# ]
# ///

import glob
import os

from PIL import Image, ImageDraw


def main():
    base_dir = "/Users/nikkie/study/playgrounds/shadow-bout"
    pdf_images_dir = os.path.join(base_dir, "pdf_images")
    output_path = os.path.join(pdf_images_dir, "janken_summary_left_card.png")

    image_paths = sorted(glob.glob(os.path.join(pdf_images_dir, "page_*.png")))
    image_paths = [
        p
        for p in image_paths
        if not p.endswith("page_001.png") and "janken_summary" not in p
    ]

    cols = 8
    rows = 7
    crop_size = 200

    summary_img = Image.new("RGB", (cols * crop_size, rows * crop_size), color="white")
    draw = ImageDraw.Draw(summary_img)

    for i, path in enumerate(image_paths):
        basename = os.path.basename(path)
        page_num_str = basename.replace("page_", "").replace(".png", "")

        try:
            with Image.open(path) as img:
                W, H = img.size
                # The card is vertically centered and horizontally centered in the left half.
                # The janken mark is at the top left of the card.
                # Let's crop x from 10% to 25% and y from 35% to 50%
                crop_box = (int(W * 0.12), int(H * 0.38), int(W * 0.22), int(H * 0.48))
                cropped = img.crop(crop_box)
                cropped = cropped.resize(
                    (crop_size, crop_size), Image.Resampling.LANCZOS
                )

                col = i % cols
                row = i // cols
                x = col * crop_size
                y = row * crop_size

                summary_img.paste(cropped, (x, y))
                draw.rectangle((x, y, x + 60, y + 25), fill="black")
                draw.text((x + 5, y + 5), page_num_str, fill="white")

        except Exception:
            pass

    summary_img.save(output_path)
    print("Done")


if __name__ == "__main__":
    main()
