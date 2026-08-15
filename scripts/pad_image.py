from pathlib import Path

from PIL import Image


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = REPOSITORY_ROOT / 'frontend' / 'attendx' / 'assets'

def pad_image(input_path, output_path, scale_factor=3):
    img = Image.open(input_path)
    width, height = img.size

    new_width = int(width * scale_factor)
    new_height = int(height * scale_factor)

    # Get the background color from the top-left pixel
    bg_color = img.getpixel((0, 0))

    new_img = Image.new('RGB', (new_width, new_height), bg_color)

    # Paste the original image into the center
    offset_x = (new_width - width) // 2
    offset_y = (new_height - height) // 2
    new_img.paste(img, (offset_x, offset_y))

    new_img.save(output_path)
    print(f"Padded image saved to {output_path}")

if __name__ == '__main__':
    pad_image(
        ASSETS_DIR / 'logo.jpg.jpeg',
        ASSETS_DIR / 'splash_logo_generated.jpg',
    )
